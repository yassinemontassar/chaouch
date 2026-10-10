import json
from pathlib import Path

import httpx2
import pytest

from chaouch.config import ModelsConfig, Settings, load_models_config
from chaouch.ingestion.tokens import whitespace_token_counter as count
from chaouch.llm import LLMClient, SQLiteCache
from evals.config import load_eval_config
from evals.gold import load_gold
from evals.judge.judge import Judge
from evals.prompts import load_prompt
from evals.runners.baseline import (
    PROMPTS_DIR,
    OracleDoc,
    Run,
    build_oracle,
    is_self_judged,
    load_docs,
    model_family,
    run_suite,
    select_questions,
    system_report,
    write_reports,
)

FIXTURES = Path(__file__).parent / "fixtures"


def provider(base_url: str, max_retries: int = 0) -> dict[str, object]:
    return {
        "base_url": base_url,
        "api_key_env": None,
        "rpm": 6000,
        "rpd": None,
        "timeout_s": 5,
        "max_retries": max_retries,
        "concurrency": 2,
    }


MODELS = ModelsConfig.model_validate(
    {
        "providers": {
            "local": provider("http://local.test/v1"),
            "api": provider("http://api.test/v1"),
            "judge": provider("http://judge.test/v1"),
        },
        "models": {
            "local": {"provider": "local", "name": "qwen3:4b"},
            "gemini_flash": {"provider": "api", "name": "gemini-x"},
            "groq_judge": {"provider": "judge", "name": "openai/gpt-oss-120b"},
        },
    }
)
CFG = load_eval_config().model_copy(update={"judge_model": "groq_judge"})


class FakeServer:
    """Answers chat requests like the real providers would, by prompt type."""

    def __init__(self, failing_hosts: tuple[str, ...] = ()) -> None:
        self.failing_hosts = failing_hosts
        self.requests: list[str] = []

    def __call__(self, request: httpx2.Request) -> httpx2.Response:
        self.requests.append(request.url.host)
        if request.url.host in self.failing_hosts:
            return httpx2.Response(429, json={"error": {"message": "quota"}})
        body = json.loads(request.content)
        content = body["messages"][0]["content"]
        if "REQUIRED FACTS" in content:
            facts = content.split("REQUIRED FACTS:")[1].split("CANDIDATE ANSWER:")[0]
            n = len([line for line in facts.splitlines() if line.strip()])
            text = json.dumps(
                {"facts": [{"index": i, "verdict": "present"} for i in range(1, n + 1)]}
            )
        elif "SOURCE DOCUMENTS" in content:
            claims = [{"claim": "a", "supported": True}, {"claim": "b", "supported": False}]
            text = json.dumps({"claims": claims})
        elif "Rate the DIALECT" in content:
            text = '```json\n{"score": 4, "label": "derja"}\n```'
        else:
            text = "PLACEHOLDER ANSWER"
        return httpx2.Response(
            200,
            json={
                "id": "x",
                "object": "chat.completion",
                "created": 0,
                "model": body["model"],
                "choices": [
                    {
                        "index": 0,
                        "finish_reason": "stop",
                        "message": {"role": "assistant", "content": text},
                    }
                ],
                "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
            },
        )


def write_processed(directory: Path) -> None:
    for doc_id in ("proc_a_01", "proc_b_01"):
        meta = {
            "doc_id": doc_id,
            "title": f"TITLE {doc_id}",
            "source_url": f"https://example.org/{doc_id}",
            "retrieved_at": "2026-10-10T12:00:00+00:00",
        }
        (directory / f"{doc_id}.json").write_text(json.dumps(meta), encoding="utf-8")
        (directory / f"{doc_id}.md").write_text("# H\n\npara one\n\npara two", encoding="utf-8")


def make_run(server: FakeServer, tmp_path: Path, budget: int = 1000) -> Run:
    write_processed(tmp_path)
    cache = SQLiteCache(tmp_path / "cache" / "eval.sqlite")
    llm = LLMClient(
        MODELS,
        Settings(_env_file=None),
        http_client=httpx2.AsyncClient(transport=httpx2.MockTransport(server)),
    )
    return Run(
        llm=llm,
        judge=Judge(llm, "groq_judge", cache),
        prompts={
            "closed": load_prompt(PROMPTS_DIR / "answer_closed_v1.md"),
            "oracle": load_prompt(PROMPTS_DIR / "answer_oracle_v1.md"),
        },
        docs=load_docs({"proc_a_01", "proc_b_01"}, tmp_path),
        budget=budget,
        count=count,
        cache=cache,
    )


def reports_for(by_system, prompt_versions=("v",)):
    return [
        system_report(
            sid,
            results,
            cfg=CFG,
            models=MODELS,
            suite="full",
            prompt_versions=list(prompt_versions),
            not_scored=1,
        )
        for sid, results in by_system.items()
    ]


QUESTIONS = select_questions(load_gold(FIXTURES / "gold_valid.jsonl"), "full", CFG)


