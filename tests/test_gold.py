import json
import subprocess
import sys
from pathlib import Path

import pytest

from chaouch.config import ROOT, ConfigError
from chaouch.ingestion.sources import load_sources
from evals.config import GoldChecks, load_eval_config
from evals.gold import load_gold, parse_gold, validate_gold

FIXTURES = Path(__file__).parent / "fixtures"
SOURCES = load_sources(FIXTURES / "sources.yaml")
VALID_LINES = [
    json.loads(line)
    for line in (FIXTURES / "gold_valid.jsonl").read_text(encoding="utf-8").splitlines()
    if line.strip()
]
NO_WARNINGS = GoldChecks(
    min_questions=0,
    script_share_min=0,
    script_share_max=1,
    not_in_scope_share_min=0,
    not_in_scope_share_max=1,
)


def write_gold(tmp_path: Path, records: list[dict[str, object]]) -> Path:
    path = tmp_path / "questions.jsonl"
    path.write_text("\n".join(json.dumps(r) for r in records), encoding="utf-8")
    return path


def with_changes(index: int, **changes: object) -> list[dict[str, object]]:
    records = [dict(r) for r in VALID_LINES]
    records[index].update(changes)
    return records


def test_valid_fixture_has_no_errors() -> None:
    report = validate_gold(FIXTURES / "gold_valid.jsonl", SOURCES, NO_WARNINGS)
    assert report.errors == []
    assert [q.id for q in report.questions] == ["t-001", "t-002", "t-003"]


def test_load_gold_returns_questions() -> None:
    questions = load_gold(FIXTURES / "gold_valid.jsonl")
    assert questions[1].required_facts == ["FACT B1", "FACT B2"]


@pytest.mark.parametrize(
    ("changes", "expected"),
    [
        ({"script": "latin"}, "script"),
        ({"category": "maybe"}, "category"),
        ({"difficulty": "extreme"}, "difficulty"),
        ({"question": ""}, "question"),
        ({"surprise": 1}, "surprise"),
        ({"required_facts": []}, "required_facts"),
        ({"gold_doc_ids": []}, "gold_doc_ids"),
        ({"procedure": None}, "procedure"),
    ],
)
def test_schema_errors_report_line(
    tmp_path: Path, changes: dict[str, object], expected: str
) -> None:
    path = write_gold(tmp_path, with_changes(0, **changes))
    report = parse_gold(path)
    assert len(report.errors) >= 1
    assert report.errors[0].startswith("line 1:")
    assert expected in report.errors[0]
    assert len(report.questions) == 2


def test_out_of_scope_may_have_no_facts() -> None:
    report = parse_gold(FIXTURES / "gold_valid.jsonl")
    assert report.questions[2].category == "out_of_scope"
    assert report.errors == []


def test_invalid_json_line(tmp_path: Path) -> None:
    path = tmp_path / "questions.jsonl"
    path.write_text(json.dumps(VALID_LINES[0]) + "\n{not json\n", encoding="utf-8")
    report = parse_gold(path)
    assert report.errors == [
        "line 2: invalid JSON (Expecting property name enclosed in double quotes)"
    ]


def test_duplicate_id(tmp_path: Path) -> None:
    path = write_gold(tmp_path, with_changes(1, id="t-001"))
    assert parse_gold(path).errors == ["line 2: duplicate id 't-001'"]


def test_unknown_doc_id(tmp_path: Path) -> None:
    path = write_gold(tmp_path, with_changes(0, gold_doc_ids=["nope_01"]))
    report = validate_gold(path, SOURCES, NO_WARNINGS)
    assert report.errors == ["t-001: gold_doc_ids not in sources.yaml: nope_01"]


def test_in_scope_procedure_without_source(tmp_path: Path) -> None:
    path = write_gold(tmp_path, with_changes(0, procedure="proc_z"))
    report = validate_gold(path, SOURCES, NO_WARNINGS)
    assert report.errors == ["t-001: procedure 'proc_z' has no source in sources.yaml"]


def test_load_gold_raises_on_errors(tmp_path: Path) -> None:
    path = write_gold(tmp_path, with_changes(0, script="latin"))
    with pytest.raises(ConfigError, match="line 1"):
        load_gold(path)


def test_distribution_warnings(tmp_path: Path) -> None:
    checks = load_eval_config().gold
    # 3 in-scope arabic + 0 others: too few, script skewed, no out-of-scope.
    records = [dict(VALID_LINES[0], id=f"t-{i}") for i in range(3)]
    report = validate_gold(write_gold(tmp_path, records), SOURCES, checks)
    assert report.errors == []
    text = "\n".join(report.warnings)
    assert "3 questions; the Phase 0 target is 50" in text
    assert "'arabic' is 100%" in text
    assert "'arabizi' is 0%" in text
    assert "out_of_scope + adversarial is 0%" in text


def test_empty_file_only_warns(tmp_path: Path) -> None:
    path = tmp_path / "questions.jsonl"
    path.write_text("", encoding="utf-8")
    report = validate_gold(path, SOURCES, load_eval_config().gold)
    assert report.errors == []
    assert report.warnings == ["0 questions; the Phase 0 target is 50"]


@pytest.mark.parametrize(("fixture", "code"), [("gold_valid.jsonl", 0), ("bad", 1)])
def test_cli_exit_code(tmp_path: Path, fixture: str, code: int) -> None:
    gold = FIXTURES / fixture
    if fixture == "bad":
        gold = write_gold(tmp_path, with_changes(0, gold_doc_ids=["nope_01"]))
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "evals.gold",
            "--gold",
            str(gold),
            "--sources",
            str(FIXTURES / "sources.yaml"),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert result.returncode == code, result.stdout + result.stderr
