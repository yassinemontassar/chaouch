from __future__ import annotations

import json
import re
from pathlib import Path

import pymupdf4llm
import trafilatura

from chaouch.ingestion.fetch import meta_path
from chaouch.ingestion.sources import Source

HEADING = re.compile(r"^#{1,6}\s+(.+?)\s*#*\s*$", re.MULTILINE)


class CleanError(Exception):
    pass


def first_heading(markdown: str) -> str | None:
    match = HEADING.search(markdown)
    return match.group(1).strip("* ") if match else None


def html_to_markdown(html: bytes) -> tuple[str, str | None]:
    markdown = trafilatura.extract(
        html,
        output_format="markdown",
        include_tables=True,
        include_links=False,
        include_comments=False,
    )
    metadata = trafilatura.extract_metadata(html)
    return markdown or "", metadata.title if metadata else None


def clean_document(source: Source, raw_dir: Path, processed_dir: Path) -> Path:
    meta = json.loads(meta_path(raw_dir, source.doc_id).read_text(encoding="utf-8"))
    raw_file = raw_dir / meta["raw_file"]
    if raw_file.suffix == ".pdf":
        markdown, title = pymupdf4llm.to_markdown(str(raw_file)), None
    else:
        markdown, title = html_to_markdown(raw_file.read_bytes())
    if not markdown.strip():
        raise CleanError(f"{source.doc_id}: no text extracted from {raw_file.name}")

    processed_dir.mkdir(parents=True, exist_ok=True)
    out = processed_dir / f"{source.doc_id}.md"
    out.write_text(markdown.strip() + "\n", encoding="utf-8")
    doc_meta = {
        "doc_id": source.doc_id,
        "source_url": str(source.url),
        "procedure": source.procedure,
        "language": source.language,
        "title": title or first_heading(markdown) or source.doc_id,
        "retrieved_at": meta["retrieved_at"],
        "sha256": meta["sha256"],
    }
    (processed_dir / f"{source.doc_id}.json").write_text(
        json.dumps(doc_meta, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return out
