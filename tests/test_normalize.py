import unicodedata

from hypothesis import given
from hypothesis import strategies as st

from chaouch.retrieval.normalize import normalize, tokenize


def test_arabic_orthography_is_unified() -> None:
    assert normalize("أَحْمَد") == "احمد"  # diacritics and hamza on alef
    assert normalize("إسلام آمنة ٱلولادة") == "اسلام امنه الولاده"
    assert normalize("مستشفى") == "مستشفي"
    assert normalize("بطـــاقة") == "بطاقه"  # tatweel


def test_presentation_forms_and_digits() -> None:
    assert normalize("\ufefb") == "لا"  # lam-alef ligature (PDF text)
    assert normalize("٣ دينار و۸۰") == "3 دينار و80"


def test_latin_is_casefolded_and_accent_free() -> None:
    assert normalize("Carte d'Identité ÉTUDIANT") == "carte d'identite etudiant"


def test_tokens_keep_arabizi_digits() -> None:
    assert tokenize("9addech yokhou wa9t el bulletin n°3?") == [
        "9addech",
        "yokhou",
        "wa9t",
        "el",
        "bulletin",
        "n",
        "3",
    ]
    assert tokenize("قدّاش تكلّف البطاقة عدد 3؟") == ["قداش", "تكلف", "البطاقه", "عدد", "3"]


@given(st.text())
def test_normalize_is_idempotent(text: str) -> None:
    once = normalize(text)
    assert normalize(once) == once


@given(st.text())
def test_no_combining_marks_left(text: str) -> None:
    assert not any(unicodedata.category(c) == "Mn" for c in normalize(text))


@given(st.from_regex(r"[0-9a-z]+", fullmatch=True))
def test_ascii_words_survive(word: str) -> None:
    assert tokenize(word) == [word]
