from pathlib import Path
from uuid import uuid4

import pytest
import respx
import httpx

from nev_crawler.adapters.rsshub import RSSHubAdapter

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.mark.asyncio
@respx.mock
async def test_rsshub_adapter_prepends_base():
    # RSSHub fronts as RSS — feed_36kr fixture works
    respx.get("http://localhost:1200/weibo/user/2391758825").mock(
        return_value=httpx.Response(
            200,
            content=(FIXTURES / "feed_36kr.xml").read_bytes(),
        )
    )
    adapter = RSSHubAdapter(base_url="http://localhost:1200")
    src = {
        "id": str(uuid4()),
        "name": "比亚迪官方",
        "url": "/weibo/user/2391758825",
    }
    result = await adapter.fetch(src)
    assert result.ok
    assert len(result.articles) == 2


@pytest.mark.asyncio
async def test_rsshub_adapter_uses_env_base_url(monkeypatch):
    monkeypatch.setenv("RSSHUB_BASE_URL", "http://custom:9999")
    adapter = RSSHubAdapter()
    assert adapter.base_url == "http://custom:9999"
