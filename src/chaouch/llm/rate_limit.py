from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable


class QuotaExhausted(Exception):
    pass


class RateLimiter:
    # ponytail: rpd counts this process only; the provider's own 429 is the backstop.

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
