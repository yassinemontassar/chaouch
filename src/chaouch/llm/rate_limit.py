"""Client-side request pacing so free-tier limits are rarely hit."""

from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable


class QuotaExhausted(Exception):
    """The provider's request budget is used up; stop and resume later (results are cached)."""


class RateLimiter:
    """Spaces requests at least 60/rpm seconds apart and stops after `rpd` requests.

    ponytail: rpd counts this process only, not other runs earlier the same day; the provider's
    own 429 (mapped to QuotaExhausted by LLMClient) is the backstop.
    """

    def __init__(
        self,
        rpm: int,
        rpd: int | None,
        *,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        self._interval = 60.0 / rpm
        self._rpd = rpd
        self._clock = clock
        self._sleep = sleep
        self._next_at = float("-inf")
        self._used = 0
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        async with self._lock:
            if self._rpd is not None and self._used >= self._rpd:
                raise QuotaExhausted(f"daily budget of {self._rpd} requests used")
            now = self._clock()
            if self._next_at > now:
                await self._sleep(self._next_at - now)
                now = self._next_at
            self._next_at = now + self._interval
            self._used += 1
