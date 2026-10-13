from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import AnyHttpUrl, Field, model_validator

from chaouch.config import ROOT, StrictModel, load_yaml

SOURCES_PATH = ROOT / "data" / "documents" / "sources.yaml"


class Source(StrictModel):
    doc_id: str = Field(pattern=r"^[a-z0-9_]+$")  # stable: gold questions reference it
    url: AnyHttpUrl
    procedure: str = Field(pattern=r"^[a-z0-9_]+$")
    language: Literal["fr", "ar"]
    license_note: str = Field(min_length=1)
    notes: str | None = None  # owner caveats, e.g. "may predate the 2024 CIN law"
    # HTML only. precision = trafilatura's default; recall keeps short blocks it would drop.
    extract_mode: Literal["precision", "recall"] = "precision"
    # distractor: an official page on another procedure, indexed only to make retrieval harder
    # (ADR 0013). Never a gold document, never a supported procedure.
    role: Literal["core", "distractor"] = "core"
    # The same page in the other language (gold v2, ADR 0014): retrieval scoring counts either one
    # as the gold document, so gold_doc_ids keep naming the original.
    translation_of: str | None = None


class SourcesFile(StrictModel):
    sources: list[Source]

    @model_validator(mode="after")
    def _unique_doc_ids(self) -> SourcesFile:
        ids = [s.doc_id for s in self.sources]
        dupes = sorted({i for i in ids if ids.count(i) > 1})
        if dupes:
            raise ValueError(f"duplicate doc_id: {', '.join(dupes)}")
        by_id = {s.doc_id: s for s in self.sources}
        for s in self.sources:
            if s.translation_of is None:
                continue
            original = by_id.get(s.translation_of)
            where = f"{s.doc_id}: translation_of {s.translation_of!r}"
            if original is None:
                raise ValueError(f"{where} is unknown")
            if original.translation_of is not None:
                raise ValueError(f"{where} is itself a translation")
            if "distractor" in (s.role, original.role):
                raise ValueError(f"{where}: both documents must be core")
            if original.language == s.language or original.procedure != s.procedure:
                raise ValueError(f"{where} has the same language or another procedure")
        return self


def load_sources(path: Path = SOURCES_PATH) -> list[Source]:
    return load_yaml(path, SourcesFile).sources
