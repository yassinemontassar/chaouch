"""Hybrid retrieval (spec 9.2): BM25 + dense → RRF → cross-encoder rerank → top k.

The four modes share one code path so ADR 0013 compares exactly what the app runs.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Literal, get_args

from chaouch.config import SearchConfig
from chaouch.retrieval.bm25 import BM25
from chaouch.retrieval.chunks import ChunkRecord, indexed_text
from chaouch.retrieval.fusion import rrf
from chaouch.retrieval.models import Rerank
from chaouch.retrieval.normalize import tokenize

Mode = Literal["bm25", "dense", "hybrid", "hybrid_rerank"]
MODES: tuple[Mode, ...] = get_args(Mode)

# (query, n) -> chunk ids, nearest first; wraps the embedder and the pgvector search
DenseSearch = Callable[[str, int], list[str]]


@dataclass(frozen=True)
class Corpus:
    chunks: list[ChunkRecord]
    by_id: dict[str, ChunkRecord]
    bm25: BM25

    @classmethod
    def build(cls, chunks: Sequence[ChunkRecord], cfg: SearchConfig) -> Corpus:
        chunks = list(chunks)
        bm25 = BM25.build([tokenize(indexed_text(c)) for c in chunks], cfg.bm25)
        return cls(chunks, {c.chunk_id: c for c in chunks}, bm25)

    def bm25_search(self, query: str, n: int) -> list[str]:
        return [self.chunks[i].chunk_id for i in self.bm25.rank(tokenize(query), n)]


def rank(
    mode: Mode,
    query: str,
    bm25_ids: list[str],
    dense_ids: list[str],
    corpus: Corpus,
    cfg: SearchConfig,
    rerank: Rerank | None = None,
) -> list[str]:
    """The full ranking of a mode from the two candidate lists (the eval scores it beyond top_k)."""
    if mode == "bm25":
        return bm25_ids
    if mode == "dense":
        return dense_ids
    fused = rrf([bm25_ids, dense_ids], cfg.rrf_k)
    if mode == "hybrid":
        return fused
    if rerank is None:
        raise ValueError("hybrid_rerank needs a reranker")
    pool = fused[: cfg.rerank_candidates]
    scores = rerank(query, [indexed_text(corpus.by_id[i]) for i in pool])
    order = sorted(range(len(pool)), key=lambda i: -scores[i])  # stable: ties keep fused order
    return [pool[i] for i in order]


def retrieve(
    query: str,
    mode: Mode,
    corpus: Corpus,
    dense_search: DenseSearch,
    cfg: SearchConfig,
    rerank: Rerank | None = None,
) -> list[ChunkRecord]:
    """The top_k chunks for a query, with source_url, title and retrieved_at for citations."""
    bm25_ids = corpus.bm25_search(query, cfg.candidates) if mode != "dense" else []
    dense_ids = dense_search(query, cfg.candidates) if mode != "bm25" else []
    ranking = rank(mode, query, bm25_ids, dense_ids, corpus, cfg, rerank)
    return [corpus.by_id[i] for i in ranking[: cfg.top_k]]
