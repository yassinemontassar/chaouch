"""Download the official sources politely: robots.txt, a per-host delay, no re-downloads."""

from __future__ import annotations

import hashlib
import json
import logging
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Literal
from urllib.parse import urlsplit
from urllib.robotparser import RobotFileParser

import httpx2

from chaouch.config import IngestionConfig
from chaouch.ingestion.sources import Source

log = logging.getLogger(__name__)

Status = Literal["fetched", "skipped", "blocked", "failed"]
DISALLOW_ALL = ["User-agent: *", "Disallow: /"]
EXTENSIONS = {"application/pdf": ".pdf", "text/html": ".html", "application/xhtml+xml": ".html"}


@dataclass(frozen=True)
class FetchResult:
    doc_id: str
    status: Status
    detail: str = ""


def meta_path(raw_dir: Path, doc_id: str) -> Path:
    return raw_dir / f"{doc_id}.meta.json"


class Fetcher:
    def __init__(
        self,
        cfg: IngestionConfig,
        client: httpx2.Client,
        *,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
        now: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._cfg = cfg
        self._client = client
        self._clock = clock
        self._sleep = sleep
        self._now = now
        self._last_request: dict[str, float] = {}
        self._robots: dict[str, RobotFileParser] = {}

    def _get(self, url: str) -> httpx2.Response:
        host = urlsplit(url).netloc
        if host in self._last_request:
            wait = self._last_request[host] + self._cfg.request_delay_s - self._clock()
            if wait > 0:
                self._sleep(wait)
        try:
            return self._client.get(
                url,
                headers={"User-Agent": self._cfg.user_agent},
                timeout=self._cfg.timeout_s,
                follow_redirects=True,
            )
        finally:
            self._last_request[host] = self._clock()

    def _allowed(self, url: str) -> bool:
        parts = urlsplit(url)
        origin = f"{parts.scheme}://{parts.netloc}"
        if origin not in self._robots:
            # RFC 9309: no robots.txt (4xx) allows everything; 5xx or unreachable disallows.
            try:
                response = self._get(f"{origin}/robots.txt")
                if response.status_code >= 500:
                    rules = DISALLOW_ALL
                elif response.status_code >= 400:
                    rules = []
                else:
                    rules = response.text.splitlines()
            except httpx2.HTTPError:
                rules = DISALLOW_ALL
            parser = RobotFileParser()
            parser.parse(rules)
            self._robots[origin] = parser
        return self._robots[origin].can_fetch(self._cfg.user_agent, url)

    def fetch(self, source: Source, raw_dir: Path, *, force: bool = False) -> FetchResult:
        url = str(source.url)
        if meta_path(raw_dir, source.doc_id).exists() and not force:
            return FetchResult(source.doc_id, "skipped", "already downloaded (use --force)")
        if not self._allowed(url):
            return FetchResult(source.doc_id, "blocked", "disallowed by robots.txt")
        try:
            response = self._get(url)
            response.raise_for_status()
        except httpx2.HTTPError as exc:
            return FetchResult(source.doc_id, "failed", str(exc))

        content_type = response.headers.get("content-type", "").split(";")[0].strip().lower()
        ext = EXTENSIONS.get(content_type) or PurePosixPath(urlsplit(url).path).suffix.lower()
        if ext not in {".pdf", ".html", ".htm"}:
            return FetchResult(
                source.doc_id, "failed", f"unsupported content type {content_type!r}"
            )

        raw_dir.mkdir(parents=True, exist_ok=True)
        raw_file = raw_dir / f"{source.doc_id}{ext}"
        raw_file.write_bytes(response.content)
        meta = {
            "doc_id": source.doc_id,
            "url": url,
            "final_url": str(response.url),
            "raw_file": raw_file.name,
            "content_type": content_type,
            "sha256": hashlib.sha256(response.content).hexdigest(),
            "retrieved_at": self._now().isoformat(timespec="seconds"),
        }
        meta_path(raw_dir, source.doc_id).write_text(
            json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return FetchResult(source.doc_id, "fetched", raw_file.name)


def fetch_all(
    sources: list[Source], raw_dir: Path, fetcher: Fetcher, *, force: bool = False
) -> list[FetchResult]:
    results = []
    for source in sources:
        result = fetcher.fetch(source, raw_dir, force=force)
        log.info("fetch", extra={"fields": {"doc_id": result.doc_id, "status": result.status}})
        results.append(result)
    return results
