"""Pipeline E2E — needs local Docker Postgres + migrations 0001-0007 applied.

Inserts a unique test source + 20 raw articles, runs the pipeline CLI as a subprocess,
verifies articles_processed is populated with cluster_id / importance_score / simhash,
then cleans up.

If schema is out of date (missing simhash column etc.), pytest will fail with a clear
psycopg error — apply migrations via:
    docker exec -i nev-postgres psql -U nev -d nev_brief \\
        < infra/supabase/migrations/0007_articles_processed_simhash_unique.sql
"""
from __future__ import annotations

import os
import subprocess
import sys
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
    pytest.mark.integration,
    pytest.mark.skipif(not _db_reachable(), reason="local Postgres not reachable"),
]


@pytest.fixture
def test_source_id() -> str:
    name = f"pipeline-e2e-{uuid4().hex[:8]}"
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
    # cleanup — order matters because of FK from articles_processed→articles_raw→sources
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


def _insert_n_raw(conn: psycopg.Connection, source_id: str, n: int) -> list[str]:
    """Insert N pending articles with brand-rich content for dict fallback to work."""
    raw_ids: list[str] = []
    seeds = [
        ("比亚迪", "BYD 销量大增", "5月销量同比增长 30%，新车型海豹06上市"),
        ("特斯拉", "Tesla Model Y 焕新", "Model Y 焕新版6月起交付 起售26.4万元"),
        ("蔚来", "NIO 发布新车", "蔚来 ET9 旗舰上市 售价 78.8 万元 续航 700 公里"),
        ("小鹏", "XPeng 智驾升级", "小鹏 G9 全新 XNGP 城市智驾推送 覆盖 200 城"),
        ("理想", "Li Auto 销量", "理想 5 月交付 4.1 万辆 L7 占比 35%"),
    ]
    with conn.cursor() as cur:
        for i in range(n):
            seed = seeds[i % len(seeds)]
            cur.execute(
                """INSERT INTO articles_raw
                   (source_id, title, url, content, published_at, status)
                   VALUES (%s, %s, %s, %s, %s, 'pending')
                   RETURNING id;""",
                (
                    source_id,
                    f"{seed[1]} #{i}",
                    f"https://test.example/article/{uuid4().hex[:12]}",
                    seed[2] + f" 第{i}号样本",
                    datetime.now(timezone.utc),
                ),
            )
            raw_ids.append(cur.fetchone()[0])
    conn.commit()
    return raw_ids


def test_pipeline_e2e_20_articles(test_source_id: str) -> None:
    """Insert 20 raw → run pipeline → verify processed table populated correctly."""
    with psycopg.connect(LOCAL_DB) as conn:
        raw_ids = _insert_n_raw(conn, test_source_id, 20)

    # Force fallback path so test doesn't need real DeepSeek API key.
    # DATABASE_URL override lets the CLI hit local Docker Postgres instead of Supabase.
    env = {
        **os.environ,
        "DEEPSEEK_API_KEY": "fake-key-force-fallback",
        "DATABASE_URL": LOCAL_DB,
    }
    # Subprocess intentionally — exercises real CLI entry point end-to-end.
    result = subprocess.run(
        [sys.executable, "-m", "nev_pipeline", "run", "--limit", "20"],
        env=env,
        capture_output=True,
        text=True,
        timeout=180,
        check=False,
    )
    assert result.returncode == 0, (
        f"CLI failed: stdout={result.stdout}\nstderr={result.stderr}"
    )

    # Verify
    with psycopg.connect(LOCAL_DB) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) FROM articles_processed WHERE raw_id = ANY(%s);",
                (raw_ids,),
            )
            count = cur.fetchone()[0]
            assert count == 20, f"want 20 processed rows, got {count}"

            cur.execute(
                """SELECT cluster_id IS NOT NULL, importance_score, simhash
                   FROM articles_processed WHERE raw_id = ANY(%s);""",
                (raw_ids,),
            )
            for has_cluster, score, sh in cur.fetchall():
                assert has_cluster, "cluster_id is null"
                assert score and score > 0, f"importance_score={score}"
                assert sh is not None, "simhash is null"

            # And that raw articles are marked done
            cur.execute(
                "SELECT status FROM articles_raw WHERE id = ANY(%s);", (raw_ids,)
            )
            statuses = {row[0] for row in cur.fetchall()}
            assert statuses == {"done"}, f"want all done, got {statuses}"
