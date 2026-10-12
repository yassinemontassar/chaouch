import pytest

from chaouch.config import SearchConfig, load_retrieval_config
from chaouch.retrieval.chunks import ChunkRecord
from chaouch.retrieval.pipeline import Corpus, rank, retrieve


def make_cfg(**update: int) -> SearchConfig:
    base = load_retrieval_config().retrieval
    return base.model_copy(update={"top_k": 2, "rerank_candidates": 3, "candidates": 4, **update})


def chunk(chunk_id: str, title: str, text: str, language: str = "fr") -> ChunkRecord:
    return ChunkRecord.model_validate(
        {
            "chunk_id": chunk_id,
            "doc_id": chunk_id.split("-")[0],
            "procedure": "p",
            "language": language,
            "source_url": f"http://example.tn/{chunk_id}",
            "title": title,
            "section": "",
            "retrieved_at": "2026-10-11",
            "n_tokens": 1,
            "text": text,
        }
    )


CHUNKS = [
    chunk("pass-0", "Passeport", "timbre fiscal 80 dinars"),
    chunk("cin-0", "Carte d'identité", "timbre fiscal 3 dinars, extrait de naissance"),
    chunk("b3-0", "Bulletin n°3", "demande en ligne, délai"),
    chunk("birth-0", "مضمون ولادة", "البلدية", language="ar"),
]
CFG = make_cfg()
CORPUS = Corpus.build(CHUNKS, CFG)


def fake_dense(query: str, n: int) -> list[str]:
    return ["birth-0", "cin-0", "b3-0", "pass-0"][:n]


def test_bm25_search_uses_normalized_title_and_text() -> None:
    assert CORPUS.bm25_search("PASSEPORT", 4) == ["pass-0"]
    assert CORPUS.bm25_search("carte d'IDENTITE", 4)[0] == "cin-0"
    assert CORPUS.bm25_search("مضمون الولادة", 4) == ["birth-0"]


def test_each_mode_ranks_from_its_candidates() -> None:
    bm25, dense = ["pass-0", "cin-0"], fake_dense("q", 4)
    assert rank("bm25", "q", bm25, dense, CORPUS, CFG) == bm25
    assert rank("dense", "q", bm25, dense, CORPUS, CFG) == dense
    # cin-0 is in both lists: first after fusion
    assert rank("hybrid", "q", bm25, dense, CORPUS, CFG)[0] == "cin-0"


def test_rerank_sees_only_rerank_candidates_and_reorders_them() -> None:
    seen: list[str] = []

    def rerank(query: str, texts: list[str]) -> list[float]:
        seen.extend(texts)
        return [float(len(t)) for t in texts]  # longest text first

    bm25, dense = ["pass-0", "cin-0"], fake_dense("q", 4)
    fused = rank("hybrid", "q", bm25, dense, CORPUS, CFG)
    ranked = rank("hybrid_rerank", "q", bm25, dense, CORPUS, CFG, rerank)
    assert len(seen) == CFG.rerank_candidates
    assert set(ranked) == set(fused[: CFG.rerank_candidates])
    assert ranked[0] == "cin-0"  # longest indexed text


def test_hybrid_rerank_needs_a_reranker() -> None:
    with pytest.raises(ValueError, match="needs a reranker"):
        rank("hybrid_rerank", "q", ["pass-0"], [], CORPUS, CFG)


def test_retrieve_returns_top_k_records() -> None:
    out = retrieve("passeport", "hybrid", CORPUS, fake_dense, CFG)
    assert len(out) == CFG.top_k
    assert out[0].chunk_id == "pass-0"
    assert out[0].source_url == "http://example.tn/pass-0"


def test_bm25_mode_does_not_call_dense_search() -> None:
    def no_dense(query: str, n: int) -> list[str]:
        raise AssertionError("dense search called")

    assert [c.chunk_id for c in retrieve("passeport", "bm25", CORPUS, no_dense, CFG)] == ["pass-0"]
