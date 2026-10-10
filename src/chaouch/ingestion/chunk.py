from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from chaouch.config import ChunkingConfig
from chaouch.ingestion.sources import Source
from chaouch.ingestion.tokens import TokenCounter

HEADING_LINE = re.compile(r"^(#{1,6})\s+(.*)$")
PARAGRAPH_BREAK = re.compile(r"\n\s*\n")
SENTENCE_BREAK = re.compile(r"(?<=[.!?؟])\s+|\n")  # also splits table rows / list items
JOIN = "\n\n"


@dataclass(frozen=True)
class Section:
    heading: str  # "A > B"; "" before the first heading
    body: str


@dataclass(frozen=True)
class Chunk:
    text: str
    body: str  # text without the overlap from the previous chunk
    section: str


def split_sections(markdown: str) -> list[Section]:
    sections: list[Section] = []
    path: list[tuple[int, str]] = []
    lines: list[str] = []

    def flush() -> None:
        body = "\n".join(lines).strip()
        if body:
            sections.append(Section(" > ".join(text for _, text in path), body))
        lines.clear()

    for line in markdown.splitlines():
        match = HEADING_LINE.match(line)
        if match:
            flush()
            level = len(match.group(1))
            while path and path[-1][0] >= level:
                path.pop()
            path.append((level, match.group(2).strip("#* \t")))
        else:
            lines.append(line)
    flush()
    return sections


def split_words(text: str, limit: int, count: TokenCounter) -> list[str]:
    pieces: list[str] = []
    current: list[str] = []
    for word in text.split():
        if current and count(" ".join([*current, word])) > limit:
            pieces.append(" ".join(current))
            current = []
        current.append(word)
    if current:
        pieces.append(" ".join(current))
    return pieces


def split_units(body: str, limit: int, count: TokenCounter) -> list[str]:
    """Paragraphs; too-long paragraphs become sentences, too-long sentences become word runs."""
    units: list[str] = []
    for paragraph in PARAGRAPH_BREAK.split(body):
        paragraph = paragraph.strip()
        if not paragraph:
            continue
        if count(paragraph) <= limit:
            units.append(paragraph)
            continue
        for sentence in SENTENCE_BREAK.split(paragraph):
            sentence = sentence.strip()
            if not sentence:
                continue
            if count(sentence) <= limit:
                units.append(sentence)
            else:
                units.extend(split_words(sentence, limit, count))
    return units


def tail(text: str, budget: int, count: TokenCounter) -> str:
    words = text.split()
    taken = 0
    while taken < len(words) and count(" ".join(words[-(taken + 1) :])) <= budget:
        taken += 1
    return " ".join(words[-taken:]) if taken else ""


def chunk_section(section: Section, cfg: ChunkingConfig, count: TokenCounter) -> list[Chunk]:
    # ponytail: re-counts the growing candidate each step (quadratic); fine for a small corpus.
    units = split_units(section.body, cfg.max_tokens - cfg.overlap_tokens, count)
    chunks: list[Chunk] = []
    current: list[str] = []
    overlap = ""

    def compose(parts: list[str]) -> str:
        body = JOIN.join(parts)
        return f"{overlap}{JOIN}{body}" if overlap else body

    def emit() -> None:
        body = JOIN.join(current)
        text = compose(current)
        if count(text) > cfg.max_tokens:  # non-additive tokenizers can overshoot by a token
            text = body
        chunks.append(Chunk(text=text, body=body, section=section.heading))

    for unit in units:
        if current and count(compose([*current, unit])) > cfg.target_tokens:
            emit()
            overlap = tail(JOIN.join(current), cfg.overlap_tokens, count)
            current = []
        current.append(unit)
    if current:
        emit()
    return chunks


def chunk_document(markdown: str, cfg: ChunkingConfig, count: TokenCounter) -> list[Chunk]:
    return [c for s in split_sections(markdown) for c in chunk_section(s, cfg, count)]


def chunk_all(
    sources: list[Source], processed_dir: Path, cfg: ChunkingConfig, count: TokenCounter
) -> tuple[Path, list[str]]:
    out = processed_dir / "chunks.jsonl"
    missing: list[str] = []
    records: list[str] = []
    for source in sources:
        md_path = processed_dir / f"{source.doc_id}.md"
        meta_file = processed_dir / f"{source.doc_id}.json"
        if not (md_path.exists() and meta_file.exists()):
            missing.append(source.doc_id)
            continue
        meta = json.loads(meta_file.read_text(encoding="utf-8"))
        chunks = chunk_document(md_path.read_text(encoding="utf-8"), cfg, count)
        for i, chunk in enumerate(chunks):
            record = {
                "chunk_id": f"{source.doc_id}-{i:04d}",
                "doc_id": source.doc_id,
                "procedure": meta["procedure"],
                "language": meta["language"],
                "source_url": meta["source_url"],
                "title": meta["title"],
                "section": chunk.section,
                "retrieved_at": meta["retrieved_at"],
                "n_tokens": count(chunk.text),
                "text": chunk.text,
            }
            records.append(json.dumps(record, ensure_ascii=False))
    processed_dir.mkdir(parents=True, exist_ok=True)
    out.write_text("".join(f"{r}\n" for r in records), encoding="utf-8")
    return out, missing
