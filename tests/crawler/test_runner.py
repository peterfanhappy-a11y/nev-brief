from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from nev_crawler.adapters.base import FetchResult
from nev_crawler.runner import crawl_sources
from python.content import ArticleRaw


def _src(name: str, type_: str = "rss") -> dict:
    return {
        "id": str(uuid4()),
        "name": name,
        "type": type_,
        "url": f"https://{name}.test/",
        "enabled": True,
        "extra": {},
    }


@pytest.mark.asyncio
async def test_crawl_sources_isolates_failures():
    src_a = _src("a")
    src_b = _src("b")

    # Single registered adapter, but mock its fetch to return ok for a, raise for b
    fetch_mock = AsyncMock()

    async def side_effect(s):
        if s["name"] == "a":
            return FetchResult(articles=[ArticleRaw(source_id=src_a["id"], url="https://a.test/1")])
        raise RuntimeError("network down")

    fetch_mock.side_effect = side_effect

    adapter = MagicMock()
    adapter.fetch = fetch_mock

    # Disable robots check and rate limit for the test by passing mocks
    robots = MagicMock()
    robots.is_allowed = AsyncMock(return_value=True)

    limiter = MagicMock()
    limiter.acquire = AsyncMock(return_value=None)

    results = await crawl_sources(
        sources=[src_a, src_b],
        adapter_registry={"rss": adapter},
        robots=robots,
        rate_limiter=limiter,
    )
    # Both finish; a succeeds, b reports error
    assert len(results) == 2
    a_result = next(r for r in results if r["source_name"] == "a")
    b_result = next(r for r in results if r["source_name"] == "b")
    assert a_result["ok"] is True
    assert b_result["ok"] is False


@pytest.mark.asyncio
async def test_crawl_sources_skips_disabled():
    src_disabled = _src("disabled")
    src_disabled["enabled"] = False

    adapter = MagicMock()
    adapter.fetch = AsyncMock(return_value=FetchResult(articles=[]))

    robots = MagicMock()
    robots.is_allowed = AsyncMock(return_value=True)
    limiter = MagicMock()
    limiter.acquire = AsyncMock(return_value=None)

    results = await crawl_sources(
        [src_disabled],
        adapter_registry={"rss": adapter},
        robots=robots,
        rate_limiter=limiter,
    )
    assert results == []
    adapter.fetch.assert_not_called()
