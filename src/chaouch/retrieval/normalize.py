"""Text normalization for lexical search (spec 9.2). Applied to chunks and queries alike.

Orthographic only: Arabizi stays in Latin letters (transliteration is the Phase 4 normalizer).
"""

from __future__ import annotations

import re
import unicodedata

TATWEEL = "\u0640"
# Applied after NFD split the hamza and madda off أ إ آ ؤ ئ and the combining marks were dropped.
FOLD = str.maketrans(
    {
        "ٱ": "ا",  # alef wasla
        "ى": "ي",  # alef maqsura
        "ة": "ه",  # ta marbuta
        TATWEEL: None,
        **{chr(0x0660 + i): str(i) for i in range(10)},  # Arabic-Indic digits
        **{chr(0x06F0 + i): str(i) for i in range(10)},  # Extended Arabic-Indic digits
    }
)
WORD = re.compile(r"\w+")


def normalize(text: str) -> str:
    """Casefold, drop every combining mark (Arabic diacritics, hamza/madda on alef, Latin accents),
    unify alef / ya / ta marbuta, remove tatweel, use Western digits."""
    text = unicodedata.normalize("NFKC", text).casefold()
    text = "".join(c for c in unicodedata.normalize("NFD", text) if unicodedata.category(c) != "Mn")
    return unicodedata.normalize("NFKC", text.translate(FOLD))


def tokenize(text: str) -> list[str]:
    """Word tokens; digits stay inside words (Arabizi `9addech`, `3omri`)."""
    return WORD.findall(normalize(text))
