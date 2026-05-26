from pathlib import Path
from uuid import uuid4

import pytest
import respx
import httpx

from nev_crawler.adapters.rss import RSSAdapter

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.mark.asyncio
@respx.mock
async def test_rss_adapter_parses_feed():
    respx.get("https://36kr.com/feed-newsflash").mock(
        return_value=httpx.Response(
            200,
            content=(FIXTURES / "feed_36kr.xml").read_bytes(),
            headers={"content-type": "application/xml"},
        )
    )
    adapter = RSSAdapter()
    src = {
        "id": str(uuid4()),
        "name": "36氪汽车",
        "url": "https://36kr.com/feed-newsflash",
    }
    result = await adapter.fetch(src)
    assert result.ok
    assert len(result.articles) == 2
    assert result.articles[0].title == "比亚迪 5 月销量突破 50 万"
    assert str(result.articles[0].source_id) == src["id"]


@pytest.mark.asyncio
@respx.mock
async def test_rss_adapter_http_error_returns_error():
    respx.get("https://broken.test/feed").mock(return_value=httpx.Response(500))
    adapter = RSSAdapter()
    result = await adapter.fetch({"id": str(uuid4()), "name": "x", "url": "https://broken.test/feed"})
    assert not result.ok
    assert result.error is not None
    assert result.articles == []
