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


class SourcesFile(StrictModel):
    sources: list[Source]

    @model_validator(mode="after")
    def _unique_doc_ids(self) -> SourcesFile:
        ids = [s.doc_id for s in self.sources]
        dupes = sorted({i for i in ids if ids.count(i) > 1})
        if dupes:
            raise ValueError(f"duplicate doc_id: {', '.join(dupes)}")
        return self


def load_sources(path: Path = SOURCES_PATH) -> list[Source]:
    return load_yaml(path, SourcesFile).sources
