"""Per-domain rate limiter — 1 QPS + jitter by default."""
from __future__ import annotations

import asyncio
import random
import time
from collections import defaultdict


class DomainRateLimiter:
    """Token bucket simplified: per-domain min interval between calls.

    spec §5.2.3: 每域 ≤ 1 QPS + 0.5-2s 随机抖动
    """

    def __init__(self, qps_per_domain: float = 1.0, jitter: float = 1.5):
        if qps_per_domain <= 0:
            raise ValueError("qps_per_domain must be positive")
        self._min_interval = 1.0 / qps_per_domain
        self._jitter = jitter
        self._last_call: dict[str, float] = defaultdict(float)
        self._locks: dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)

    async def acquire(self, domain: str) -> None:
        async with self._locks[domain]:
            now = time.monotonic()
            last = self._last_call[domain]
            elapsed = now - last
            wait = self._min_interval - elapsed
            if wait > 0:
                jitter = random.uniform(0, self._jitter) if self._jitter > 0 else 0
                await asyncio.sleep(wait + jitter)
            self._last_call[domain] = time.monotonic()
