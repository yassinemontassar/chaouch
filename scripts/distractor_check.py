"""Pre-check for distractor documents (ADR 0013): could a distractor answer a gold question?

For every in-scope question, (question + required facts) is scored against every chunk of the
question's gold documents and every distractor chunk. A distractor chunk scoring at least as high
as the best gold chunk is flagged for a human read. This screens; it does not decide.

Scorers: each embedder (vectors from the pgvector index, seconds) and, with --reranker, the
cross-encoder (~4 s per pair on CPU, so ~1.5 h for the whole gold set).

Usage: uv run python -m scripts.distractor_check [--reranker]   (after `uv run tasks.py index`)
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Callable

from chaouch.config import Settings, load_retrieval_config
from chaouch.retrieval.chunks import ChunkRecord, indexed_text, load_chunks
from chaouch.retrieval.models import load_embedder, load_reranker, release_models
from chaouch.retrieval.store import assert_fresh, chunk_vectors, connect
from evals.gold import GoldQuestion, load_gold

TOP = 3
# (question index, chunks) -> one score per chunk
Scorer = Callable[[int, list[ChunkRecord]], list[float]]


def query_text(q: GoldQuestion) -> str:
    return f"{q.question}\n" + "; ".join(q.required_facts)


def screen(
    name: str, questions: list[GoldQuestion], chunks: list[ChunkRecord], score: Scorer
) -> list[tuple[str, str, str, float, float]]:
    distractors = [c for c in chunks if c.role == "distractor"]
    flagged = []
    print(f"\n== {name}", flush=True)
    for i, q in enumerate(questions):
        gold = [c for c in chunks if c.doc_id in q.gold_doc_ids]
        scores = score(i, [*gold, *distractors])
        best_gold = max(scores[: len(gold)])
        ranked = sorted(zip(scores[len(gold) :], distractors, strict=True), key=lambda p: -p[0])
        top = ", ".join(f"{c.chunk_id} {s:+.2f}" for s, c in ranked[:TOP])
        hits = [(s, c) for s, c in ranked if s >= best_gold]
        mark = "FLAG" if hits else "ok  "
        print(f"{mark} {q.id:10} best gold {best_gold:+.2f} | top distractors: {top}", flush=True)
        flagged += [(name, q.id, c.chunk_id, s, best_gold) for s, c in hits]
    return flagged


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reranker", action="store_true", help="also screen with the reranker")
    args = parser.parse_args()

    cfg = load_retrieval_config().retrieval
    chunks, sha = load_chunks()
    if not any(c.role == "distractor" for c in chunks):
        print("no distractor chunks in chunks.jsonl")
        return 0
    questions = [q for q in load_gold() if q.category == "in_scope"]
    queries = [query_text(q) for q in questions]
    flagged = []

    with connect(Settings().database_dsn()) as conn:
        for key in cfg.embedders:
            assert_fresh(conn, key, sha)
            vectors = chunk_vectors(conn, key)
            query_vectors = load_embedder(cfg, key).embed_queries(queries)
            release_models()

            def by_cosine(
                i: int, cs: list[ChunkRecord], qv=query_vectors, vs=vectors
            ) -> list[float]:
                return [float(vs[c.chunk_id] @ qv[i]) for c in cs]

            flagged += screen(key, questions, chunks, by_cosine)

    if args.reranker:
        rerank = load_reranker(cfg)
        flagged += screen(
            "reranker",
            questions,
            chunks,
            lambda i, cs: rerank(queries[i], [indexed_text(c) for c in cs]),
        )

    print(f"\n{len(flagged)} flagged (scorer, question, distractor chunk) triples")
    for scorer, qid, chunk_id, score, best in flagged:
        print(f"  {scorer}: {qid}: {chunk_id} {score:+.2f} >= best gold {best:+.2f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
