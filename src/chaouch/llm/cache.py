"""SQLite cache for LLM calls, so eval runs are cheap to repeat and resumable across days."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path
from typing import Any


class SQLiteCache:
    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(path)
        self._db.execute(
            "CREATE TABLE IF NOT EXISTS calls (key TEXT PRIMARY KEY, value TEXT NOT NULL)"
        )

    @staticmethod
    def key(provider: str, request: dict[str, Any]) -> str:
        """Hash of everything that determines the answer (prompt text carries its version)."""
        blob = json.dumps([provider, request], sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(blob.encode("utf-8")).hexdigest()

    def get(self, key: str) -> dict[str, Any] | None:
        row = self._db.execute("SELECT value FROM calls WHERE key = ?", (key,)).fetchone()
        return None if row is None else dict(json.loads(row[0]))

    def put(self, key: str, value: dict[str, Any]) -> None:
        with self._db:
            self._db.execute(
                "INSERT OR REPLACE INTO calls (key, value) VALUES (?, ?)",
                (key, json.dumps(value, ensure_ascii=False)),
            )

    def close(self) -> None:
        self._db.close()
