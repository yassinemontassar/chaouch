from scripts.gold_from_xlsx import to_record

HEADER = ["id", "procedure", "question", "required_facts", "gold_doc_ids", "notes"]


def test_lists_are_split_and_text_is_kept() -> None:
    row = ("q-001", None, "  chnowa ?  ", "fact a; fact b ;", "doc_a_01", None)
    assert to_record(HEADER, row) == {
        "id": "q-001",
        "procedure": None,
        "question": "  chnowa ?  ",
        "required_facts": ["fact a", "fact b"],
        "gold_doc_ids": ["doc_a_01"],
        "notes": "",
    }


def test_empty_lists() -> None:
    record = to_record(HEADER, ("q-002", None, "x", None, None, "out of scope"))
    assert record["required_facts"] == []
    assert record["gold_doc_ids"] == []
    assert record["notes"] == "out of scope"


def test_out_of_scope_procedure_becomes_null() -> None:
    record = to_record(HEADER, ("oos-001", "out_of_scope", "x", None, None, None))
    assert record["procedure"] is None
