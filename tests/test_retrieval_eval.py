from typing import Any

import pytest

from chaouch.config import load_retrieval_config
from chaouch.retrieval.chunks import ChunkRecord
from evals.gold import GoldQuestion
from evals.metrics.aggregate import breakdown, paired_bootstrap_ci
from evals.metrics.retrieval import recall_at_k, reciprocal_rank, retrieval_aggregate
from evals.runners.retrieval import (
    comparison_pairs,
    gold_doc_language,
    markdown,
    paired_differences,
    run_configs,
    score_row,
    summarize,
)

# --- metrics -------------------------------------------------------------------------------------


def test_recall_counts_documents_in_the_top_k_chunks() -> None:
    chunk_docs = ["x", "a", "a", "b"]
    assert recall_at_k(chunk_docs, ["a"], 1) == 0
    assert recall_at_k(chunk_docs, ["a"], 3) == 1
    assert recall_at_k(chunk_docs, ["a", "b"], 3) == 0.5  # two gold docs, one found
    assert recall_at_k(chunk_docs, ["a", "b"], 5) == 1


def test_several_chunks_of_one_gold_doc_count_once() -> None:
    assert recall_at_k(["a", "a", "a"], ["a", "b"], 3) == 0.5


def test_reciprocal_rank() -> None:
    assert reciprocal_rank(["x", "y", "a"], ["a"]) == pytest.approx(1 / 3)
    assert reciprocal_rank(["b", "a"], ["a", "b"]) == 1
    assert reciprocal_rank(["x", "y"], ["a"]) == 0  # gold doc not retrieved
    assert reciprocal_rank([], ["a"]) == 0


def test_breakdown_takes_an_aggregator() -> None:
    rows = [
        {"script": "arabizi", "recall@1": 1.0, "recall@3": 1.0, "recall@5": 1.0, "rr": 1.0},
        {"script": "arabizi", "recall@1": 0.0, "recall@3": 1.0, "recall@5": 1.0, "rr": 0.5},
        {"script": "arabic", "recall@1": 0.0, "recall@3": 0.0, "recall@5": 0.0, "rr": 0.0},
    ]
    out = breakdown(rows, "script", retrieval_aggregate)
    assert out["arabizi"] == {
        "n": 2,
        "recall@1": 0.5,
        "recall@3": 1.0,
        "recall@5": 1.0,
        "mrr": 0.75,
    }
    assert out["arabic"]["mrr"] == 0


def test_paired_bootstrap() -> None:
    same = paired_bootstrap_ci([1.0, 0.0, 1.0], [1.0, 0.0, 1.0])
    assert same == {"diff": 0.0, "ci95": [0.0, 0.0]}
    better = paired_bootstrap_ci([1.0] * 10, [0.0] * 5 + [1.0] * 5)
    assert better["diff"] == 0.5
    low, high = better["ci95"]
    assert 0 < low <= 0.5 <= high <= 1
    assert paired_bootstrap_ci([1.0] * 10, [0.0] * 5 + [1.0] * 5) == better  # fixed seed
    with pytest.raises(ValueError, match="same length"):
        paired_bootstrap_ci([1.0], [1.0, 0.0])


# --- runner pieces --------------------------------------------------------------------------------


def chunk(chunk_id: str, language: str) -> ChunkRecord:
    return ChunkRecord.model_validate(
        {
            "chunk_id": chunk_id,
            "doc_id": chunk_id.split("-")[0],
            "procedure": "p",
            "language": language,
            "source_url": "http://example.tn",
            "title": "t",
            "section": "",
            "retrieved_at": "2026-10-11",
            "n_tokens": 1,
            "text": "x",
        }
    )


def question(qid: str, gold: list[str], script: str = "arabizi") -> GoldQuestion:
    return GoldQuestion.model_validate(
        {
            "id": qid,
            "procedure": "cin",
            "question": "q",
            "script": script,
            "code_switching": False,
            "category": "in_scope",
            "difficulty": "easy",
            "expected_answer": "a",
            "required_facts": ["f"],
            "gold_doc_ids": gold,
        }
    )


