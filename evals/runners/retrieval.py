"""Retrieval eval (spec 8.4): Recall@k and MRR against gold_doc_ids. No LLM, no judge.

Usage: uv run tasks.py eval-retrieval   (after `db-up` and `index`)

Scores every configuration (BM25, then dense / hybrid / hybrid+rerank per embedder) on every corpus:
`core` (the procedure documents) and, once distractor documents exist, `full`.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from operator import itemgetter
from pathlib import Path
from typing import Any

from chaouch.config import SearchConfig, Settings, load_retrieval_config
from chaouch.retrieval.chunks import ChunkRecord, load_chunks
from chaouch.retrieval.models import load_embedder, load_reranker, release_models
from chaouch.retrieval.pipeline import Corpus, Mode, rank
from chaouch.retrieval.store import StaleIndexError, assert_fresh, connect, dense_search
from evals.gold import GOLD_PATH, GoldQuestion, load_gold
from evals.metrics.aggregate import bootstrap_ci, breakdown, paired_bootstrap_ci, percentile
from evals.metrics.retrieval import KS, recall_at_k, reciprocal_rank, retrieval_aggregate
from evals.runners.baseline import REPORTS_DIR, fmt, fmt_ci

CORPUS_ROLES = {"core": ("core",), "full": ("core", "distractor")}
BREAKDOWNS = ("script", "doc_language", "procedure")
METRICS = (*(f"recall@{k}" for k in KS), "rr")  # rr per question; its mean is MRR
PAIRED_METRICS = ("rr", "recall@1")


@dataclass(frozen=True)
class RunConfig:
    name: str
    mode: Mode
    embedder: str | None


def run_configs(cfg: SearchConfig) -> list[RunConfig]:
    out = [RunConfig("bm25", "bm25", None)]
    for key in cfg.embedders:
        for mode in ("dense", "hybrid", "hybrid_rerank"):
            out.append(RunConfig(f"{mode}:{key}", mode, key))
    return out


def gold_doc_language(gold: Sequence[str], language_of: Mapping[str, str]) -> str:
    languages = {language_of[d] for d in gold}
    return languages.pop() if len(languages) == 1 else "mixed"


def score_row(
    q: GoldQuestion,
    corpus: str,
    config: str,
    ranking: Sequence[str],
    chunks_by_id: dict[str, ChunkRecord],
    language_of: Mapping[str, str],
    top_k: int,
) -> dict[str, Any]:
    chunk_docs = [chunks_by_id[c].doc_id for c in ranking]
    return {
        "id": q.id,
        "corpus": corpus,
        "config": config,
        "script": q.script,
        "procedure": q.procedure,
        "doc_language": gold_doc_language(q.gold_doc_ids, language_of),
        "gold_doc_ids": q.gold_doc_ids,
        "top_chunks": list(ranking[:top_k]),
        **{f"recall@{k}": recall_at_k(chunk_docs, q.gold_doc_ids, k) for k in KS},
        "rr": reciprocal_rank(chunk_docs, q.gold_doc_ids),
    }


def summarize(rows: Sequence[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Per corpus, per config: means, bootstrap CIs and breakdowns."""
    groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for r in rows:
        groups[(r["corpus"], r["config"])].append(r)
    out: dict[str, dict[str, Any]] = defaultdict(dict)
    for (corpus, config), group in groups.items():
        out[corpus][config] = {
            "metrics": retrieval_aggregate(group),
            "ci95": {m: bootstrap_ci(group, itemgetter(m)) for m in METRICS},
            "breakdowns": {f: breakdown(group, f, retrieval_aggregate) for f in BREAKDOWNS},
        }
    return dict(out)


def comparison_pairs(configs: Sequence[RunConfig]) -> list[tuple[str, str]]:
    """Each config vs bm25, hybrid vs dense, the reranker vs plain hybrid, and each later embedder
    vs the first one, mode by mode; only pairs whose two configs were run."""
    names = {c.name for c in configs}
    pairs = [(c.name, "bm25") for c in configs if c.name != "bm25"]
    embedders = list(dict.fromkeys(c.embedder for c in configs if c.embedder))
    pairs += [(f"hybrid:{e}", f"dense:{e}") for e in embedders]  # what BM25 adds to dense
    pairs += [(f"hybrid_rerank:{e}", f"hybrid:{e}") for e in embedders]  # what the reranker adds
    pairs += [(f"hybrid_rerank:{e}", f"dense:{e}") for e in embedders]  # rerank vs the best plain
    for other in embedders[1:]:
        for mode in ("dense", "hybrid", "hybrid_rerank"):
            pairs.append((f"{mode}:{other}", f"{mode}:{embedders[0]}"))
    return [(a, b) for a, b in pairs if a in names and b in names]