async def test_end_to_end_baselines(tmp_path: Path) -> None:
    server = FakeServer()
    by_system = await run_suite(make_run(server, tmp_path), QUESTIONS, ["B0", "B1", "B2"], CFG)
    reports = {r["system"]: r for r in reports_for(by_system)}

    assert len(QUESTIONS) == 2  # the out_of_scope fixture is not scored in Phase 0
    for sid in ("B0", "B1", "B2"):
        m = reports[sid]["metrics"]
        assert (m["n"], m["n_errors"]) == (2, 0)
        assert m["correctness"] == 1.0
        assert m["dialect"] == 4
        assert m["latency_p50_ms"] is not None
        assert set(reports[sid]["breakdowns"]["script"]) == {"arabic", "arabizi"}
    assert reports["B0"]["metrics"]["faithfulness"] is None  # no context to be faithful to
    assert reports["B0"]["metrics"]["oracle_truncation_rate"] is None
    assert reports["B1"]["metrics"]["faithfulness"] == 0.5
    assert reports["B2"]["metrics"]["oracle_truncation_rate"] == 0.0
    assert not any(r["self_judged"] for r in reports.values())
    assert not any(r["incomplete"] for r in reports.values())

    table = write_reports(list(reports.values()), "full", tmp_path / "reports").read_text(
        encoding="utf-8"
    )
    assert "| B1 | qwen3:4b | 2 | 1.00 | 0.50 | 4.00 |" in table
    assert len(list((tmp_path / "reports").glob("*_B*.json"))) == 3


async def test_rerun_is_served_from_cache(tmp_path: Path) -> None:
    server = FakeServer()
    await run_suite(make_run(server, tmp_path), QUESTIONS, ["B1"], CFG)
    first = len(server.requests)
    by_system = await run_suite(make_run(server, tmp_path), QUESTIONS, ["B1"], CFG)
    assert len(server.requests) == first
    assert reports_for(by_system)[0]["metrics"]["correctness"] == 1.0


async def test_quota_marks_report_incomplete(tmp_path: Path) -> None:
    server = FakeServer(failing_hosts=("api.test",))
    by_system = await run_suite(make_run(server, tmp_path), QUESTIONS, ["B1", "B2"], CFG)
    reports = {r["system"]: r for r in reports_for(by_system)}
    assert reports["B2"]["incomplete"] is True
    assert reports["B2"]["metrics"]["n_errors"] == 2
    assert reports["B1"]["incomplete"] is False
    assert reports["B1"]["metrics"]["correctness"] == 1.0


def doc(markdown: str) -> OracleDoc:
    return OracleDoc("d", "T", "https://example.org/d", "2026-10-10", markdown)


def test_oracle_fits_budget() -> None:
    text, used, truncated = build_oracle([doc("a b\n\nc d")], budget=100, count=count)
    assert not truncated
    assert "Source: https://example.org/d (retrieved 2026-10-10)" in text
    assert text.endswith("a b\n\nc d")
    assert used == count(text)


def test_oracle_truncates_at_paragraph() -> None:
    header_tokens = count("### T\nSource: https://example.org/d (retrieved 2026-10-10)")
    text, used, truncated = build_oracle(
        [doc("a b\n\nc d e f")], budget=header_tokens + 3, count=count
    )
    assert truncated
    assert text.endswith("a b")
    assert used == header_tokens + 2


def test_missing_processed_doc(tmp_path: Path) -> None:
    with pytest.raises(Exception, match="run ingest"):
        load_docs({"nope"}, tmp_path)


@pytest.mark.parametrize(
    ("name", "family"),
    [
        ("qwen3:4b", "qwen"),
        ("qwen/qwen3.8-27b", "qwen"),
        ("gemini-2.5-flash", "gemini"),
        ("openai/gpt-oss-120b", "gpt"),
    ],
)
def test_model_family(name: str, family: str) -> None:
    assert model_family(name) == family


def test_self_judging_detection() -> None:
    models = ModelsConfig.model_validate(
        {
            "providers": MODELS.model_dump()["providers"],
            "models": {
                **MODELS.model_dump()["models"],
                "qwen_judge": {"provider": "judge", "name": "qwen/qwen3.8-27b"},
                "gemini_judge": {"provider": "api", "name": "gemini-y"},
            },
        }
    )
    assert not is_self_judged(models, "local", "groq_judge")
    assert not is_self_judged(models, "gemini_flash", "groq_judge")
    assert is_self_judged(models, "local", "qwen_judge")  # same family, other provider
    assert is_self_judged(models, "gemini_flash", "gemini_judge")


def test_repo_eval_config_matches_models() -> None:
    cfg = load_eval_config()
    models = load_models_config()
    assert cfg.judge_model in models.models
    assert all(s.model in models.models for s in cfg.systems.values())
    # The default judge must not judge any configured baseline (B2 especially).
    assert not any(is_self_judged(models, s.model, cfg.judge_model) for s in cfg.systems.values())


def test_smoke_selects_first_in_scope_by_id() -> None:
    questions = load_gold(FIXTURES / "gold_valid.jsonl")
    small = CFG.model_copy(update={"smoke_size": 1})
    assert [q.id for q in select_questions(questions, "smoke", small)] == ["t-001"]
