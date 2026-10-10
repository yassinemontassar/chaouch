import json
from pathlib import Path

import httpx2
import openai
import pytest

from chaouch.config import ConfigError, ModelsConfig, Settings
from chaouch.llm import LLMClient, QuotaExhausted, RateLimiter, SQLiteCache

CONFIG = ModelsConfig.model_validate(
    {
        "providers": {
            "local": {
                "base_url": "http://llm.test/v1",
                "api_key_env": None,
                "rpm": 600,
                "rpd": None,
                "timeout_s": 5,
                "max_retries": 3,
                "concurrency": 1,
            },
            "capped": {
                "base_url": "http://capped.test/v1",
                "api_key_env": "GROQ_API_KEY",
                "rpm": 600,
                "rpd": 2,
                "timeout_s": 5,
                "max_retries": 0,
                "concurrency": 1,
            },
        },
        "models": {
            "m": {"provider": "local", "name": "local-model"},
            "c": {"provider": "capped", "name": "capped-model"},
        },
    }
)
MESSAGES = [{"role": "user", "content": "PLACEHOLDER"}]


def ok_body(text: str = "hello") -> dict[str, object]:
    return {
        "id": "x",
        "object": "chat.completion",
        "created": 0,
        "model": "local-model",
        "choices": [
            {"index": 0, "finish_reason": "stop", "message": {"role": "assistant", "content": text}}
        ],
        "usage": {"prompt_tokens": 7, "completion_tokens": 3, "total_tokens": 10},
    }


class Recorder:
    """MockTransport handler that replays a scripted list of responses."""

    def __init__(self, *responses: httpx2.Response | Exception) -> None:
        self.responses = list(responses)
        self.requests: list[httpx2.Request] = []

    def __call__(self, request: httpx2.Request) -> httpx2.Response:
        self.requests.append(request)
        item = self.responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


def too_many() -> httpx2.Response:
    # retry-after-ms keeps the SDK's backoff to 1 ms in tests.
    return httpx2.Response(
        429, headers={"retry-after-ms": "1"}, json={"error": {"message": "slow"}}
    )


def make_client(handler: Recorder, settings: Settings | None = None) -> LLMClient:
    http = httpx2.AsyncClient(transport=httpx2.MockTransport(handler))
    return LLMClient(CONFIG, settings or Settings(_env_file=None), http_client=http)


async def test_complete_returns_text_and_usage() -> None:
    handler = Recorder(httpx2.Response(200, json=ok_body("salut")))
    result = await make_client(handler).complete(MESSAGES, "m")
    assert result.text == "salut"
    assert (result.provider, result.model) == ("local", "local-model")
    assert (result.prompt_tokens, result.completion_tokens) == (7, 3)
    assert result.cached is False
    sent = json.loads(handler.requests[0].content)
    assert sent["model"] == "local-model"
    assert sent["temperature"] == 0.0
    assert "response_format" not in sent


async def test_json_mode_sets_response_format() -> None:
    handler = Recorder(httpx2.Response(200, json=ok_body("{}")))
    await make_client(handler).complete(MESSAGES, "m", json_mode=True)
    assert json.loads(handler.requests[0].content)["response_format"] == {"type": "json_object"}


async def test_retries_429_then_succeeds() -> None:
    handler = Recorder(too_many(), too_many(), httpx2.Response(200, json=ok_body()))
    result = await make_client(handler).complete(MESSAGES, "m")
    assert result.text == "hello"
    assert len(handler.requests) == 3


async def test_retries_server_error() -> None:
    handler = Recorder(
        httpx2.Response(503, headers={"retry-after-ms": "1"}), httpx2.Response(200, json=ok_body())
    )
    assert (await make_client(handler).complete(MESSAGES, "m")).text == "hello"


async def test_persistent_429_becomes_quota_exhausted() -> None:
    handler = Recorder(*(too_many() for _ in range(4)))  # 1 try + 3 retries
    with pytest.raises(QuotaExhausted):
        await make_client(handler).complete(MESSAGES, "m")
    assert len(handler.requests) == 4


