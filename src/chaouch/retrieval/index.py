"""Build the retrieval index from chunks.jsonl. Usage: uv run tasks.py index (after `db-up`)."""

from __future__ import annotations

import sys
import time

from chaouch.config import Settings, load_retrieval_config
from chaouch.retrieval.chunks import CHUNKS_PATH, indexed_text, load_chunks
from chaouch.retrieval.models import Vectors, load_embedder, release_models
from chaouch.retrieval.store import connect, rebuild


def main() -> int:
    cfg = load_retrieval_config().retrieval
    if not CHUNKS_PATH.exists():
        print("no chunks.jsonl; run `uv run tasks.py ingest` first")
        return 1
    chunks, sha = load_chunks()
    texts = [indexed_text(c) for c in chunks]
    vectors: dict[str, Vectors] = {}
    for key in cfg.embedders:  # one model in memory at a time
        start = time.perf_counter()
        vectors[key] = load_embedder(cfg, key).embed_docs(texts)
        release_models()
        print(f"embed {key}: {len(texts)} chunks in {time.perf_counter() - start:.1f} s")
    with connect(Settings().database_dsn()) as conn:
        rebuild(conn, chunks, vectors, sha)
    docs = len({c.doc_id for c in chunks})
    print(f"index: {len(chunks)} chunks, {docs} docs, {len(vectors)} embedders, sha {sha[:12]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
