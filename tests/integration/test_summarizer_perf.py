"""Summarizer perf — 35 clusters < 90s with fail-safe path."""
from __future__ import annotations

import os
import subprocess
import sys
import time
from datetime import date, datetime, timezone
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
    except Exception:
        return False


pytestmark = [
    pytest.mark.perf,
    pytest.mark.skipif(not _db_reachable(), reason="local Postgres not reachable"),
]


@pytest.fixture
def perf_source_id():
    name = f"summarizer-perf-{uuid4().hex[:8]}"
    with psycopg.connect(LOCAL_DB) as conn, conn.cursor() as cur:
        cur.execute(
            """INSERT INTO sources (name, type, url, authority, locale, category, enabled)
               VALUES (%s, 'rss', 'https://perf.example/feed', 8, 'zh', 'media', true)
               RETURNING id;""",
            (name,),
        )
        sid = cur.fetchone()[0]
        conn.commit()
    yield sid
    with psycopg.connect(LOCAL_DB) as conn, conn.cursor() as cur:
        cur.execute("DELETE FROM daily_briefs WHERE brief_date = CURRENT_DATE;")
        cur.execute(
            """DELETE FROM articles_processed
               WHERE raw_id IN (SELECT id FROM articles_raw WHERE source_id=%s);""",
            (sid,),
        )
        cur.execute("DELETE FROM articles_raw WHERE source_id=%s;", (sid,))
        cur.execute("DELETE FROM sources WHERE id=%s;", (sid,))
        conn.commit()


def test_35_clusters_under_90s(perf_source_id):
    """Self-defined gate: 35 clusters end-to-end < 90s with fail-safe path."""
    now = datetime.now(timezone.utc)
    cluster_count = 35
    with psycopg.connect(LOCAL_DB) as conn, conn.cursor() as cur:
        for ci in range(cluster_count):
            cluster_id = str(uuid4())
            for ai in range(3):
                cur.execute(
                    """INSERT INTO articles_raw
                       (source_id, title, url, content, published_at, status)
                       VALUES (%s, %s, %s, %s, %s, 'done')
                       RETURNING id;""",
                    (perf_source_id, f"perf c{ci} a{ai}",
                     f"https://perf.test/{uuid4().hex[:12]}",
                     f"性能测试 cluster {ci} article {ai} BYD", now),
                )
                raw_id = cur.fetchone()[0]
                cur.execute(
                    """INSERT INTO articles_processed
                       (raw_id, title, clean_text, language, brands, models, topics,
                        importance_score, cluster_id, simhash, status)
                       VALUES (%s, %s, %s, 'zh', %s, %s, %s, %s, %s, %s, 'done');""",
                    (raw_id, f"perf c{ci} a{ai}", f"BYD cluster {ci}",
                     ["BYD"], [], ["new_car"], 50.0 + ci, cluster_id, ci * 1000 + ai),
                )
        conn.commit()

    env = {**os.environ, "DATABASE_URL": LOCAL_DB,
           "DEEPSEEK_API_KEY": "fake-force-failure"}
    today = date.today().isoformat()
    start = time.time()
    result = subprocess.run(
        [sys.executable, "-m", "nev_summarizer", "run",
         "--date", today, "--top-n", str(cluster_count)],
        env=env, capture_output=True, text=True, timeout=120,
    )
    elapsed = time.time() - start
    assert result.returncode == 0, f"CLI failed: {result.stderr}"
    assert elapsed < 90, f"took {elapsed:.1f}s, want <90s"
