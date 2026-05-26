from pathlib import Path

import pytest
import respx
import httpx

from nev_crawler.robots import RobotsChecker

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.mark.asyncio
@respx.mock
async def test_robots_blocks_all():
    respx.get("https://blocked.test/robots.txt").mock(
        return_value=httpx.Response(200, text=(FIXTURES / "robots_disallow_all.txt").read_text())
    )
    checker = RobotsChecker(user_agent="NEV-Brief-Bot/1.0")
    assert await checker.is_allowed("https://blocked.test/article/1") is False


@pytest.mark.asyncio
@respx.mock
async def test_robots_allows_news_path():
    respx.get("https://ok.test/robots.txt").mock(
        return_value=httpx.Response(200, text=(FIXTURES / "robots_allow_news.txt").read_text())
    )
    checker = RobotsChecker(user_agent="NEV-Brief-Bot/1.0")
    assert await checker.is_allowed("https://ok.test/news/123") is True
    assert await checker.is_allowed("https://ok.test/private/456") is False


@pytest.mark.asyncio
@respx.mock
async def test_robots_404_treats_as_allowed():
    respx.get("https://norobots.test/robots.txt").mock(return_value=httpx.Response(404))
    checker = RobotsChecker(user_agent="NEV-Brief-Bot/1.0")
    assert await checker.is_allowed("https://norobots.test/x") is True


@pytest.mark.asyncio
@respx.mock
async def test_robots_caches_per_host():
    route = respx.get("https://cached.test/robots.txt").mock(
        return_value=httpx.Response(200, text="User-agent: *\nAllow: /")
    )
    checker = RobotsChecker(user_agent="NEV-Brief-Bot/1.0")
    await checker.is_allowed("https://cached.test/a")
    await checker.is_allowed("https://cached.test/b")
    await checker.is_allowed("https://cached.test/c")
    assert route.call_count == 1  # 仅一次拉取