async def test_timeout_propagates_after_retries(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GROQ_API_KEY", "k")
    handler = Recorder(httpx2.ReadTimeout("slow"))  # capped provider: max_retries=0
    with pytest.raises(openai.APITimeoutError):
        await make_client(handler).complete(MESSAGES, "c")


async def test_daily_cap_stops_before_calling(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GROQ_API_KEY", "k")
    handler = Recorder(*(httpx2.Response(200, json=ok_body()) for _ in range(2)))
    client = make_client(handler)
    await client.complete(MESSAGES, "c")
    await client.complete(MESSAGES, "c")
    with pytest.raises(QuotaExhausted):
        await client.complete(MESSAGES, "c")
    assert len(handler.requests) == 2


async def test_api_key_is_sent(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GROQ_API_KEY", "secret-key")
    handler = Recorder(httpx2.Response(200, json=ok_body()))
    await make_client(handler).complete(MESSAGES, "c")
    assert handler.requests[0].headers["authorization"] == "Bearer secret-key"


async def test_missing_api_key_fails_clearly(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    with pytest.raises(ConfigError, match="GROQ_API_KEY"):
        await make_client(Recorder()).complete(MESSAGES, "c")


async def test_unknown_model_key() -> None:
    with pytest.raises(ConfigError, match="unknown model key"):
        await make_client(Recorder()).complete(MESSAGES, "nope")


async def test_cache_hit_skips_network(tmp_path: Path) -> None:
    cache = SQLiteCache(tmp_path / "sub" / "cache.sqlite")
    handler = Recorder(httpx2.Response(200, json=ok_body("first")))
    client = make_client(handler)
    first = await client.complete(MESSAGES, "m", cache=cache)
    second = await client.complete(MESSAGES, "m", cache=cache)
    assert (first.cached, second.cached) == (False, True)
    assert second.text == "first"
    assert len(handler.requests) == 1


async def test_cache_key_depends_on_request(tmp_path: Path) -> None:
    cache = SQLiteCache(tmp_path / "cache.sqlite")
    handler = Recorder(
        httpx2.Response(200, json=ok_body("a")), httpx2.Response(200, json=ok_body("b"))
    )
    client = make_client(handler)
    await client.complete(MESSAGES, "m", cache=cache)
    other = await client.complete(MESSAGES, "m", temperature=0.7, cache=cache)
    assert other.text == "b"
    assert len(handler.requests) == 2


def test_cache_persists_across_instances(tmp_path: Path) -> None:
    path = tmp_path / "cache.sqlite"
    key = SQLiteCache.key("p", {"x": "عسلامة"})
    first = SQLiteCache(path)
    first.put(key, {"text": "عسلامة"})
    first.close()
    assert SQLiteCache(path).get(key) == {"text": "عسلامة"}
    assert SQLiteCache(path).get("missing") is None


class FakeClock:
    def __init__(self) -> None:
        self.now = 100.0
        self.sleeps: list[float] = []

    def __call__(self) -> float:
        return self.now

    async def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds


async def test_rate_limiter_spaces_requests() -> None:
    clock = FakeClock()
    limiter = RateLimiter(rpm=30, rpd=None, clock=clock, sleep=clock.sleep)  # 2 s apart
    for _ in range(3):
        await limiter.acquire()
    assert clock.sleeps == [2.0, 2.0]


async def test_rate_limiter_no_wait_after_idle() -> None:
    clock = FakeClock()
    limiter = RateLimiter(rpm=30, rpd=None, clock=clock, sleep=clock.sleep)
    await limiter.acquire()
    clock.now += 10
    await limiter.acquire()
    assert clock.sleeps == []


async def test_rate_limiter_daily_cap() -> None:
    clock = FakeClock()
    limiter = RateLimiter(rpm=600, rpd=1, clock=clock, sleep=clock.sleep)
    await limiter.acquire()
    with pytest.raises(QuotaExhausted):
        await limiter.acquire()