CHUNKS = {c.chunk_id: c for c in [chunk("a-0", "fr"), chunk("a-1", "fr"), chunk("b-0", "ar")]}
LANGUAGE = {c.doc_id: c.language for c in CHUNKS.values()}


def test_gold_doc_language() -> None:
    assert gold_doc_language(["a"], LANGUAGE) == "fr"
    assert gold_doc_language(["a", "b"], LANGUAGE) == "mixed"


def test_score_row() -> None:
    row = score_row(question("q1", ["b"]), "core", "bm25", ["a-0", "b-0"], CHUNKS, LANGUAGE, 1)
    assert row["recall@1"] == 0 and row["recall@3"] == 1 and row["rr"] == 0.5
    assert row["doc_language"] == "ar"
    assert row["top_chunks"] == ["a-0"]


def test_configs_and_pairs() -> None:
    cfg = load_retrieval_config().retrieval
    configs = run_configs(cfg)
    assert [c.name for c in configs[:2]] == ["bm25", "dense:bge_m3"]
    assert len(configs) == 1 + 3 * len(cfg.embedders)
    pairs = comparison_pairs(configs)
    assert ("hybrid_rerank:bge_m3", "bm25") in pairs
    assert ("dense:qwen3_emb_0_6b", "dense:bge_m3") in pairs
    assert ("hybrid_rerank:bge_m3", "hybrid:bge_m3") in pairs
    assert ("hybrid:bge_m3", "dense:bge_m3") in pairs
    # only pairs whose two configs were run
    subset = [c for c in configs if c.name in {"bm25", "hybrid:bge_m3", "hybrid_rerank:bge_m3"}]
    assert comparison_pairs(subset) == [
        ("hybrid:bge_m3", "bm25"),
        ("hybrid_rerank:bge_m3", "bm25"),
        ("hybrid_rerank:bge_m3", "hybrid:bge_m3"),
    ]


def rows_for(config: str, rrs: list[float]) -> list[dict[str, Any]]:
    return [
        {
            "id": f"q{i}",
            "corpus": "core",
            "config": config,
            "script": "arabizi",
            "doc_language": "fr",
            "procedure": "cin",
            "recall@1": float(rr == 1),
            "recall@3": float(rr > 0),
            "recall@5": float(rr > 0),
            "rr": rr,
        }
        for i, rr in enumerate(rrs)
    ]


def test_summary_paired_and_markdown() -> None:
    rows = rows_for("bm25", [1, 0.5, 0, 1]) + rows_for("dense:e", [1, 1, 1, 1])
    summary = summarize(rows)
    assert summary["core"]["bm25"]["metrics"]["mrr"] == 0.625
    assert summary["core"]["dense:e"]["ci95"]["rr"] == [1.0, 1.0]
    paired = paired_differences(rows, [("dense:e", "bm25")])
    (mrr,) = [d for d in paired["core"] if d["metric"] == "rr"]
    assert mrr["diff"] == 0.375
    report = {
        "created_at": "2026-10-11T00:00:00+00:00",
        "gold": {"n_questions": 4, "sha256": "f" * 64},
        "chunks_sha256": "e" * 64,
        "configs": [{"name": "bm25"}, {"name": "dense:e"}],
        "corpora": {"core": {"docs": 2, "chunks": 3}},
        "summary": summary,
        "paired": paired,
        "latency": {"bm25": {"p50_ms": 1.0, "p95_ms": 2.0}},
        "retrieval_config": load_retrieval_config().retrieval.model_dump(),
    }
    text = markdown(report)
    assert "| bm25 | 0.50 (0.00–1.00) |" in text
    assert "| dense:e | bm25 | MRR | +0.38 |" in text
    assert "arabizi (n=4)" in text
