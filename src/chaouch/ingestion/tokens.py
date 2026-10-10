"""Token counting with the embedding model's tokenizer (Arabic inflates counts a lot)."""

from __future__ import annotations

import functools
from collections.abc import Callable

from tokenizers import Tokenizer

TokenCounter = Callable[[str], int]


@functools.cache
def _load(name: str) -> Tokenizer:
    return Tokenizer.from_pretrained(name)  # downloads tokenizer.json once (HF cache)


def hf_token_counter(name: str) -> TokenCounter:
    def count(text: str) -> int:
        return len(_load(name).encode(text, add_special_tokens=False).ids)

    return count


def whitespace_token_counter(text: str) -> int:
    """Offline stand-in for tests."""
    return len(text.split())
