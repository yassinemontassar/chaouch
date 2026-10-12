"""Sanity check for an embedder's index and query encoding (ADR 0013, Qwen3-Embedding-0.6B).

Rules out pipeline bugs before blaming the model:
1. batch padding / last-token pooling: a short chunk embedded alone vs batched with the longest one;
2. index consistency: freshly embedded chunks vs the vectors stored in pgvector;
3. the query instruction: rankings of a few Arabic-script questions with and without it.

Usage: uv run python -m scripts.qwen_sanity_check [--embedder qwen3_emb_0_6b] [--questions 5]
(after `uv run tasks.py index`)
"""

from __future__ import annotations

import argparse
import sys

import numpy as np

from chaouch.config import Settings, load_retrieval_config
from chaouch.retrieval.chunks import indexed_text, load_chunks
from chaouch.retrieval.models import _sentence_transformer, load_embedder
from chaouch.retrieval.store import assert_fresh, chunk_vectors, connect
from evals.gold import load_gold

TOP = 5


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--embedder", default="qwen3_emb_0_6b")
    parser.add_argument("--questions", type=int, default=5, help="Arabic-script questions to show")
    args = parser.parse_args()

    cfg = load_retrieval_config().retrieval
    chunks, sha = load_chunks()
    by_id = {c.chunk_id: c for c in chunks}
    with connect(Settings().database_dsn()) as conn:
        assert_fresh(conn, args.embedder, sha)
        stored = chunk_vectors(conn, args.embedder)

    model = _sentence_transformer(cfg.embedders[args.embedder].name, cfg.device)
    modules = [type(m).__name__ for m in model]
    print(f"padding side: {model.tokenizer.padding_side}; modules: {modules}")
    print(f"prompts: {model.prompts}")
    embedder = load_embedder(cfg, args.embedder)

    short = min(chunks, key=lambda c: c.n_tokens)
    long = max(chunks, key=lambda c: c.n_tokens)
    alone = embedder.embed_docs([indexed_text(short)])[0]
    batched = embedder.embed_docs([indexed_text(long), indexed_text(short)])[1]
    print(
        f"\n1. {short.chunk_id} ({short.n_tokens} tokens) alone vs batched: {alone @ batched:.4f}"
    )

    sample = chunks[::7]
    fresh = [embedder.embed_docs([indexed_text(c)])[0] for c in sample]
    cosines = [round(float(f @ stored[c.chunk_id]), 4) for f, c in zip(fresh, sample, strict=True)]
    print(f"2. fresh vs stored, {len(sample)} chunks: {cosines}")

    ids = list(stored)
    matrix = np.stack([stored[i] for i in ids])
    questions = [q for q in load_gold() if q.category == "in_scope" and q.script == "arabic"]
    print("\n3. rankings (gold rank among chunks, top documents):")
    for q in questions[: args.questions]:
        variants = (
            ("prompt", embedder.embed_queries([q.question])[0]),
            ("no prompt", embedder.embed_docs([q.question])[0]),
        )
        for label, vector in variants:
            order = [ids[i] for i in np.argsort(-(matrix @ vector))]
            docs = [by_id[c].doc_id for c in order]
            gold_rank = next((r for r, d in enumerate(docs, 1) if d in q.gold_doc_ids), None)
            print(f"{q.id:10} {label:9} gold rank {gold_rank}: {docs[:TOP]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
