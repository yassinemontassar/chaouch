import pytest

from evals.judge.judge import (
    CorrectnessOut,
    DialectOut,
    FaithfulnessOut,
    JudgeError,
    correctness_score,
    faithfulness_score,
    parse_json,
)
from evals.metrics.aggregate import percentile
from evals.prompts import Prompt


def test_parse_json_strips_code_fence() -> None:
    out = parse_json('```json\n{"score": 3, "label": "mixed"}\n```', DialectOut)
    assert (out.score, out.label) == (3, "mixed")


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
    score, order = correctness_score(
        verdicts((2, "absent"), (1, "present"), (3, "contradicted")), 3
    )
    assert score == pytest.approx(1 / 3)
    assert order == ["present", "absent", "contradicted"]


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
