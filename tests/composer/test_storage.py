import json
from datetime import date
from unittest.mock import MagicMock

import pytest

from nev_composer.storage import (
    ActiveSubscriber, fetch_daily_brief_candidates,
    fetch_active_subscribers, upsert_delivery,
)


def _mock_conn(fetchone=None, fetchall=None):
    conn = MagicMock()
    cur = MagicMock()
    cur.__enter__ = lambda s: cur
    cur.__exit__ = lambda *a: None
    cur.fetchone.return_value = fetchone
    cur.fetchall.return_value = fetchall or []
    conn.cursor.return_value = cur
    return conn, cur


def test_fetch_candidates_returns_none_when_no_brief():
    conn, _ = _mock_conn(fetchone=None)
    assert fetch_daily_brief_candidates(conn, date(2026, 5, 31)) is None


def test_fetch_candidates_parses_jsonb_string():
    payload = [{"rank": 1, "cluster_id": "cl1"}]
    conn, _ = _mock_conn(fetchone=(json.dumps(payload),))
    assert fetch_daily_brief_candidates(conn, date(2026, 5, 31)) == payload


def test_fetch_candidates_passes_through_list():
    payload = [{"rank": 1}]
    conn, _ = _mock_conn(fetchone=(payload,))
    assert fetch_daily_brief_candidates(conn, date(2026, 5, 31)) == payload


def test_fetch_active_subscribers_returns_dataclass():
    rows = [
        ("uuid-1", "alice@x.com", "08:00:00", "tok-1", ["BYD"], ["new_car"]),
        ("uuid-2", "bob@x.com",   "08:00:00", "tok-2", [], []),
    ]
    conn, cur = _mock_conn(fetchall=rows)
    out = fetch_active_subscribers(conn)
    sql = cur.execute.call_args[0][0]
    assert "subscribers" in sql
    assert "LEFT JOIN subscriber_preferences" in sql
    assert "status = 'active'" in sql
    assert len(out) == 2
    assert isinstance(out[0], ActiveSubscriber)
    assert out[0].email == "alice@x.com"
    assert out[0].pref_brands == ["BYD"]
    assert out[1].pref_brands == []


def test_upsert_delivery_uses_on_conflict():
    conn, cur = _mock_conn()
    upsert_delivery(
        conn, "sub-1", date(2026, 5, 31),
        content_html="<h1>x</h1>", content_text="x",
        selected_items=["cl1", "cl2"],
    )
    sql = cur.execute.call_args[0][0]
    assert "INSERT INTO deliveries" in sql
    assert "ON CONFLICT (subscriber_id, brief_date) DO UPDATE" in sql
    args = cur.execute.call_args[0][1]
    assert args[0] == "sub-1"
    assert args[1] == date(2026, 5, 31)
    assert args[2] == "<h1>x</h1>"
    assert json.loads(args[4]) == ["cl1", "cl2"]


def test_upsert_delivery_unicode():
    conn, cur = _mock_conn()
    upsert_delivery(conn, "sub-1", date(2026, 5, 31), "<h1>比亚迪</h1>", "比亚迪", [])
    args = cur.execute.call_args[0][1]
    assert "比亚迪" in args[2]
    assert "比亚迪" in args[3]
