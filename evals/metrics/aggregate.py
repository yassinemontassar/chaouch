"""Aggregate per-question results into the numbers that go in reports."""

from __future__ import annotations

import math
from collections.abc import Sequence
from statistics import fmean
from typing import Any


def percentile(values: Sequence[float], p: float) -> float | None:
    """Nearest-rank percentile."""
    if not values:
        return None
    ordered = sorted(values)
    return ordered[max(0, math.ceil(p / 100 * len(ordered)) - 1)]


def mean(values: Sequence[float | None]) -> float | None:
    present = [v for v in values if v is not None]
    return fmean(present) if present else None


def aggregate(results: Sequence[dict[str, Any]]) -> dict[str, Any]:
    answered = [r for r in results if r["answer"] is not None]
    latencies = [r["latency_ms"] for r in answered]
    with_oracle = [r for r in results if r["oracle_truncated"] is not None]
    return {
        "n": len(results),
        "n_errors": sum(r["error"] is not None for r in results),
        "correctness": mean([r["correctness"] for r in results]),
        "faithfulness": mean([r["faithfulness"] for r in results]),
        "dialect": mean([r["dialect_score"] for r in results]),
        "latency_p50_ms": percentile(latencies, 50),
        "latency_p95_ms": percentile(latencies, 95),
        "prompt_tokens": mean([r["prompt_tokens"] for r in answered]),
        "completion_tokens": mean([r["completion_tokens"] for r in answered]),
        "oracle_truncation_rate": (
            mean([float(r["oracle_truncated"]) for r in with_oracle]) if with_oracle else None
        ),
    }


def breakdown(results: Sequence[dict[str, Any]], field: str) -> dict[str, dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = {}
    for r in results:
        groups.setdefault(r[field], []).append(r)
    return {key: aggregate(group) for key, group in sorted(groups.items())}
