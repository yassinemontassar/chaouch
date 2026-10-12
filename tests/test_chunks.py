import hashlib
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from chaouch.retrieval.chunks import indexed_text, load_chunks

RECORD = {
    "chunk_id": "doc_x_01-0000",
    "doc_id": "doc_x_01",
    "procedure": "cin",
    "language": "fr",
    "source_url": "http://example.tn/x",
    "title": "Renouvellement de la carte",
    "section": "",
    "retrieved_at": "2026-10-11",
    "n_tokens": 3,
    "text": "Pièces à fournir",
}


def write(tmp_path: Path, *records: dict[str, object]) -> Path:
    path = tmp_path / "chunks.jsonl"
    path.write_text("".join(json.dumps(r) + "\n" for r in records), encoding="utf-8")
    return path


def test_load_chunks_returns_records_and_file_sha(tmp_path: Path) -> None:
    path = write(tmp_path, RECORD, {**RECORD, "chunk_id": "doc_x_01-0001", "role": "distractor"})
    chunks, sha = load_chunks(path)
    assert [c.role for c in chunks] == ["core", "distractor"]
    assert sha == hashlib.sha256(path.read_bytes()).hexdigest()


def test_indexed_text_starts_with_the_title(tmp_path: Path) -> None:
    (chunk,), _ = load_chunks(write(tmp_path, RECORD))
    assert indexed_text(chunk) == "Renouvellement de la carte\n\nPièces à fournir"


def test_unknown_field_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValidationError):
        load_chunks(write(tmp_path, {**RECORD, "surprise": 1}))
