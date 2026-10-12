"""Retrieval metrics against gold_doc_ids (spec 8.1).

The input is the document of each ranked chunk, in rank order. k counts chunks, as the LLM sees
chunks: Recall@5 = share of the gold documents present in the top 5 chunks.
"""

from __future__ import annotations

from collections.abc import Sequence
from statistics import fmean
from typing import Any

KS = (1, 3, 5)


def recall_at_k(chunk_docs: Sequence[str], gold: Sequence[str], k: int) -> float:
    return len(set(chunk_docs[:k]) & set(gold)) / len(set(gold))


def reciprocal_rank(chunk_docs: Sequence[str], gold: Sequence[str]) -> float:
    """1 / rank of the first chunk from a gold document; 0 if none was retrieved."""
    return next((1 / rank for rank, d in enumerate(chunk_docs, start=1) if d in set(gold)), 0.0)


def retrieval_aggregate(rows: Sequence[dict[str, Any]]) -> dict[str, Any]:
    return {
        "n": len(rows),
        **{f"recall@{k}": fmean(r[f"recall@{k}"] for r in rows) for k in KS},
        "mrr": fmean(r["rr"] for r in rows),
    }
