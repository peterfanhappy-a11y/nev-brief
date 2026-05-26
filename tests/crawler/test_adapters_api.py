from pathlib import Path
from uuid import uuid4

import pytest
import respx
import httpx

from nev_crawler.adapters.api import APIAdapter

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.mark.asyncio
@respx.mock
async def test_api_adapter_parses_json():
    respx.get("https://api.example.com/news").mock(
        return_value=httpx.Response(200, text=(FIXTURES / "api_cpca.json").read_text(encoding="utf-8"))
    )
    adapter = APIAdapter()
    src = {
        "id": str(uuid4()),
        "name": "CPCA API",
        "url": "https://api.example.com/news",
        "extra": {
            "items_path": "items",
            "title_field": "title",
            "url_field": "url",
            "published_field": "publishedAt",
        },
    }
    result = await adapter.fetch(src)
    assert result.ok
    assert len(result.articles) == 2
    assert result.articles[0].title == "5 月乘用车上险数据"
