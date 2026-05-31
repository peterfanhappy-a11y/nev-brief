"""Summarizer E2E — local Postgres + auth-fail fallback to verify pipeline shape."""
from __future__ import annotations

import json
import os
import subprocess
import sys
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
    pytest.mark.integration,
    pytest.mark.skipif(not _db_reachable(), reason="local Postgres not reachable"),
]


@pytest.fixture
def test_source_id():
    name = f"summarizer-e2e-{uuid4().hex[:8]}"
    with psycopg.connect(LOCAL_DB) as conn, conn.cursor() as cur:
        cur.execute(
            """INSERT INTO sources (name, type, url, authority, locale, category, enabled)
               VALUES (%s, 'rss', 'https://test.example/feed', 8, 'zh', 'media', true)
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


def _insert_test_data(conn, source_id):
    """Insert 30 raw + 30 processed across 10 clusters."""
    now = datetime.now(timezone.utc)
    cluster_ids: dict[int, str] = {i: str(uuid4()) for i in range(10)}
    with conn.cursor() as cur:
        for i in range(30):
            cluster_idx = i // 3
            cur.execute(
                """INSERT INTO articles_raw
                   (source_id, title, url, content, published_at, status)
                   VALUES (%s, %s, %s, %s, %s, 'done')
                   RETURNING id;""",
                (source_id, f"测试 #{i}",
                 f"https://test.example/a/{uuid4().hex[:12]}",
                 f"比亚迪销量第{i}号 cluster{cluster_idx}", now),
            )
            raw_id = cur.fetchone()[0]
            cur.execute(
                """INSERT INTO articles_processed
                   (raw_id, title, clean_text, language, brands, models, topics,
                    importance_score, cluster_id, simhash, status)
                   VALUES (%s, %s, %s, 'zh', %s, %s, %s, %s, %s, %s, 'done');""",
                (raw_id, f"测试 #{i}", f"比亚迪 cluster{cluster_idx}",
                 ["BYD"], [], ["new_car"], 50.0 + cluster_idx,
                 cluster_ids[cluster_idx], 1234567 + i),
            )
    conn.commit()
    return cluster_ids


def test_summarizer_e2e_pipeline_shape(test_source_id):
    """Pipeline reaches daily_briefs even when DeepSeek auth-fails (fail-safe)."""
    with psycopg.connect(LOCAL_DB) as conn:
        _insert_test_data(conn, test_source_id)

    env = {**os.environ, "DATABASE_URL": LOCAL_DB,
           "DEEPSEEK_API_KEY": "fake-force-failure"}
    today = date.today().isoformat()
    result = subprocess.run(
        [sys.executable, "-m", "nev_summarizer", "run", "--date", today, "--top-n", "10"],
        env=env, capture_output=True, text=True, timeout=120,
    )
    assert result.returncode == 0, f"CLI failed: stdout={result.stdout}\nstderr={result.stderr}"
    assert "OK brief=" in result.stdout

    with psycopg.connect(LOCAL_DB) as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT candidates FROM daily_briefs WHERE brief_date = %s;",
            (date.today(),),
        )
        row = cur.fetchone()
        assert row is not None, "daily_briefs row missing"
        candidates = row[0]
        if isinstance(candidates, (str, bytes)):
            candidates = json.loads(candidates)
        assert isinstance(candidates, list)
        assert len(candidates) == 0, (
            f"expected 0 candidates with fake DeepSeek key, got {len(candidates)}"
        )