def paired_differences(
    rows: Sequence[dict[str, Any]], pairs: Sequence[tuple[str, str]]
) -> dict[str, list[dict[str, Any]]]:
    by_key = {(r["corpus"], r["config"], r["id"]): r for r in rows}
    corpora = list(dict.fromkeys(r["corpus"] for r in rows))
    ids = sorted({r["id"] for r in rows})
    out: dict[str, list[dict[str, Any]]] = {}
    for corpus in corpora:
        out[corpus] = []
        for a, b in pairs:
            for metric in PAIRED_METRICS:
                va = [by_key[(corpus, a, i)][metric] for i in ids]
                vb = [by_key[(corpus, b, i)][metric] for i in ids]
                out[corpus].append(
                    {"a": a, "b": b, "metric": metric, **paired_bootstrap_ci(va, vb)}
                )
    return out


def latency_summary(timings: dict[str, list[float]]) -> dict[str, dict[str, float | None]]:
    return {
        stage: {"p50_ms": percentile(values, 50), "p95_ms": percentile(values, 95)}
        for stage, values in timings.items()
    }


def metric_label(metric: str) -> str:
    return "MRR" if metric == "rr" else metric.replace("recall@", "R@")


def markdown(report: dict[str, Any]) -> str:
    lines = [
        f"# Retrieval eval, {report['created_at'][:10]}",
        "",
        f"Gold set: {report['gold']['n_questions']} in-scope questions "
        f"(questions.jsonl sha256 {report['gold']['sha256'][:12]}). "
        f"Chunks: sha256 {report['chunks_sha256'][:12]}.",
        "R@k = share of the gold documents found in the top k **chunks** (what the LLM sees); "
        "MRR = mean of 1 / rank of the first chunk from a gold document. "
        "In brackets: 95% bootstrap intervals over questions.",
    ]
    configs = [c["name"] for c in report["configs"]]
    for corpus, summary in report["summary"].items():
        info = report["corpora"][corpus]
        lines += [
            "",
            f"## Corpus `{corpus}`: {info['docs']} documents, {info['chunks']} chunks",
            "",
            "| Config | R@1 | R@3 | R@5 | MRR |",
            "|---|---|---|---|---|",
        ]
        for name in configs:
            s = summary[name]
            cells = [
                f"{fmt(s['metrics'][m if m != 'rr' else 'mrr'])} ({fmt_ci(s['ci95'][m])})"
                for m in METRICS
            ]
            lines.append(f"| {name} | {' | '.join(cells)} |")
        for field in BREAKDOWNS:
            keys = sorted({k for name in configs for k in summary[name]["breakdowns"][field]})
            first = summary[configs[0]]["breakdowns"][field]
            header = " | ".join(f"{k} (n={first[k]['n']})" if k in first else k for k in keys)
            lines += [
                "",
                f"By {field.replace('_', ' ')} (R@1 / MRR):",
                "",
                f"| Config | {header} |",
                "|---" * (len(keys) + 1) + "|",
            ]
            for name in configs:
                b = summary[name]["breakdowns"][field]
                cells = [
                    f"{fmt(b[k]['recall@1'])} / {fmt(b[k]['mrr'])}" if k in b else "–" for k in keys
                ]
                lines.append(f"| {name} | {' | '.join(cells)} |")
        lines += [
            "",
            "Paired differences (A − B on the same questions, 95% paired bootstrap):",
            "",
            "| A | B | Metric | A − B | 95% CI |",
            "|---|---|---|---|---|",
        ]
        for d in report["paired"][corpus]:
            lines.append(
                f"| {d['a']} | {d['b']} | {metric_label(d['metric'])} | {d['diff']:+.2f} "
                f"| {d['ci95'][0]:+.2f} to {d['ci95'][1]:+.2f} |"
            )
    lines += ["", "## Latency per stage (CPU)", "", "| Stage | p50 ms | p95 ms |", "|---|---|---|"]
    for stage, lat in report["latency"].items():
        lines.append(f"| {stage} | {fmt(lat['p50_ms'], 0)} | {fmt(lat['p95_ms'], 0)} |")
    cfg = report["retrieval_config"]
    lines += [
        "",
        f"Settings: candidates {cfg['candidates']} per retriever, RRF k {cfg['rrf_k']}, "
        f"rerank {cfg['rerank_candidates']} with {cfg['reranker_model']} "
        f"(max_length {cfg['rerank_max_length']}), top_k {cfg['top_k']}, device {cfg['device']}.",
    ]
    return "\n".join(lines) + "\n"


def ms_since(start: float) -> float:
    return (time.perf_counter() - start) * 1000


