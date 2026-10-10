"""Baselines B0/B1/B2 (spec 8.3) scored by the LLM judge.

Usage: uv run tasks.py eval-full | eval-smoke  [--systems B0,B1]
"""

from __future__ import annotations

import argparse
import asyncio
import dataclasses
import json
import re
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import openai

from chaouch.config import (
    ROOT,
    ConfigError,
    ModelsConfig,
    Settings,
    load_models_config,
    load_retrieval_config,
)
from chaouch.ingestion.tokens import TokenCounter, hf_token_counter
from chaouch.llm import LLMClient, QuotaExhausted, SQLiteCache
from evals.config import EvalConfig, SystemConfig, load_eval_config
from evals.gold import GoldQuestion, load_gold
from evals.judge.judge import Judge, JudgeError
from evals.metrics.aggregate import aggregate, breakdown
from evals.prompts import Prompt, load_prompt

PROMPTS_DIR = Path(__file__).parent / "prompts"
PROCESSED_DIR = ROOT / "data" / "documents" / "processed"
REPORTS_DIR = ROOT / "reports"


@dataclass(frozen=True)
class OracleDoc:
    doc_id: str
    title: str
    source_url: str
    retrieved_at: str
    markdown: str


@dataclass
class QuestionResult:
    id: str
    system: str
    script: str
    category: str
    difficulty: str
    answer: str | None = None
    latency_ms: float | None = None
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    oracle_tokens: int | None = None
    oracle_truncated: bool | None = None
    correctness: float | None = None
    fact_verdicts: list[str] | None = None
    faithfulness: float | None = None
    dialect_score: int | None = None
    dialect_label: str | None = None
    error: str | None = None


def load_docs(doc_ids: set[str], processed_dir: Path) -> dict[str, OracleDoc]:
    missing = sorted(d for d in doc_ids if not (processed_dir / f"{d}.md").exists())
    if missing:
        raise ConfigError(f"cleaned documents missing (run ingest): {', '.join(missing)}")
    docs = {}
    for doc_id in doc_ids:
        meta = json.loads((processed_dir / f"{doc_id}.json").read_text(encoding="utf-8"))
        docs[doc_id] = OracleDoc(
            doc_id=doc_id,
            title=meta["title"],
            source_url=meta["source_url"],
            retrieved_at=meta["retrieved_at"],
            markdown=(processed_dir / f"{doc_id}.md").read_text(encoding="utf-8"),
        )
    return docs


def build_oracle(docs: list[OracleDoc], budget: int, count: TokenCounter) -> tuple[str, int, bool]:
    parts: list[str] = []
    used = 0
    for doc in docs:
        header = f"### {doc.title}\nSource: {doc.source_url} (retrieved {doc.retrieved_at})"
        for block in [header, *re.split(r"\n\s*\n", doc.markdown.strip())]:
            n = count(block)
            if used + n > budget:
                return "\n\n".join(parts), used, True
            parts.append(block)
            used += n
    return "\n\n".join(parts), used, False


def model_family(name: str) -> str:
    match = re.match(r"[a-z]+", name.rsplit("/", 1)[-1].lower())
    return match.group(0) if match else name


def is_self_judged(models: ModelsConfig, system_model: str, judge_model: str) -> bool:
    a, b = models.models[system_model], models.models[judge_model]
    return model_family(a.name) == model_family(b.name)


@dataclass(frozen=True)
class Run:
    llm: LLMClient
    judge: Judge
    prompts: dict[str, Prompt]
    docs: dict[str, OracleDoc]
    budget: int
    count: TokenCounter
    cache: SQLiteCache | None


