"""T7 tests — daily_briefs UPSERT/fetch with mocked psycopg."""
from __future__ import annotations

import json
from datetime import date
from typing import Any
from unittest.mock import MagicMock

from nev_summarizer.storage import fetch_daily_brief, upsert_daily_brief


def _mock_conn(fetchone_result: Any = None) -> tuple[MagicMock, MagicMock]:
    conn = MagicMock()
    cur = MagicMock()
    cur.__enter__ = lambda s: cur
    cur.__exit__ = lambda *a: None
    cur.fetchone.return_value = fetchone_result
    conn.cursor.return_value = cur
    return conn, cur


def test_upsert_calls_on_conflict() -> None:
    conn, cur = _mock_conn()
    candidates = [{"rank": 1, "cluster_id": "cl1", "title": "t", "summary": "s"}]
    upsert_daily_brief(conn, date(2026, 5, 30), candidates)
    sql = cur.execute.call_args[0][0]
    assert "INSERT INTO daily_briefs" in sql
    assert "ON CONFLICT (brief_date) DO UPDATE" in sql
    args = cur.execute.call_args[0][1]
    assert args[0] == date(2026, 5, 30)
    assert json.loads(args[1]) == candidates


def test_upsert_preserves_unicode() -> None:
    conn, cur = _mock_conn()
    candidates = [{"title": "比亚迪", "summary": "中文摘要"}]
    upsert_daily_brief(conn, date(2026, 5, 30), candidates)
    params = cur.execute.call_args[0][1]
    parsed = json.loads(params[1])
    assert parsed[0]["title"] == "比亚迪"


def test_fetch_returns_none_when_missing() -> None:
    conn, _ = _mock_conn(fetchone_result=None)
    assert fetch_daily_brief(conn, date(2026, 5, 30)) is None


def test_fetch_parses_json_string() -> None:
    conn, _ = _mock_conn(fetchone_result=(json.dumps([{"rank": 1}]),))
    assert fetch_daily_brief(conn, date(2026, 5, 30)) == [{"rank": 1}]


def test_fetch_passes_through_list() -> None:
    conn, _ = _mock_conn(fetchone_result=([{"rank": 1}],))
    assert fetch_daily_brief(conn, date(2026, 5, 30)) == [{"rank": 1}]
