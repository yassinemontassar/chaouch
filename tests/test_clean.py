import json
from pathlib import Path

import pymupdf
import pytest

from chaouch.ingestion.clean import CleanError, clean_document, first_heading
from chaouch.ingestion.fetch import meta_path
from chaouch.ingestion.sources import Source

FIXTURES = Path(__file__).parent / "fixtures"
SOURCE = Source(
    doc_id="doc_a",
    url="https://gov.test/page",
    procedure="proc_a",
    language="fr",
    license_note="test",
)


def put_raw(raw_dir: Path, name: str, content: bytes) -> None:
    raw_dir.mkdir(parents=True, exist_ok=True)
    (raw_dir / name).write_bytes(content)
    meta = {"raw_file": name, "retrieved_at": "2026-10-10T12:00:00+00:00", "sha256": "abc"}
    meta_path(raw_dir, "doc_a").write_text(json.dumps(meta), encoding="utf-8")


def make_pdf() -> bytes:
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 72), "PLACEHOLDER PDF HEADING", fontsize=24)
    page.insert_text((72, 120), "Synthetic body line one of the test document.", fontsize=11)
    doc.set_metadata({"title": "Microsoft Word - junk.docx"})
    data: bytes = doc.tobytes()
    doc.close()
    return data


def test_html_keeps_headings_and_content_drops_nav(tmp_path: Path) -> None:
    put_raw(tmp_path / "raw", "doc_a.html", (FIXTURES / "page.html").read_bytes())
    out = clean_document(SOURCE, tmp_path / "raw", tmp_path / "processed")
    markdown = out.read_text(encoding="utf-8")
    assert "# PLACEHOLDER HEADING ONE" in markdown
    assert "## PLACEHOLDER HEADING TWO" in markdown
    assert "فقرة تجريبية" in markdown
    assert "| cell 1 | cell 2 |" in markdown
    assert "NAVLINK" not in markdown
    assert "FOOTER" not in markdown
    meta = json.loads((tmp_path / "processed" / "doc_a.json").read_text(encoding="utf-8"))
    assert meta["source_url"] == "https://gov.test/page"
    assert meta["retrieved_at"] == "2026-10-10T12:00:00+00:00"
    assert meta["language"] == "fr"
    assert meta["title"]


def test_pdf_prefers_first_heading_over_junk_metadata(tmp_path: Path) -> None:
    put_raw(tmp_path / "raw", "doc_a.pdf", make_pdf())
    out = clean_document(SOURCE, tmp_path / "raw", tmp_path / "processed")
    assert "Synthetic body line one" in out.read_text(encoding="utf-8")
    meta = json.loads((tmp_path / "processed" / "doc_a.json").read_text(encoding="utf-8"))
    assert meta["title"] == "PLACEHOLDER PDF HEADING"


def test_empty_html_raises(tmp_path: Path) -> None:
    put_raw(tmp_path / "raw", "doc_a.html", b"<html><body></body></html>")
    with pytest.raises(CleanError, match="no text"):
        clean_document(SOURCE, tmp_path / "raw", tmp_path / "processed")


@pytest.mark.parametrize(
    ("markdown", "expected"),
    [("intro\n## **Bold Title** ##\ntext", "Bold Title"), ("no heading here", None)],
)
def test_first_heading(markdown: str, expected: str | None) -> None:
    assert first_heading(markdown) == expected
