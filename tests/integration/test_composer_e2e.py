"""Composer E2E — local Postgres, generates a delivery, verifies row exists."""
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
def test_setup():
    """Insert 1 subscriber + 1 daily_brief, yield ids, cleanup at end."""
    today = date.today()
    email = f"composer-e2e-{uuid4().hex[:8]}@example.com"
    candidates = [
        {
            "rank": i + 1,
            "cluster_id": str(uuid4()),
            "title": f"测试新闻 {i+1}",
            "summary": f"测试摘要内容 {i+1}",
            "brands": ["BYD"] if i % 2 == 0 else ["Tesla"],
            "topics": ["new_car"] if i < 3 else ["overseas"] if i == 3 else ["tech"],
            "source_links": [{"name": "36氪", "url": f"https://test/{i}"}],
            "global_importance": 80.0 - i * 5,
            "key_data": {"type": "none", "values": {}},
            "primary_source": "36氪",
            "source_count": 1,
        }
        for i in range(5)
    ]

    sub_id: str | None = None
    with psycopg.connect(LOCAL_DB) as conn, conn.cursor() as cur:
        cur.execute(
            """INSERT INTO subscribers (email, status, plan, push_time, push_channel)
               VALUES (%s, 'active', 'free', '08:00', 'email') RETURNING id::text;""",
            (email,),
        )
        sub_id = cur.fetchone()[0]
        cur.execute(
            """INSERT INTO subscriber_preferences (subscriber_id, brands, topics, regions)
               VALUES (%s, %s, %s, '{}');""",
            (sub_id, ["BYD", "Tesla"], ["new_car", "sales"]),
        )
        cur.execute(
            """INSERT INTO daily_briefs (brief_date, candidates)
               VALUES (%s, %s::jsonb)
               ON CONFLICT (brief_date) DO UPDATE SET candidates = EXCLUDED.candidates;""",
            (today, json.dumps(candidates)),
        )
        conn.commit()

    yield {"sub_id": sub_id, "email": email, "brief_date": today}

    # Cleanup
    with psycopg.connect(LOCAL_DB) as conn, conn.cursor() as cur:
        cur.execute("DELETE FROM deliveries WHERE subscriber_id = %s;", (sub_id,))
        cur.execute("DELETE FROM subscribers WHERE id = %s;", (sub_id,))
        # Don't delete daily_brief if it pre-existed; only delete our fixture
        # (test_setup uses today, which is likely empty in test DB)
        cur.execute(
            "DELETE FROM daily_briefs WHERE brief_date = %s AND candidates::text LIKE %s;",
            (today, "%测试新闻%"),
        )
        conn.commit()


def test_composer_e2e_generates_delivery(test_setup):
    """python -m nev_composer run --date <today> --subscriber <email> → deliveries row exists."""
    today = test_setup["brief_date"].isoformat()
    email = test_setup["email"]

    env = {**os.environ, "DATABASE_URL": LOCAL_DB}
    result = subprocess.run(
        [sys.executable, "-m", "nev_composer", "run",
         "--date", today, "--subscriber", email],
        env=env, capture_output=True, text=True, timeout=60,
    )
    assert result.returncode == 0, f"CLI failed: stdout={result.stdout}\nstderr={result.stderr}"
    assert "composed=1" in result.stdout, f"expected composed=1 in: {result.stdout}"

    with psycopg.connect(LOCAL_DB) as conn, conn.cursor() as cur:
        cur.execute(
            """SELECT content_html, content_text, status, selected_items
               FROM deliveries
               WHERE subscriber_id = %s AND brief_date = %s;""",
            (test_setup["sub_id"], test_setup["brief_date"]),
        )
        row = cur.fetchone()
    assert row is not None, "deliveries row missing"
    html, text, status, selected = row
    assert "测试新闻" in html
    assert "测试新闻" in text
    assert status == "pending"
    # selected_items should be list of cluster_id strings (jsonb may auto-parse)
    parsed = json.loads(selected) if isinstance(selected, (str, bytes)) else selected
    assert isinstance(parsed, list)
    assert len(parsed) <= 10
