"""LLM-as-judge: correctness, faithfulness and dialect, one JSON call per metric."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, ValidationError

from chaouch.llm import LLMClient, SQLiteCache
from evals.prompts import load_prompt

PROMPTS_DIR = Path(__file__).parent / "prompts"
FENCE = re.compile(r"^```(?:json)?\s*|\s*```$")

Verdict = Literal["present", "absent", "contradicted"]
DialectLabel = Literal["derja", "msa", "french", "mixed", "other"]


class JudgeError(Exception):
    pass


class FactVerdict(BaseModel):
    index: int
    verdict: Verdict


class CorrectnessOut(BaseModel):
    facts: list[FactVerdict]


class Claim(BaseModel):
    claim: str
    supported: bool


class FaithfulnessOut(BaseModel):
    claims: list[Claim]


class DialectOut(BaseModel):
    score: int = Field(ge=1, le=5)
    label: DialectLabel


def parse_json[T: BaseModel](text: str, model: type[T]) -> T:
    try:
        return model.model_validate(json.loads(FENCE.sub("", text.strip())))
    except (json.JSONDecodeError, ValidationError) as exc:
        raise JudgeError(f"bad {model.__name__}: {text[:200]!r}") from exc


def correctness_score(out: CorrectnessOut, n_facts: int) -> tuple[float, list[Verdict]]:
    by_index = {f.index: f.verdict for f in out.facts}
    if sorted(by_index) != list(range(1, n_facts + 1)) or len(out.facts) != n_facts:
        raise JudgeError(f"expected verdicts for facts 1..{n_facts}, got {sorted(by_index)}")
    verdicts = [by_index[i] for i in range(1, n_facts + 1)]
    return verdicts.count("present") / n_facts, verdicts


def faithfulness_score(out: FaithfulnessOut) -> float | None:
    """Share of supported claims; None when the answer makes no factual claim."""
    if not out.claims:
        return None
    return sum(c.supported for c in out.claims) / len(out.claims)


class Judge:
    def __init__(self, llm: LLMClient, model_key: str, cache: SQLiteCache | None) -> None:
        self._llm = llm
        self._model_key = model_key
        self._cache = cache
        self._prompts = {
            name: load_prompt(PROMPTS_DIR / f"{name}_v1.md")
            for name in ("correctness", "faithfulness", "dialect")
        }

    @property
    def prompt_versions(self) -> list[str]:
        return [p.version for p in self._prompts.values()]

    async def _ask[T: BaseModel](self, name: str, model: type[T], **values: str) -> T:
        content = self._prompts[name].render(**values)
        completion = await self._llm.complete(
            [{"role": "user", "content": content}],
            self._model_key,
            json_mode=True,
            cache=self._cache,
        )
        return parse_json(completion.text, model)

    async def correctness(
        self, question: str, reference: str, facts: list[str], answer: str
    ) -> tuple[float, list[Verdict]]:
        numbered = "\n".join(f"{i}. {fact}" for i, fact in enumerate(facts, start=1))
        out = await self._ask(
            "correctness",
            CorrectnessOut,
            question=question,
            reference=reference,
            facts=numbered,
            answer=answer,
        )
        return correctness_score(out, len(facts))

    async def faithfulness(self, documents: str, answer: str) -> float | None:
        out = await self._ask("faithfulness", FaithfulnessOut, documents=documents, answer=answer)
        return faithfulness_score(out)

    async def dialect(self, answer: str) -> tuple[int, DialectLabel]:
        out = await self._ask("dialect", DialectOut, answer=answer)
        return out.score, out.label
