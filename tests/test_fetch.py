import json
from datetime import UTC, datetime
from pathlib import Path

import httpx2
import pytest

from chaouch.config import IngestionConfig
from chaouch.ingestion.fetch import Fetcher, meta_path
from chaouch.ingestion.sources import Source

CFG = IngestionConfig(user_agent="TestBot", request_delay_s=3.0, timeout_s=5)
PAGE = b"<html><body><p>PLACEHOLDER</p></body></html>"


def source(doc_id: str = "doc_a", url: str = "https://gov.test/page") -> Source:
    return Source(doc_id=doc_id, url=url, procedure="proc_a", language="fr", license_note="test")


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0
        self.sleeps: list[float] = []

    def __call__(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds


class Site:
    """MockTransport handler: a robots.txt plus a dict of pages."""

    def __init__(self, robots: httpx2.Response, pages: dict[str, httpx2.Response]) -> None:
        self.robots = robots
        self.pages = pages
        self.requests: list[httpx2.Request] = []

    def __call__(self, request: httpx2.Request) -> httpx2.Response:
        self.requests.append(request)
        if request.url.path == "/robots.txt":
            return self.robots
        return self.pages.get(request.url.path, httpx2.Response(404))


def html(body: bytes = PAGE) -> httpx2.Response:
    return httpx2.Response(200, headers={"content-type": "text/html; charset=utf-8"}, content=body)


def make_fetcher(site: Site, clock: FakeClock | None = None) -> Fetcher:
    clock = clock or FakeClock()
    client = httpx2.Client(transport=httpx2.MockTransport(site))
    return Fetcher(
        CFG,
        client,
        clock=clock,
        sleep=clock.sleep,
        now=lambda: datetime(2026, 10, 10, 12, 0, tzinfo=UTC),
    )


def test_fetch_writes_raw_and_meta(tmp_path: Path) -> None:
    site = Site(httpx2.Response(404), {"/page": html()})
    result = make_fetcher(site).fetch(source(), tmp_path)
    assert result.status == "fetched"
    assert (tmp_path / "doc_a.html").read_bytes() == PAGE
    meta = json.loads(meta_path(tmp_path, "doc_a").read_text(encoding="utf-8"))
    assert meta["retrieved_at"] == "2026-10-10T12:00:00+00:00"
    assert meta["content_type"] == "text/html"
    assert meta["raw_file"] == "doc_a.html"
    assert len(meta["sha256"]) == 64
    assert site.requests[-1].headers["user-agent"] == "TestBot"


def test_pdf_detected_from_content_type(tmp_path: Path) -> None:
    pdf = httpx2.Response(200, headers={"content-type": "application/pdf"}, content=b"%PDF-1.4")
    site = Site(httpx2.Response(404), {"/download": pdf})
    make_fetcher(site).fetch(source(url="https://gov.test/download"), tmp_path)
    assert (tmp_path / "doc_a.pdf").exists()


def test_robots_disallow_blocks(tmp_path: Path) -> None:
    robots = httpx2.Response(200, text="User-agent: *\nDisallow: /page\n")
    site = Site(robots, {"/page": html()})
    result = make_fetcher(site).fetch(source(), tmp_path)
    assert result.status == "blocked"
    assert [r.url.path for r in site.requests] == ["/robots.txt"]


def test_robots_server_error_blocks(tmp_path: Path) -> None:
    site = Site(httpx2.Response(503), {"/page": html()})
    assert make_fetcher(site).fetch(source(), tmp_path).status == "blocked"


def test_robots_fetched_once_per_host(tmp_path: Path) -> None:
    site = Site(httpx2.Response(404), {"/a": html(), "/b": html()})
    sources = [source("doc_a", "https://gov.test/a"), source("doc_b", "https://gov.test/b")]
    fetcher = make_fetcher(site)
    for s in sources:
        fetcher.fetch(s, tmp_path)
    assert [r.url.path for r in site.requests] == ["/robots.txt", "/a", "/b"]


def test_per_host_delay(tmp_path: Path) -> None:
    clock = FakeClock()
    site = Site(httpx2.Response(404), {"/a": html(), "/b": html()})
    sources = [source("doc_a", "https://gov.test/a"), source("doc_b", "https://gov.test/b")]
    fetcher = make_fetcher(site, clock)
    for s in sources:
        fetcher.fetch(s, tmp_path)
    assert clock.sleeps == [3.0, 3.0]  # robots -> /a -> /b, each 3 s apart


def test_skip_existing_unless_force(tmp_path: Path) -> None:
    site = Site(httpx2.Response(404), {"/page": html()})
    fetcher = make_fetcher(site)
    assert fetcher.fetch(source(), tmp_path).status == "fetched"
    assert fetcher.fetch(source(), tmp_path).status == "skipped"
    site.pages["/page"] = html(b"<html><body>NEW</body></html>")
    assert fetcher.fetch(source(), tmp_path, force=True).status == "fetched"
    assert (tmp_path / "doc_a.html").read_bytes() == b"<html><body>NEW</body></html>"


@pytest.mark.parametrize(
    "response",
    [httpx2.Response(404), httpx2.Response(200, headers={"content-type": "image/png"})],
)
def test_failures_do_not_write(tmp_path: Path, response: httpx2.Response) -> None:
    site = Site(httpx2.Response(404), {"/page": response})
    assert make_fetcher(site).fetch(source(), tmp_path).status == "failed"
    assert not meta_path(tmp_path, "doc_a").exists()
