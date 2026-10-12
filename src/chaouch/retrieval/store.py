"""Chunks and their embeddings in Postgres + pgvector. Exact cosine scan (no ANN index): the corpus
has a few dozen chunks; add HNSW when it reaches thousands."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

import numpy as np
import psycopg
from pgvector.psycopg import register_vector

from chaouch.retrieval.chunks import ChunkRecord
from chaouch.retrieval.models import Vectors

Connection = psycopg.Connection[tuple[Any, ...]]

SCHEMA = """
CREATE TABLE IF NOT EXISTS chunks (
    chunk_id text PRIMARY KEY,
    doc_id text NOT NULL,
    procedure text NOT NULL,
    role text NOT NULL,
    language text NOT NULL,
    source_url text NOT NULL,
    title text NOT NULL,
    section text NOT NULL,
    retrieved_at text NOT NULL,
    text text NOT NULL
);
-- vector without a fixed size: each embedder has its own dimension (checked at index time)
CREATE TABLE IF NOT EXISTS embeddings (
    chunk_id text NOT NULL REFERENCES chunks ON DELETE CASCADE,
    embedder text NOT NULL,
    embedding vector NOT NULL,
    PRIMARY KEY (chunk_id, embedder)
);
CREATE TABLE IF NOT EXISTS index_meta (
    embedder text PRIMARY KEY,
    chunks_sha text NOT NULL
);
"""

COLUMNS = (
    "chunk_id",
    "doc_id",
    "procedure",
    "role",
    "language",
    "source_url",
    "title",
    "section",
    "retrieved_at",
    "text",
)


class StaleIndexError(Exception):
    pass


def connect(dsn: str) -> Connection:
    conn = psycopg.connect(dsn)
    conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
    conn.commit()
    register_vector(conn)
    return conn


def rebuild(
    conn: Connection,
    chunks: Sequence[ChunkRecord],
    vectors: Mapping[str, Vectors],
    chunks_sha: str,
) -> None:
    """Replace the whole index in one transaction."""
    placeholders = ", ".join(["%s"] * len(COLUMNS))
    with conn.transaction(), conn.cursor() as cur:
        cur.execute(SCHEMA)
        cur.execute("TRUNCATE chunks, embeddings, index_meta")
        cur.executemany(
            f"INSERT INTO chunks ({', '.join(COLUMNS)}) VALUES ({placeholders})",
            [tuple(getattr(c, col) for col in COLUMNS) for c in chunks],
        )
        for embedder, vecs in vectors.items():
            if len(vecs) != len(chunks):
                raise ValueError(f"{embedder}: {len(vecs)} vectors for {len(chunks)} chunks")
            cur.executemany(
                "INSERT INTO embeddings (chunk_id, embedder, embedding) VALUES (%s, %s, %s)",
                [(c.chunk_id, embedder, v) for c, v in zip(chunks, vecs, strict=True)],
            )
            cur.execute(
                "INSERT INTO index_meta (embedder, chunks_sha) VALUES (%s, %s)",
                (embedder, chunks_sha),
            )


def assert_fresh(conn: Connection, embedder: str, chunks_sha: str) -> None:
    try:
        row = conn.execute(
            "SELECT chunks_sha FROM index_meta WHERE embedder = %s", (embedder,)
        ).fetchone()
    except psycopg.errors.UndefinedTable:
        conn.rollback()
        row = None
    if row is None or row[0] != chunks_sha:
        state = "missing" if row is None else "stale (chunks.jsonl changed)"
        raise StaleIndexError(f"{embedder} index is {state}; run `uv run tasks.py index`")


def chunk_vectors(conn: Connection, embedder: str) -> dict[str, Vectors]:
    rows = conn.execute(
        "SELECT chunk_id, embedding FROM embeddings WHERE embedder = %s", (embedder,)
    ).fetchall()
    return {str(r[0]): np.asarray(r[1].to_numpy(), dtype=np.float32) for r in rows}


def dense_search(
    conn: Connection,
    embedder: str,
    query_vector: Vectors,
    n: int,
    roles: Sequence[str] = ("core", "distractor"),
) -> list[str]:
    """Chunk ids by cosine distance (vectors are normalized), ties by chunk id."""
    rows = conn.execute(
        "SELECT e.chunk_id FROM embeddings e JOIN chunks c USING (chunk_id)"
        " WHERE e.embedder = %s AND c.role = ANY(%s)"
        " ORDER BY e.embedding <=> %s, e.chunk_id LIMIT %s",
        (embedder, list(roles), query_vector, n),
    ).fetchall()
    return [str(r[0]) for r in rows]