async def evaluate(
    run: Run, q: GoldQuestion, system_id: str, system: SystemConfig
) -> QuestionResult:
    result = QuestionResult(q.id, system_id, q.script, q.category, q.difficulty)
    try:
        context = None
        if system.use_oracle:
            gold_docs = [run.docs[d] for d in q.gold_doc_ids]
            context, result.oracle_tokens, result.oracle_truncated = build_oracle(
                gold_docs, run.budget, run.count
            )
            prompt = run.prompts["oracle"].render(documents=context, question=q.question)
        else:
            prompt = run.prompts["closed"].render(question=q.question)

        answer = await run.llm.complete(
            [{"role": "user", "content": prompt}], system.model, cache=run.cache
        )
        result.answer = answer.text
        result.latency_ms = answer.latency_ms
        result.prompt_tokens = answer.prompt_tokens
        result.completion_tokens = answer.completion_tokens

        correctness = run.judge.correctness(
            q.question, q.expected_answer, q.required_facts, answer.text
        )
        dialect = run.judge.dialect(answer.text)
        (
            (result.correctness, verdicts),
            (result.dialect_score, result.dialect_label),
        ) = await asyncio.gather(correctness, dialect)
        result.fact_verdicts = list(verdicts)
        if context is not None:
            result.faithfulness = await run.judge.faithfulness(context, answer.text)
    except QuotaExhausted as exc:
        result.error = f"quota: {exc}"
    except (JudgeError, openai.APIError) as exc:
        result.error = f"{type(exc).__name__}: {exc}"
    return result


def system_report(
    system_id: str,
    results: list[QuestionResult],
    *,
    cfg: EvalConfig,
    models: ModelsConfig,
    suite: str,
    prompt_versions: list[str],
    not_scored: int,
) -> dict[str, Any]:
    system = cfg.systems[system_id]
    rows = [dataclasses.asdict(r) for r in results]
    return {
        "system": system_id,
        "suite": suite,
        "created_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "model": models.models[system.model].model_dump(),
        "use_oracle": system.use_oracle,
        "judge": models.models[cfg.judge_model].model_dump(),
        "self_judged": is_self_judged(models, system.model, cfg.judge_model),
        "prompt_versions": prompt_versions,
        "incomplete": any((r.error or "").startswith("quota") for r in results),
        "not_scored_in_phase0": not_scored,  # out_of_scope / adversarial: refusal metrics in P3
        "metrics": aggregate(rows),
        "breakdowns": {f: breakdown(rows, f) for f in ("script", "category", "difficulty")},
        "results": rows,
    }


def fmt(value: Any, digits: int = 2) -> str:
    if value is None:
        return "–"
    return f"{value:.{digits}f}" if isinstance(value, float) else str(value)


