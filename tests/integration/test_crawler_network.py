"""真网络 smoke — @pytest.mark.network 默认 skip，CI 关闭。

跑法：uv run pytest tests/integration/test_crawler_network.py -m network
"""
import pytest
from uuid import uuid4

from nev_crawler.adapters.rss import RSSAdapter


@pytest.mark.network
@pytest.mark.asyncio
async def test_36kr_rss_returns_some_items():
    adapter = RSSAdapter()
    src = {
        "id": str(uuid4()),
        "name": "36氪汽车",
        "url": "https://36kr.com/feed-newsflash",
    }
    result = await adapter.fetch(src)
    # 至少有返回（成功或失败，但接口可达）
    assert result is not None
    if result.ok:
        assert len(result.articles) > 0


@pytest.mark.network
@pytest.mark.asyncio
async def test_electrek_rss_returns_some_items():
    adapter = RSSAdapter()
    src = {
        "id": str(uuid4()),
        "name": "Electrek",
        "url": "https://electrek.co/feed/",
    }
    result = await adapter.fetch(src)
    if result.ok:
        assert len(result.articles) > 0
