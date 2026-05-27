"""端到端集成 — mock 5 个不同信源 → runner → 验证失败隔离 + robots 屏蔽。"""
import os
from pathlib import Path
from uuid import uuid4

import pytest
import psycopg
import respx
import httpx

from nev_crawler.runner import crawl_sources

FIXTURES = Path(__file__).parent.parent / "crawler" / "fixtures"


@pytest.fixture
def db():
    url = os.environ.get("DATABASE_URL", "postgresql://nev:nev_local_dev@localhost:54322/nev_brief")
    conn = psycopg.connect(url)
    yield conn
    conn.close()


def _seed_source(db, name: str, type_: str, url: str, locale: str = "zh") -> str:
    sid = str(uuid4())
    with db.cursor() as cur:
        cur.execute(
            """INSERT INTO sources (id, name, type, url, authority, locale, category)
               VALUES (%s, %s, %s, %s, 5, %s, 'media')""",
            (sid, name, type_, url, locale),
        )
    db.commit()
    return sid


@pytest.mark.integration
@pytest.mark.asyncio
@respx.mock
async def test_crawl_5_sources_end_to_end(db):
    # 准备 5 个源：3 个成功 + 1 个 500 + 1 个 robots.txt 阻止
    feed_xml = (FIXTURES / "feed_36kr.xml").read_bytes()

    s1 = _seed_source(db, f"src1-{uuid4()}", "rss", "https://ok-a.test/feed")
    respx.get("https://ok-a.test/feed").mock(return_value=httpx.Response(200, content=feed_xml))
    respx.get("https://ok-a.test/robots.txt").mock(return_value=httpx.Response(404))

    s2 = _seed_source(db, f"src2-{uuid4()}", "rss", "https://ok-b.test/feed")
    respx.get("https://ok-b.test/feed").mock(return_value=httpx.Response(200, content=feed_xml))
    respx.get("https://ok-b.test/robots.txt").mock(return_value=httpx.Response(404))

    s3 = _seed_source(db, f"src3-{uuid4()}", "rss", "https://ok-c.test/feed")
    respx.get("https://ok-c.test/feed").mock(return_value=httpx.Response(200, content=feed_xml))
    respx.get("https://ok-c.test/robots.txt").mock(return_value=httpx.Response(404))

    s4 = _seed_source(db, f"src4-{uuid4()}", "rss", "https://broken.test/feed")
    respx.get("https://broken.test/feed").mock(return_value=httpx.Response(500))
    respx.get("https://broken.test/robots.txt").mock(return_value=httpx.Response(404))

    s5 = _seed_source(db, f"src5-{uuid4()}", "rss", "https://blocked.test/feed")
    respx.get("https://blocked.test/robots.txt").mock(
        return_value=httpx.Response(200, text="User-agent: *\nDisallow: /")
    )

    sources = []
    for sid, name, url in [
        (s1, "src1", "https://ok-a.test/feed"),
        (s2, "src2", "https://ok-b.test/feed"),
        (s3, "src3", "https://ok-c.test/feed"),
        (s4, "src4", "https://broken.test/feed"),
        (s5, "src5", "https://blocked.test/feed"),
    ]:
        sources.append({"id": sid, "name": name, "type": "rss", "url": url, "enabled": True, "extra": {}})

    reports = await crawl_sources(sources)
    assert len(reports) == 5
    ok_count = sum(1 for r in reports if r["ok"])
    assert ok_count == 3  # 3 succeed, 1 server error, 1 robots blocked
    blocked_or_failed = sum(1 for r in reports if not r["ok"])
    assert blocked_or_failed == 2
