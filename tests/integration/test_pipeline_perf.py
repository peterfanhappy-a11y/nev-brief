"""Pipeline perf — 100 articles < 5 min with mocked DeepSeek (fake key → fallback path).

Spec 验收门 5: 100 篇端到端 < 5 分钟 (300 s).

Uses dict-fallback path (fake DEEPSEEK_API_KEY) to avoid real network calls — this
measures pure local processing speed (text clean + simhash + dict entity extract +
scoring + clustering + DB writes).
"""
from __future__ import annotations

import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from uuid import uuid4

import psycopg
import pytest

LOCAL_DB = os.environ.get(
    "PIPELINE_TEST_DB_URL",
    "postgresql://nev:nev_local_dev@localhost:54322/nev_brief",
)


def _db_reachable() -> bool:
    try:
        with psycopg.connect(LOCAL_DB, connect_timeout=2):
            return True
    except Exception:  # noqa: BLE001
        return False


pytestmark = [
    pytest.mark.perf,
    pytest.mark.skipif(not _db_reachable(), reason="local Postgres not reachable"),
]


@pytest.fixture
def perf_source_id() -> str:
    name = f"pipeline-perf-{uuid4().hex[:8]}"
    with psycopg.connect(LOCAL_DB) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO sources (name, type, url, authority, locale, category, enabled)
                   VALUES (%s, 'rss', 'https://test.example/feed', 7, 'zh', 'media', true)
                   RETURNING id;""",
                (name,),
            )
            sid = cur.fetchone()[0]
        conn.commit()
    yield sid
    with psycopg.connect(LOCAL_DB) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM articles_processed WHERE raw_id IN "
                "(SELECT id FROM articles_raw WHERE source_id=%s);",
                (sid,),
            )
            cur.execute("DELETE FROM articles_raw WHERE source_id=%s;", (sid,))
            cur.execute("DELETE FROM sources WHERE id=%s;", (sid,))
        conn.commit()


def test_100_articles_under_5min(perf_source_id: str) -> None:
    """spec 验收门 5: 100 篇端到端 < 5 分钟 (使用 fallback 路径，等价 mock DeepSeek)"""
    with psycopg.connect(LOCAL_DB) as conn:
        with conn.cursor() as cur:
            for i in range(100):
                cur.execute(
                    """INSERT INTO articles_raw
                       (source_id, title, url, content, published_at, status)
                       VALUES (%s, %s, %s, %s, %s, 'pending');""",
                    (
                        perf_source_id,
                        f"性能测试 #{i} BYD 比亚迪 销量 增长",
                        f"https://perf.test/{uuid4().hex[:12]}",
                        "比亚迪 5 月销量同比增长 30%，多款新车型上市",
                        datetime.now(timezone.utc),
                    ),
                )
        conn.commit()

    # Force fallback (no real DeepSeek calls) → pure local processing speed.
    env = {
        **os.environ,
        "DEEPSEEK_API_KEY": "fake-key-force-fallback",
        "DATABASE_URL": LOCAL_DB,
    }
    start = time.time()
    result = subprocess.run(
        [sys.executable, "-m", "nev_pipeline", "run", "--limit", "100"],
        env=env,
        capture_output=True,
        text=True,
        timeout=320,
        check=False,
    )
    elapsed = time.time() - start
    assert result.returncode == 0, f"CLI failed: {result.stderr}"
    assert elapsed < 300, f"took {elapsed:.1f}s, want <300s. stdout={result.stdout}"
