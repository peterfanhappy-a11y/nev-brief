import asyncio
import time

import pytest

from nev_crawler.rate_limiter import DomainRateLimiter


@pytest.mark.asyncio
async def test_single_domain_enforces_qps():
    limiter = DomainRateLimiter(qps_per_domain=2.0, jitter=0)
    start = time.monotonic()
    for _ in range(4):
        await limiter.acquire("example.com")
    elapsed = time.monotonic() - start
    # 4 calls at 2 QPS = 3 waits of 0.5s = ~1.5s; allow ±0.2s
    assert 1.3 <= elapsed <= 2.0


@pytest.mark.asyncio
async def test_different_domains_independent():
    limiter = DomainRateLimiter(qps_per_domain=1.0, jitter=0)
    start = time.monotonic()
    await limiter.acquire("a.com")
    await limiter.acquire("b.com")
    await limiter.acquire("c.com")
    elapsed = time.monotonic() - start
    assert elapsed < 0.2  # 不同域独立，不应有等待


def test_qps_zero_rejected():
    with pytest.raises(ValueError):
        DomainRateLimiter(qps_per_domain=0)
