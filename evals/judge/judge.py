from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, ValidationError

from chaouch.llm import LLMClient, SQLiteCache
from evals.prompts import load_prompt

PROMPTS_DIR = Path(__file__).parent / "prompts"
# correctness and dialect v2: ADR 0009
PROMPTS = {
    "correctness": "correctness_v2",
    "faithfulness": "faithfulness_v1",
    "dialect": "dialect_v2",
}
FENCE = re.compile(r"^```(?:json)?\s*|\s*```$")
# Gemma 4 always thinks and prints it before the JSON; it cannot be turned off (ADR 0010).
THOUGHT = re.compile(r"^\s*<(thought|think)>.*?</\1>", re.DOTALL)

Verdict = Literal["present", "absent", "contradicted"]
DialectLabel = Literal["derja", "msa", "french", "mixed", "other"]


class JudgeError(Exception):
    pass


ECHO_REASON = "echo of the question"


def normalize(text: str) -> str:
    """Lowercase, no diacritics or hamza marks, words separated by single spaces."""
    text = unicodedata.normalize("NFD", unicodedata.normalize("NFKC", text).lower())
    text = "".join(c for c in text if not unicodedata.combining(c))
    return re.sub(r"[\W_]+", " ", text).strip()


def trigrams(text: str) -> set[str]:
    text = normalize(text)
    return {text[i : i + 3] for i in range(len(text) - 2)}


# Adding one of these to a yes/no question answers it ("ليست ضرورية"), it is not an echo.
ANSWER_WORDS = {
    normalize(w)
    for w in (
        *("لا", "لاء", "ليس", "ليست", "نعم", "إيه", "إي"),
        *("ey", "eyh", "le", "lé", "non", "oui", "mouch", "mech"),
    )
}


def is_echo(question: str, answer: str) -> bool:
    """The answer mostly repeats the question and adds little (ADR 0009).

    Echo: it covers >= 70% of the question's character 3-grams, >= 38% of its own 3-grams come
    from the question, it adds < 50 new 3-grams, and it adds no yes/no word.
    """
    q, a = trigrams(question), trigrams(answer)
    if not q or not a:
        return False
    if len(q & a) / len(q) < 0.7 or len(a & q) / len(a) < 0.38 or len(a - q) >= 50:
        return False
    added = set(normalize(answer).split()) - set(normalize(question).split())
    return not added & ANSWER_WORDS


class FactVerdict(BaseModel):
    index: int
    verdict: Verdict
    reason: str = ""  # one line, asked for since correctness_v2


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
        return model.model_validate(json.loads(FENCE.sub("", THOUGHT.sub("", text).strip())))
    except (json.JSONDecodeError, ValidationError) as exc:
        raise JudgeError(f"bad {model.__name__}: {text[:200]!r}") from exc


def correctness_score(out: CorrectnessOut, n_facts: int) -> tuple[float, list[Verdict], list[str]]:
    by_index = {f.index: f for f in out.facts}
    if sorted(by_index) != list(range(1, n_facts + 1)) or len(out.facts) != n_facts:
        raise JudgeError(f"expected verdicts for facts 1..{n_facts}, got {sorted(by_index)}")
    facts = [by_index[i] for i in range(1, n_facts + 1)]
    verdicts = [f.verdict for f in facts]
    return verdicts.count("present") / n_facts, verdicts, [f.reason for f in facts]


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
            name: load_prompt(PROMPTS_DIR / f"{file}.md") for name, file in PROMPTS.items()
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
    ) -> tuple[float, list[Verdict], list[str]]:
        if is_echo(question, answer):  # scored without a judge call
            return 0.0, ["absent"] * len(facts), [ECHO_REASON] * len(facts)
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

    async def dialect(
        self, question: str, answer: str
    ) -> tuple[int, DialectLabel | Literal["echo"]]:
        if is_echo(question, answer):
            return 1, "echo"
        out = await self._ask("dialect", DialectOut, question=question, answer=answer)
        return out.score, out.label
