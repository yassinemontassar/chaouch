from pathlib import Path

import pytest

from chaouch.config import ConfigError
from chaouch.ingestion.sources import load_sources

ENTRY = """
  - doc_id: {doc_id}
    url: {url}
    procedure: proc_a
    language: {language}
    license_note: test fixture
"""


def write(tmp_path: Path, *entries: str) -> Path:
    path = tmp_path / "sources.yaml"
    path.write_text("sources:" + "".join(entries), encoding="utf-8")
    return path


def entry(
    doc_id: str = "proc_a_01", url: str = "https://example.org/a", language: str = "fr"
) -> str:
    return ENTRY.format(doc_id=doc_id, url=url, language=language)


def test_repo_sources_file_is_valid() -> None:
    load_sources()  # the owner's file must always parse, even when empty


def test_loads_entries(tmp_path: Path) -> None:
    [source] = load_sources(write(tmp_path, entry()))
    assert source.doc_id == "proc_a_01"
    assert str(source.url) == "https://example.org/a"


@pytest.mark.parametrize(
    "bad",
    [
        entry(doc_id="Has Spaces"),
        entry(url="not-a-url"),
        entry(language="en"),
    ],
)
def test_invalid_entry(tmp_path: Path, bad: str) -> None:
    with pytest.raises(ConfigError):
        load_sources(write(tmp_path, bad))


def test_duplicate_doc_id(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="duplicate doc_id: proc_a_01"):
        load_sources(write(tmp_path, entry(), entry(url="https://example.org/b")))
