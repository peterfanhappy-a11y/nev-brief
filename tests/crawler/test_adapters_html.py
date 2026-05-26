from pathlib import Path
from uuid import uuid4

import pytest
import respx
import httpx

from nev_crawler.adapters.html import HTMLAdapter

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.mark.asyncio
@respx.mock
async def test_html_adapter_extracts_with_selectors():
    respx.get("https://www.autohome.com.cn/news/").mock(
        return_value=httpx.Response(
            200,
            text=(FIXTURES / "page_autohome.html").read_text(encoding="utf-8"),
            headers={"content-type": "text/html"},
        )
    )
    adapter = HTMLAdapter()
    src = {
        "id": str(uuid4()),
        "name": "汽车之家资讯",
        "url": "https://www.autohome.com.cn/news/",
        "extra": {
            "list_selector": ".article-pic-list li",
            "title_selector": ".article-content h3 a",
            "link_selector": ".article-content h3 a",
            "link_attr": "href",
            "time_selector": ".fn-clear .fn-right",
        },
    }
    result = await adapter.fetch(src)
    assert result.ok
    assert len(result.articles) == 2
    assert result.articles[0].title == "小鹏 G9 改款发布"
    assert result.articles[0].url == "https://www.autohome.com.cn/news/202605/1.html"


@pytest.mark.asyncio
@respx.mock
async def test_html_adapter_missing_selectors_returns_error():
    respx.get("https://x.test/").mock(return_value=httpx.Response(200, text="<html></html>"))
    adapter = HTMLAdapter()
    result = await adapter.fetch({"id": str(uuid4()), "name": "x", "url": "https://x.test/", "extra": {}})
    assert not result.ok
