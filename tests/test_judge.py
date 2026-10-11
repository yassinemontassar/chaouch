import json
from pathlib import Path
from typing import cast

import pytest

from chaouch.llm import LLMClient
from evals.gold import load_gold
from evals.judge.judge import (
    ECHO_REASON,
    CorrectnessOut,
    DialectOut,
    FaithfulnessOut,
    Judge,
    JudgeError,
    correctness_score,
    faithfulness_score,
    is_echo,
    parse_json,
)
from evals.metrics.aggregate import bootstrap_ci, percentile, trustworthy
from evals.prompts import Prompt


def test_parse_json_strips_code_fence() -> None:
    out = parse_json('```json\n{"score": 3, "label": "mixed"}\n```', DialectOut)
    assert (out.score, out.label) == (3, "mixed")


def test_parse_json_accepts_a_bare_list() -> None:
    text = '<thought>x</thought>[{"claim": "a", "supported": true}]'
    assert parse_json(text, FaithfulnessOut).claims[0].supported
    with pytest.raises(JudgeError):
        parse_json("[5]", DialectOut)  # two fields: no guessing


def test_parse_json_strips_leading_thought() -> None:
    text = '<thought>*  "لازمك": {"score": 1}?\n</thought>{"score": 5, "label": "derja"}'
    assert parse_json(text, DialectOut).score == 5


@pytest.mark.parametrize(
    "text",
    ["not json", '{"score": 6, "label": "derja"}', '{"score": 3, "label": "english"}', "{}"],
)
def test_parse_json_rejects_bad_output(text: str) -> None:
    with pytest.raises(JudgeError):
        parse_json(text, DialectOut)


def verdicts(*items: tuple[int, str]) -> CorrectnessOut:
    return CorrectnessOut.model_validate({"facts": [{"index": i, "verdict": v} for i, v in items]})


def test_correctness_score() -> None:
    score, order, reasons = correctness_score(
        verdicts((2, "absent"), (1, "present"), (3, "contradicted")), 3
    )
    assert score == pytest.approx(1 / 3)
    assert order == ["present", "absent", "contradicted"]
    assert reasons == ["", "", ""]  # v1 replies have no reason


def test_reasons_follow_fact_order() -> None:
    out = CorrectnessOut.model_validate(
        {"facts": [{"index": 2, "verdict": "absent", "reason": "no price"},
                   {"index": 1, "verdict": "present", "reason": "says 4 photos"}]}
    )  # fmt: skip
    assert correctness_score(out, 2)[2] == ["says 4 photos", "no price"]


@pytest.mark.parametrize(
    "out",
    [
        verdicts((1, "present")),  # missing fact 2
        verdicts((1, "present"), (2, "present"), (3, "present")),  # extra fact
        verdicts((1, "present"), (1, "absent")),  # duplicate index
    ],
)
def test_correctness_score_rejects_wrong_indices(out: CorrectnessOut) -> None:
    with pytest.raises(JudgeError):
        correctness_score(out, 2)


def test_faithfulness_score() -> None:
    claims = [{"claim": "a", "supported": True}, {"claim": "b", "supported": False}]
    assert faithfulness_score(FaithfulnessOut.model_validate({"claims": claims})) == 0.5
    assert faithfulness_score(FaithfulnessOut(claims=[])) is None


def test_prompt_render() -> None:
    prompt = Prompt("p_v1", "Q: {{question}} D: {{documents}}")
    assert prompt.render(question="x", documents="{{question}}") == "Q: x D: {{question}}"
    with pytest.raises(ValueError, match="needs"):
        prompt.render(question="x")


@pytest.mark.parametrize(
    ("values", "p", "expected"),
    [([], 50, None), ([5.0], 95, 5.0), ([1, 2, 3, 4], 50, 2), ([1, 2, 3, 4], 95, 4)],
)
def test_percentile(values: list[float], p: float, expected: float | None) -> None:
    assert percentile(values, p) == expected


CASES = json.loads((Path(__file__).parent / "fixtures" / "echoes.json").read_text(encoding="utf-8"))
ECHOES = [(c["question"], c["answer"]) for c in CASES["echoes"]]
SHORT_ANSWERS = [(c["question"], c["answer"]) for c in CASES["short_answers"]]


@pytest.mark.parametrize(("question", "answer"), ECHOES)
def test_echoes_are_flagged(question: str, answer: str) -> None:
    assert is_echo(question, answer)


@pytest.mark.parametrize(("question", "answer"), SHORT_ANSWERS)
def test_short_answers_that_reuse_the_question_are_not_echoes(question: str, answer: str) -> None:
    assert not is_echo(question, answer)  # "ليست ضرورية" answers a yes/no question


def test_no_gold_answer_is_an_echo() -> None:
    questions = load_gold()
    assert len(questions) == 51
    assert [q.id for q in questions if is_echo(q.question, q.expected_answer)] == []


async def test_echo_is_scored_without_judge_calls() -> None:
    judge = Judge(cast(LLMClient, None), "unused", None)  # any call would fail
    question, answer = ECHOES[0]
    assert await judge.correctness(question, "ref", ["a", "b"], answer) == (
        0.0, ["absent", "absent"], [ECHO_REASON, ECHO_REASON],
    )  # fmt: skip
    assert await judge.dialect(question, answer) == (1, "echo")


def row(correctness: float | None, faithfulness: float | None = None) -> dict[str, object]:
    return {"correctness": correctness, "faithfulness": faithfulness}


def test_trustworthy_needs_all_facts_and_faithfulness() -> None:
    assert trustworthy(row(1.0, 0.9)) == 1.0
    assert trustworthy(row(1.0, 0.8)) == 0.0
    assert trustworthy(row(0.5, 1.0)) == 0.0
    assert trustworthy(row(1.0, None)) == 0.0  # missing faithfulness is not trusted


def test_bootstrap_ci() -> None:
    def metric(r: dict[str, object]) -> float | None:
        return r["correctness"]  # type: ignore[return-value]

    rows = [row(float(i % 2)) for i in range(40)]
    low, high = bootstrap_ci(rows, metric) or [0, 0]
    assert 0.3 < low < 0.5 < high < 0.7
    assert bootstrap_ci(rows, metric) == [low, high]  # fixed seed
    assert bootstrap_ci([row(1.0)] * 5, metric) == [1.0, 1.0]
    assert bootstrap_ci([row(None)] * 5, metric) is None
