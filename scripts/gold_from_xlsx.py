# /// script
# requires-python = ">=3.12"
# dependencies = ["openpyxl"]
# ///
"""Convert the owner's gold spreadsheet (tab "Questions") to data/evals/gold/questions.jsonl.

Usage: uv run scripts/gold_from_xlsx.py path/to/gold.xlsx
Row 1 is the header, row 2 the EXAMPLE row (skipped); empty rows are skipped.
Text is copied unchanged.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

OUT = Path(__file__).resolve().parents[1] / "data" / "evals" / "gold" / "questions.jsonl"
LIST_FIELDS = {"required_facts", "gold_doc_ids"}


def to_record(header: list[str], row: tuple[Any, ...]) -> dict[str, Any]:
    record: dict[str, Any] = {}
    for name, value in zip(header, row, strict=True):
        if name in LIST_FIELDS:
            items = "" if value is None else str(value)
            record[name] = [item.strip() for item in items.split(";") if item.strip()]
        else:
            record[name] = value
    record["notes"] = record.get("notes") or ""
    if record.get("procedure") == "out_of_scope":  # a label in the sheet; the schema wants null
        record["procedure"] = None
    return record


def main(xlsx: Path) -> int:
    import openpyxl

    sheet = openpyxl.load_workbook(xlsx, read_only=True, data_only=True)["Questions"]
    rows = list(sheet.iter_rows(values_only=True))
    header = [str(h).split("\n")[0].strip() for h in rows[0]]  # "required_facts\n(separate with ;)"
    if rows[1][0] != "EXAMPLE":
        print(f"row 2 should be the EXAMPLE row, found id {rows[1][0]!r}")
        return 1
    lines = []
    for number, row in enumerate(rows[2:], start=3):
        if all(v is None for v in row):
            continue
        lines.append(json.dumps(to_record(header, row), ensure_ascii=False))
        print(f"row {number} -> line {len(lines)}")
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    print(f"{len(lines)} questions -> {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main(Path(sys.argv[1])))
