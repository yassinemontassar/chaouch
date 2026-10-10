from __future__ import annotations

import asyncio
import dataclasses
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

import httpx2
import openai
from openai import AsyncOpenAI

from chaouch.config import ConfigError, ModelsConfig, Settings
from chaouch.llm.cache import SQLiteCache
from chaouch.llm.rate_limit import QuotaExhausted, RateLimiter

Message = dict[str, str]


@dataclass(frozen=True)
class Completion:
    text: str
    provider: str
    model: str
    prompt_tokens: int | None
    completion_tokens: int | None
    latency_ms: float


class LLMClient:
    """Retries and backoff come from the SDK; rpm/rpd pacing and concurrency from models.yaml."""

    def __init__(
        self,
        config: ModelsConfig,
        settings: Settings,
        *,
        http_client: httpx2.AsyncClient | None = None,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        self._config = config
        self._settings = settings
        self._http_client = http_client
        self._clients: dict[str, AsyncOpenAI] = {}
        self._limiters = {
            name: RateLimiter(p.rpm, p.rpd, clock=clock, sleep=sleep)
            for name, p in config.providers.items()
        }
        self._semaphores = {
            name: asyncio.Semaphore(p.concurrency) for name, p in config.providers.items()
        }

    def openai(self, provider: str) -> AsyncOpenAI:
        if provider not in self._clients:
            cfg = self._config.providers[provider]
            # The SDK needs a non-empty key even for servers without auth (local Ollama).
            api_key = self._settings.api_key(cfg.api_key_env) if cfg.api_key_env else "unused"
            self._clients[provider] = AsyncOpenAI(
                base_url=cfg.base_url,
                api_key=api_key,
                timeout=cfg.timeout_s,
                max_retries=cfg.max_retries,
                http_client=self._http_client,
            )
        return self._clients[provider]

    async def complete(
        self,
        messages: list[Message],
        model_key: str,
        *,
        temperature: float = 0.0,
        json_mode: bool = False,
        cache: SQLiteCache | None = None,
    ) -> Completion:
        if model_key not in self._config.models:
            raise ConfigError(f"unknown model key {model_key!r}; see configs/models.yaml")
        model = self._config.models[model_key]
        provider = model.provider
        request: dict[str, Any] = {
            **model.params,
            "model": model.name,
            "messages": messages,
            "temperature": temperature,
        }
        if json_mode:
            request["response_format"] = {"type": "json_object"}

        key = SQLiteCache.key(provider, request) if cache else None
        if cache and key and (hit := cache.get(key)) is not None:
            return Completion(**hit)

        async with self._semaphores[provider]:
            await self._limiters[provider].acquire()
            start = time.perf_counter()
            try:
                response = await self.openai(provider).chat.completions.create(**request)
            except openai.RateLimitError as exc:  # still 429 after the SDK's retries
                raise QuotaExhausted(f"{provider}: {exc}") from exc
            latency_ms = (time.perf_counter() - start) * 1000

        usage = response.usage
        completion = Completion(
            text=response.choices[0].message.content or "",
            provider=provider,
            model=model.name,
            prompt_tokens=usage.prompt_tokens if usage else None,
            completion_tokens=usage.completion_tokens if usage else None,
            latency_ms=latency_ms,
        )
        if cache and key:
            cache.put(key, dataclasses.asdict(completion))
        return completion
