from __future__ import annotations

from collections.abc import Sequence


def rrf(rankings: Sequence[Sequence[str]], k: int) -> list[str]:
    """Reciprocal Rank Fusion: score(d) = sum over rankings of 1 / (k + rank), rank from 1.
    Ties keep the order in which items were first seen (first ranking first)."""
    scores: dict[str, float] = {}
    for ranking in rankings:
        for rank, item in enumerate(ranking, start=1):
            scores[item] = scores.get(item, 0.0) + 1 / (k + rank)
    order = {item: i for i, item in enumerate(scores)}  # dicts keep insertion order
    return sorted(scores, key=lambda item: (-scores[item], order[item]))