def select[T](available: dict[str, T], wanted: str | None, what: str) -> dict[str, T]:
    if not wanted:
        return available
    names = wanted.split(",")
    unknown = [n for n in names if n not in available]
    if unknown:
        raise SystemExit(
            f"unknown {what}: {', '.join(unknown)} (available: {', '.join(available)})"
        )
    return {n: available[n] for n in names}


def main() -> int:
    parser = argparse.ArgumentParser(description="Retrieval eval: Recall@k and MRR, no LLM.")
    parser.add_argument("--configs", help="comma-separated, e.g. bm25,hybrid:bge_m3 (default: all)")
    parser.add_argument("--corpora", help="comma-separated: core,full (default: all available)")
    parser.add_argument("--label", default="", help="report name suffix, e.g. rerank")
    args = parser.parse_args()

    cfg = load_retrieval_config().retrieval
    chunks, chunks_sha = load_chunks()
    questions = [q for q in load_gold() if q.category == "in_scope"]
    chunks_by_id = {c.chunk_id: c for c in chunks}
    language_of = {c.doc_id: c.language for c in chunks}
    available = {"core": [c for c in chunks if c.role == "core"]}
    if any(c.role == "distractor" for c in chunks):
        available["full"] = chunks
    corpora = select(available, args.corpora, "corpora")
    configs = list(select({c.name: c for c in run_configs(cfg)}, args.configs, "configs").values())
    embedders = list(dict.fromkeys(c.embedder for c in configs if c.embedder))
    timings: dict[str, list[float]] = defaultdict(list)
    dense: dict[
        tuple[str, str, str], list[str]
    ] = {}  # (corpus, embedder, question id) -> chunk ids

    with connect(Settings().database_dsn()) as conn:
        try:
            for key in embedders:
                assert_fresh(conn, key, chunks_sha)
        except StaleIndexError as exc:
            print(exc)
            return 1
        for key in embedders:  # one model in memory at a time
            embedder = load_embedder(cfg, key)
            for q in questions:
                start = time.perf_counter()
                (vector,) = embedder.embed_queries([q.question])
                timings[f"embed query ({key})"].append(ms_since(start))
                for name in corpora:
                    start = time.perf_counter()
                    dense[(name, key, q.id)] = dense_search(
                        conn, key, vector, cfg.candidates, CORPUS_ROLES[name]
                    )
                    timings["dense search (pgvector)"].append(ms_since(start))
            release_models()

    rerank = load_reranker(cfg) if any(c.mode == "hybrid_rerank" for c in configs) else None
    run_start = time.perf_counter()
    rows: list[dict[str, Any]] = []
    for corpus_name, corpus_chunks in corpora.items():
        corpus = Corpus.build(corpus_chunks, cfg)
        for i, q in enumerate(questions, start=1):
            start = time.perf_counter()
            bm25_ids = corpus.bm25_search(q.question, cfg.candidates)
            timings["bm25"].append(ms_since(start))
            for c in configs:
                dense_ids = dense[(corpus_name, c.embedder, q.id)] if c.embedder else []
                start = time.perf_counter()
                ranking = rank(c.mode, q.question, bm25_ids, dense_ids, corpus, cfg, rerank)
                if c.mode == "hybrid_rerank":
                    timings[f"fuse + rerank {cfg.rerank_candidates}"].append(ms_since(start))
                rows.append(
                    score_row(q, corpus_name, c.name, ranking, chunks_by_id, language_of, cfg.top_k)
                )
            elapsed = (time.perf_counter() - run_start) / 60
            print(f"{corpus_name}: {i}/{len(questions)} questions, {elapsed:.1f} min", flush=True)
    release_models()

    report = {
        "created_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "label": args.label,
        "retrieval_config": cfg.model_dump(),
        "configs": [{"name": c.name, "mode": c.mode, "embedder": c.embedder} for c in configs],
        "chunks_sha256": chunks_sha,
        "corpora": {
            name: {"docs": len({c.doc_id for c in cs}), "chunks": len(cs)}
            for name, cs in corpora.items()
        },
        "gold": {
            "sha256": hashlib.sha256(GOLD_PATH.read_bytes()).hexdigest(),
            "n_questions": len(questions),
        },
        "summary": summarize(rows),
        "paired": paired_differences(rows, comparison_pairs(configs)),
        "latency": latency_summary(timings),
        "results": rows,
    }
    table = write_report(report, REPORTS_DIR)
    print(table.read_text(encoding="utf-8"))
    return 0


def write_report(report: dict[str, Any], out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    label = f"_{report['label']}" if report.get("label") else ""
    prefix = out_dir / f"{report['created_at'][:10]}_retrieval{label}"
    prefix.with_suffix(".json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    table = prefix.with_suffix(".md")
    table.write_text(markdown(report), encoding="utf-8")
    return table


if __name__ == "__main__":
    sys.exit(main())
