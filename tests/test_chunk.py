import itertools
import json
from pathlib import Path

from hypothesis import given, settings
from hypothesis import strategies as st

from chaouch.config import ChunkingConfig
from chaouch.ingestion.chunk import chunk_all, chunk_document, split_sections, tail
from chaouch.ingestion.sources import Source
from chaouch.ingestion.tokens import whitespace_token_counter as count

CFG = ChunkingConfig(tokenizer="unused", target_tokens=12, max_tokens=16, overlap_tokens=3)


def words(n: int, prefix: str = "w") -> str:
    return " ".join(f"{prefix}{i}" for i in range(n))


def test_split_sections_tracks_heading_path() -> None:
    markdown = "intro text\n# A\na body\n## B\nb body\n## C\nc body\n# D\nd body"
    sections = split_sections(markdown)
    assert [(s.heading, s.body) for s in sections] == [
        ("", "intro text"),
        ("A", "a body"),
        ("A > B", "b body"),
        ("A > C", "c body"),
        ("D", "d body"),
    ]


def test_empty_sections_are_dropped() -> None:
    assert [s.heading for s in split_sections("# A\n## B\nonly b")] == ["A > B"]


def test_short_section_is_one_chunk() -> None:
    [chunk] = chunk_document("# T\nfew words here", CFG, count)
    assert chunk.text == "few words here"
    assert chunk.section == "T"


def test_long_paragraph_split_with_overlap() -> None:
    chunks = chunk_document("# T\n" + words(40), CFG, count)
    assert len(chunks) > 1
    for prev, nxt in itertools.pairwise(chunks):
        overlap = prev.body.split()[-CFG.overlap_tokens :]
        assert nxt.text.split()[: CFG.overlap_tokens] == overlap
        assert nxt.text.endswith(nxt.body)


def test_tables_split_by_rows_not_mid_row() -> None:
    rows = "\n".join(f"| r{i} | v{i} |" for i in range(8))  # 5 tokens/row, 40 total
    chunks = chunk_document(f"# Fees\n{rows}", CFG, count)
    for chunk in chunks:
        for line in chunk.body.splitlines():
            if line:
                assert line.startswith("|") and line.endswith("|")


def test_tail() -> None:
    assert tail("a b c d", 2, count) == "c d"
    assert tail("a b", 0, count) == ""


@st.composite
def markdown_docs(draw: st.DrawFn) -> str:
    word = st.text(alphabet="abcdefghijklmnopqrstuvwxyzابتثجح0123456789", min_size=1, max_size=6)
    paragraph = st.lists(word, min_size=1, max_size=40).map(" ".join)
    section = st.tuples(st.integers(1, 3), word, st.lists(paragraph, min_size=0, max_size=4)).map(
        lambda s: f"{'#' * s[0]} {s[1]}\n" + "\n\n".join(s[2])
    )
    return "\n".join(draw(st.lists(section, min_size=1, max_size=5)))


@settings(max_examples=200, deadline=None)
@given(markdown_docs())
def test_chunker_invariants(markdown: str) -> None:
    sections = split_sections(markdown)
    chunks = chunk_document(markdown, CFG, count)
    for chunk in chunks:
        assert count(chunk.text) <= CFG.max_tokens
        assert chunk.text.endswith(chunk.body)
    for section in sections:
        own = [c for c in chunks if c.section == section.heading]
        # No text lost or reordered: the bodies, in order, are exactly the section's words.
        rebuilt = [w for c in own if c.body for w in c.body.split()]
        expected_text = " ".join(x.body for x in sections if x.heading == section.heading)
        assert rebuilt == expected_text.split()


def test_chunk_all_writes_metadata(tmp_path: Path) -> None:
    source = Source(
        doc_id="doc_a",
        url="https://gov.test/a",
        procedure="proc_a",
        language="ar",
        license_note="t",
    )
    meta = {
        "doc_id": "doc_a",
        "source_url": "https://gov.test/a",
        "procedure": "proc_a",
        "language": "ar",
        "title": "T",
        "retrieved_at": "2026-10-10T12:00:00+00:00",
        "sha256": "abc",
    }
    (tmp_path / "doc_a.json").write_text(json.dumps(meta), encoding="utf-8")
    (tmp_path / "doc_a.md").write_text("# T\n" + words(30), encoding="utf-8")
    missing_source = source.model_copy(update={"doc_id": "doc_missing"})

    out, missing = chunk_all([source, missing_source], tmp_path, CFG, count)

    assert missing == ["doc_missing"]
    records = [json.loads(line) for line in out.read_text(encoding="utf-8").splitlines()]
    assert [r["chunk_id"] for r in records][:2] == ["doc_a-0000", "doc_a-0001"]
    first = records[0]
    expected_keys = {"doc_id", "procedure", "language", "source_url", "title", "section"}
    assert expected_keys <= first.keys()
    assert first["retrieved_at"] == "2026-10-10T12:00:00+00:00"
    assert first["n_tokens"] == count(first["text"])
