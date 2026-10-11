from __future__ import annotations

import math
import random
from collections.abc import Callable, Sequence
from statistics import fmean
from typing import Any


def percentile(values: Sequence[float], p: float) -> float | None:
    """Nearest-rank percentile."""
    if not values:
        return None
    ordered = sorted(values)
    return ordered[max(0, math.ceil(p / 100 * len(ordered)) - 1)]


# An answer we could show as is: every required fact, and (nearly) every claim in the documents.
TRUSTWORTHY_FAITHFULNESS = 0.9


def mean(values: Sequence[float | None]) -> float | None:
    present = [v for v in values if v is not None]
    return fmean(present) if present else None


def trustworthy(r: dict[str, Any]) -> float:
    return float(r["correctness"] == 1.0 and (r["faithfulness"] or 0) >= TRUSTWORTHY_FAITHFULNESS)


def aggregate(results: Sequence[dict[str, Any]]) -> dict[str, Any]:
    answered = [r for r in results if r["answer"] is not None]
    latencies = [r["latency_ms"] for r in answered]
    with_oracle = [r for r in results if r["oracle_truncated"] is not None]
    return {
        "n": len(results),
        "n_errors": sum(r["error"] is not None for r in results),
        "n_generation_failures": sum(r["generation_failure"] is not None for r in results),
        "n_echoes": sum(r["echo"] for r in results),
        "correctness": mean([r["correctness"] for r in results]),
        "faithfulness": mean([r["faithfulness"] for r in results]),
        "dialect": mean([r["dialect_score"] for r in results]),
        # only with documents; a missing faithfulness score counts as not trustworthy
        "trustworthy_rate": mean([trustworthy(r) for r in with_oracle]) if with_oracle else None,
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


def bootstrap_ci(
    results: Sequence[dict[str, Any]],
    metric: Callable[[dict[str, Any]], float | None],
    *,
    resamples: int = 2000,
    seed: int = 0,
) -> list[float] | None:
    """95% percentile interval of the mean, resampling questions with replacement."""
    values = [metric(r) for r in results]
    if all(v is None for v in values):
        return None
    rng = random.Random(seed)
    means = sorted(
        m
        for _ in range(resamples)
        if (m := mean([values[rng.randrange(len(values))] for _ in values])) is not None
    )
    return [round(means[int(0.025 * len(means))], 3), round(means[int(0.975 * len(means)) - 1], 3)]


def confidence_intervals(results: Sequence[dict[str, Any]]) -> dict[str, list[float] | None]:
    with_oracle = [r for r in results if r["oracle_truncated"] is not None]
    return {
        "correctness": bootstrap_ci(results, lambda r: r["correctness"]),
        "dialect": bootstrap_ci(results, lambda r: r["dialect_score"]),
        "trustworthy_rate": bootstrap_ci(with_oracle, trustworthy) if with_oracle else None,
    }
