from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict

from chaouch.config import ROOT

CHUNKS_PATH = ROOT / "data" / "documents" / "processed" / "chunks.jsonl"


class ChunkRecord(BaseModel):
    """One line of chunks.jsonl (written by chaouch.ingestion.chunk.chunk_all)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    chunk_id: str
    doc_id: str
    procedure: str
    language: Literal["fr", "ar"]
    source_url: str
    title: str
    section: str
    retrieved_at: str
    n_tokens: int
    text: str
    role: Literal["core", "distractor"] = "core"


def load_chunks(path: Path = CHUNKS_PATH) -> tuple[list[ChunkRecord], str]:
    """The chunks and the sha256 of the file, which identifies the index built from it."""
    data = path.read_bytes()
    lines = data.decode("utf-8").splitlines()
    chunks = [ChunkRecord.model_validate(json.loads(line)) for line in lines if line.strip()]
    return chunks, hashlib.sha256(data).hexdigest()


def indexed_text(chunk: ChunkRecord) -> str:
    """What every retriever sees; the page title separates sibling documents (the two CIN pages)."""
    return f"{chunk.title}\n\n{chunk.text}"
