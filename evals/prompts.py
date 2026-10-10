"""Versioned prompt files: `{{name}}` placeholders; the file stem is the version."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

PLACEHOLDER = re.compile(r"\{\{(\w+)\}\}")


@dataclass(frozen=True)
class Prompt:
    version: str  # e.g. "answer_oracle_v1"
    template: str

    def render(self, **values: str) -> str:
        needed = set(PLACEHOLDER.findall(self.template))
        if needed != set(values):
            raise ValueError(f"{self.version} needs {sorted(needed)}, got {sorted(values)}")
        # A single substitution pass: braces inside values are never expanded.
        return PLACEHOLDER.sub(lambda m: values[m.group(1)], self.template)


def load_prompt(path: Path) -> Prompt:
    return Prompt(version=path.stem, template=path.read_text(encoding="utf-8"))