def markdown_table(reports: list[dict[str, Any]]) -> str:
    lines = [
        "| System | Model | n | Correctness | Faithfulness | Dialect (1–5) "
        "| p50 ms | p95 ms | Oracle truncated | Errors |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for r in reports:
        m = r["metrics"]
        lines.append(
            f"| {r['system']} | {r['model']['name']} | {m['n']} | {fmt(m['correctness'])} "
            f"| {fmt(m['faithfulness'])} | {fmt(m['dialect'])} | {fmt(m['latency_p50_ms'], 0)} "
            f"| {fmt(m['latency_p95_ms'], 0)} | {fmt(m['oracle_truncation_rate'])} "
            f"| {m['n_errors']} |"
        )
    lines += [
        "",
        "By script (correctness / dialect):",
        "",
        "| System | Script | n | Correctness | Dialect |",
    ]
    lines.append("|---|---|---|---|---|")
    for r in reports:
        for script, m in r["breakdowns"]["script"].items():
            lines.append(
                f"| {r['system']} | {script} | {m['n']} | {fmt(m['correctness'])} "
                f"| {fmt(m['dialect'])} |"
            )
    judge = reports[0]["judge"]
    lines += [
        "",
        f"Judge: {judge['name']} ({judge['provider']}). Prompts: "
        f"{', '.join(reports[0]['prompt_versions'])}.",
    ]
    for r in reports:
        if r["self_judged"]:
            lines.append(f"Warning: {r['system']} is judged by its own model family.")
        if r["incomplete"]:
            lines.append(f"Warning: {r['system']} is incomplete (quota hit); re-run to resume.")
    lines.append(
        f"Out-of-scope / adversarial questions not scored in Phase 0: "
        f"{reports[0]['not_scored_in_phase0']}."
    )
    return "\n".join(lines) + "\n"


async def run_suite(
    run: Run, questions: list[GoldQuestion], system_ids: list[str], cfg: EvalConfig
) -> dict[str, list[QuestionResult]]:
    jobs = [(sid, q) for sid in system_ids for q in questions]
    results = await asyncio.gather(*(evaluate(run, q, sid, cfg.systems[sid]) for sid, q in jobs))
    by_system: dict[str, list[QuestionResult]] = {sid: [] for sid in system_ids}
    for result in results:
        by_system[result.system].append(result)
    return by_system


def write_reports(reports: list[dict[str, Any]], suite: str, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    date = datetime.now(UTC).date().isoformat()
    prefix = date if suite == "full" else f"{date}_smoke"
    for report in reports:
        path = out_dir / f"{prefix}_{report['system']}.json"
        path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    table = out_dir / f"{prefix}_baseline.md"
    table.write_text(markdown_table(reports), encoding="utf-8")
    return table


def select_questions(
    questions: list[GoldQuestion], suite: str, cfg: EvalConfig
) -> list[GoldQuestion]:
    in_scope = [q for q in questions if q.category == "in_scope"]
    if suite == "smoke":
        return sorted(in_scope, key=lambda q: q.id)[: cfg.smoke_size]
    return in_scope


def main() -> int:
    parser = argparse.ArgumentParser(description="Run baseline evals.")
    parser.add_argument("--suite", choices=["full", "smoke"], default="full")
    parser.add_argument("--systems", help="comma-separated, e.g. B0,B1 (default: per suite)")
    args = parser.parse_args()

    cfg = load_eval_config()
    models = load_models_config()
    default = cfg.smoke_systems if args.suite == "smoke" else list(cfg.systems)
    system_ids = args.systems.split(",") if args.systems else default
    unknown = [s for s in system_ids if s not in cfg.systems]
    if unknown:
        raise ConfigError(f"unknown systems: {', '.join(unknown)}")
    for key in [cfg.judge_model, *(cfg.systems[s].model for s in system_ids)]:
        if key not in models.models:
            raise ConfigError(f"model key {key!r} not in configs/models.yaml")

    questions = load_gold()
    selected = select_questions(questions, args.suite, cfg)
    if not selected:
        print("No in-scope gold questions yet ([HUMAN] task: data/evals/gold/questions.jsonl).")
        return 0

    needs_docs = any(cfg.systems[s].use_oracle for s in system_ids)
    docs = (
        load_docs({d for q in selected for d in q.gold_doc_ids}, PROCESSED_DIR)
        if needs_docs
        else {}
    )
    cache = SQLiteCache(cfg.cache_path)
    llm = LLMClient(models, Settings())
    run = Run(
        llm=llm,
        judge=Judge(llm, cfg.judge_model, cache),
        prompts={
            "closed": load_prompt(PROMPTS_DIR / "answer_closed_v1.md"),
            "oracle": load_prompt(PROMPTS_DIR / "answer_oracle_v1.md"),
        },
        docs=docs,
        budget=cfg.oracle_token_budget,
        count=hf_token_counter(load_retrieval_config().chunking.tokenizer),
        cache=cache,
    )
    by_system = asyncio.run(run_suite(run, selected, system_ids, cfg))
    prompt_versions = [p.version for p in run.prompts.values()] + run.judge.prompt_versions
    reports = [
        system_report(
            sid,
            results,
            cfg=cfg,
            models=models,
            suite=args.suite,
            prompt_versions=prompt_versions,
            not_scored=len(questions) - len([q for q in questions if q.category == "in_scope"]),
        )
        for sid, results in by_system.items()
    ]
    table = write_reports(reports, args.suite, REPORTS_DIR)
    print(table.read_text(encoding="utf-8"))
    errors = sum(r["metrics"]["n_errors"] for r in reports)
    if errors:
        print(f"{errors} questions had errors; see the JSON reports.")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
