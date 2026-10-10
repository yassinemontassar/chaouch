"""Gold evaluation set: schema (spec 7.2), loader and validator.

The questions themselves are written by the owner, never generated.
Usage: uv run tasks.py validate-evals [--gold PATH] [--sources PATH]
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from chaouch.config import ROOT, ConfigError
from chaouch.ingestion.sources import SOURCES_PATH, Source, load_sources
from evals.config import GoldChecks, load_eval_config

GOLD_PATH = ROOT / "data" / "evals" / "gold" / "questions.jsonl"

Script = Literal["arabic", "arabizi", "mixed_fr"]
Category = Literal["in_scope", "out_of_scope", "adversarial"]
Difficulty = Literal["easy", "medium", "hard"]


class GoldQuestion(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str = Field(min_length=1)
    procedure: str | None
    question: str = Field(min_length=1)
    script: Script
    code_switching: bool
    category: Category
    difficulty: Difficulty
    expected_answer: str = Field(min_length=1)
    required_facts: list[str]
    gold_doc_ids: list[str]
    notes: str = ""

    @model_validator(mode="after")
    def _in_scope_is_answerable(self) -> GoldQuestion:
        if self.category == "in_scope":
            missing = [
                name
                for name, value in [
                    ("procedure", self.procedure),
                    ("required_facts", self.required_facts),
                    ("gold_doc_ids", self.gold_doc_ids),
                ]
                if not value
            ]
            if missing:
                raise ValueError(f"in_scope question needs non-empty {', '.join(missing)}")
        return self


@dataclass
class GoldReport:
    questions: list[GoldQuestion] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def load_gold(path: Path = GOLD_PATH) -> list[GoldQuestion]:
    report = parse_gold(path)
    if report.errors:
        raise ConfigError(f"invalid gold set {path}:\n" + "\n".join(report.errors))
    return report.questions


def parse_gold(path: Path) -> GoldReport:
    report = GoldReport()
    seen: set[str] = set()
    for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            question = GoldQuestion.model_validate(json.loads(line))
        except json.JSONDecodeError as exc:
            report.errors.append(f"line {lineno}: invalid JSON ({exc.msg})")
            continue
        except ValidationError as exc:
            for err in exc.errors():
                where = ".".join(str(p) for p in err["loc"]) or "record"
                report.errors.append(f"line {lineno}: {where}: {err['msg']}")
            continue
        if question.id in seen:
            report.errors.append(f"line {lineno}: duplicate id {question.id!r}")
            continue
        seen.add(question.id)
        report.questions.append(question)
    return report


def validate_gold(path: Path, sources: list[Source], checks: GoldChecks) -> GoldReport:
    report = parse_gold(path)
    doc_ids = {s.doc_id for s in sources}
    procedures = {s.procedure for s in sources}
    for q in report.questions:
        unknown = [d for d in q.gold_doc_ids if d not in doc_ids]
        if unknown:
            report.errors.append(f"{q.id}: gold_doc_ids not in sources.yaml: {', '.join(unknown)}")
        if q.category == "in_scope" and q.procedure not in procedures:
            report.errors.append(f"{q.id}: procedure {q.procedure!r} has no source in sources.yaml")
    report.warnings.extend(distribution_warnings(report.questions, checks))
    return report


def distribution_warnings(questions: list[GoldQuestion], checks: GoldChecks) -> list[str]:
    n = len(questions)
    warnings = []
    if n < checks.min_questions:
        warnings.append(f"{n} questions; the Phase 0 target is {checks.min_questions}")
    if n == 0:
        return warnings
    scripts = Counter(q.script for q in questions)
    for script in ("arabic", "arabizi", "mixed_fr"):
        share = scripts[script] / n
        if not checks.script_share_min <= share <= checks.script_share_max:
            warnings.append(f"script {script!r} is {share:.0%} of questions (aim for about 1/3)")
    not_in_scope = sum(q.category != "in_scope" for q in questions) / n
    if not checks.not_in_scope_share_min <= not_in_scope <= checks.not_in_scope_share_max:
        warnings.append(f"out_of_scope + adversarial is {not_in_scope:.0%} (aim for about 15%)")
    return warnings


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate the gold evaluation set.")
    parser.add_argument("--gold", type=Path, default=GOLD_PATH)
    parser.add_argument("--sources", type=Path, default=SOURCES_PATH)
    args = parser.parse_args()

    report = validate_gold(args.gold, load_sources(args.sources), load_eval_config().gold)
    for warning in report.warnings:
        print(f"WARNING: {warning}")
    for error in report.errors:
        print(f"ERROR: {error}")
    counts = Counter(q.script for q in report.questions)
    summary = ", ".join(f"{k}={v}" for k, v in sorted(counts.items())) or "none"
    print(f"{len(report.questions)} valid questions ({summary}), {len(report.errors)} errors")
    return 1 if report.errors else 0


if __name__ == "__main__":
    sys.exit(main())
