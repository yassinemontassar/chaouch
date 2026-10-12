"""Postgres + pgvector. Needs `uv run tasks.py db-up`; runs in a throwaway schema."""

import uuid
from collections.abc import Iterator

import numpy as np
import pytest

from chaouch.config import Settings
from chaouch.retrieval.chunks import ChunkRecord
from chaouch.retrieval.store import (
    Connection,
    StaleIndexError,
    assert_fresh,
    connect,
    dense_search,
    rebuild,
)

pytestmark = pytest.mark.integration


def chunk(chunk_id: str, role: str = "core") -> ChunkRecord:
    return ChunkRecord.model_validate(
        {
            "chunk_id": chunk_id,
            "doc_id": chunk_id.split("-")[0],
            "procedure": "cin",
            "language": "fr",
            "source_url": "http://example.tn",
            "title": "t",
            "section": "",
            "retrieved_at": "2026-10-11",
            "n_tokens": 1,
            "text": "x",
            "role": role,
        }
    )


def unit(*values: float) -> np.ndarray:
    v = np.array(values, dtype=np.float32)
    return v / np.linalg.norm(v)


@pytest.fixture
def conn() -> Iterator[Connection]:
    schema = f"test_{uuid.uuid4().hex[:8]}"
    with connect(Settings().database_dsn()) as c:
        c.execute(f"CREATE SCHEMA {schema}")
        c.execute(f"SET search_path TO {schema}, public")
        c.commit()
        try:
            yield c
        finally:
            c.rollback()
            c.execute(f"DROP SCHEMA {schema} CASCADE")
            c.commit()


CHUNKS = [chunk("a-0"), chunk("b-0"), chunk("c-0", role="distractor")]
VECTORS = {
    "e1": np.stack([unit(1, 0, 0), unit(1, 1, 0), unit(0, 1, 0)]),
    "e2": np.stack([unit(0, 1, 0), unit(1, 1, 0), unit(1, 0, 0)]),
}


def test_dense_search_orders_by_cosine_and_filters(conn: Connection) -> None:
    rebuild(conn, CHUNKS, VECTORS, "sha1")
    query = unit(1, 0.1, 0)
    assert dense_search(conn, "e1", query, 3) == ["a-0", "b-0", "c-0"]
    assert dense_search(conn, "e2", query, 3) == ["c-0", "b-0", "a-0"]
    assert dense_search(conn, "e2", query, 3, roles=["core"]) == ["b-0", "a-0"]
    assert dense_search(conn, "e1", query, 1) == ["a-0"]


def test_rebuild_replaces_everything(conn: Connection) -> None:
    rebuild(conn, CHUNKS, VECTORS, "sha1")
    rebuild(conn, CHUNKS[:1], {"e1": VECTORS["e1"][:1]}, "sha2")
    assert dense_search(conn, "e1", unit(0, 1, 0), 5) == ["a-0"]
    assert dense_search(conn, "e2", unit(0, 1, 0), 5) == []


def test_freshness(conn: Connection) -> None:
    with pytest.raises(StaleIndexError, match="missing"):
        assert_fresh(conn, "e1", "sha1")  # no tables yet
    rebuild(conn, CHUNKS, VECTORS, "sha1")
    assert_fresh(conn, "e1", "sha1")
    with pytest.raises(StaleIndexError, match="stale"):
        assert_fresh(conn, "e1", "other")
    with pytest.raises(StaleIndexError, match="missing"):
        assert_fresh(conn, "e3", "sha1")


def test_vector_count_must_match_chunks(conn: Connection) -> None:
    with pytest.raises(ValueError, match="2 vectors for 3 chunks"):
        rebuild(conn, CHUNKS, {"e1": VECTORS["e1"][:2]}, "sha1")
