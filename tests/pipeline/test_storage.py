"""Unit tests for nev_pipeline.storage — mocks psycopg.Connection."""
from __future__ import annotations

from unittest.mock import MagicMock

from nev_pipeline.storage import (
    claim_pending,
    load_recent_processed,
    mark_raw_done,
    mark_raw_failed,
    upsert_processed,
)


def _mock_conn(rows: list | None = None) -> tuple[MagicMock, MagicMock]:
    conn = MagicMock()
    cur = MagicMock()
    cur.__enter__ = lambda s: cur
    cur.__exit__ = lambda *a: None
    cur.fetchall.return_value = rows or []
    cur.description = []
    conn.cursor.return_value = cur
    return conn, cur


def test_claim_pending_uses_skip_locked_atomic() -> None:
    conn, cur = _mock_conn(rows=[])
    claim_pending(conn, limit=10)
    sql_called = cur.execute.call_args[0][0]
    assert "UPDATE articles_raw" in sql_called
    assert "FOR UPDATE SKIP LOCKED" in sql_called
    assert "RETURNING" in sql_called
    params = cur.execute.call_args[0][1]
    assert params == (10,)


def test_claim_pending_returns_dicts() -> None:
    cur_rows = [("id-1", "src-1", "title", "content", "hash", "url", None)]
    conn = MagicMock()
    cur = MagicMock()
    cur.__enter__ = lambda s: cur
    cur.__exit__ = lambda *a: None
    cur.fetchall.return_value = cur_rows
    col_names = ("id", "source_id", "title", "content", "content_hash", "url", "published_at")
    cur.description = [MagicMock() for _ in col_names]
    for c, name in zip(cur.description, col_names, strict=True):
        c.name = name
    conn.cursor.return_value = cur
    out = claim_pending(conn, limit=10)
    assert out[0]["title"] == "title"
    assert out[0]["url"] == "url"


def test_upsert_processed_uses_on_conflict_raw_id() -> None:
    conn, cur = _mock_conn()
    upsert_processed(
        conn,
        {
            "raw_id": "r1",
            "source_id": "s1",
            "title": "t",
            "clean_text": "c",
            "simhash": 12345,
            "cluster_id": "cl1",
            "brands": ["BYD"],
            "models": [],
            "topics": [],
            "people": [],
            "importance_score": 50.0,
            "language": "zh",
        },
    )
    sql = cur.execute.call_args[0][0]
    assert "INSERT INTO articles_processed" in sql
    assert "ON CONFLICT (raw_id) DO UPDATE" in sql


def test_mark_raw_done_updates_status() -> None:
    conn, cur = _mock_conn()
    mark_raw_done(conn, "r1")
    sql = cur.execute.call_args[0][0]
    assert "UPDATE articles_raw" in sql
    assert "status='done'" in sql or "status = 'done'" in sql


def test_mark_raw_failed_updates_status() -> None:
    conn, cur = _mock_conn()
    mark_raw_failed(conn, "r1", "some error")
    sql = cur.execute.call_args[0][0]
    assert "UPDATE articles_raw" in sql
    assert "failed" in sql


def test_load_recent_processed_window() -> None:
    conn, cur = _mock_conn(rows=[])
    cur.description = []
    load_recent_processed(conn, hours=24)
    sql = cur.execute.call_args[0][0]
    assert "articles_processed" in sql
    params = cur.execute.call_args[0][1]
    assert params == (24,) or any("24" in str(p) for p in params)
