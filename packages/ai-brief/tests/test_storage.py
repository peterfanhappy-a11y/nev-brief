"""storage.py 单测 — 用 mock cursor 验证 row 映射 + rowcount 累加逻辑。
真实 DB 往返在 T12 E2E 验证。"""
from __future__ import annotations

from collections.abc import Sequence
from datetime import date
from typing import Any
from unittest.mock import MagicMock

from ai_brief import storage
from ai_brief.storage import AiArticle


def _mock_conn(
    fetch_rows: Sequence[tuple[Any, ...]] | None = None,
    rowcounts: Sequence[int] | None = None,
) -> tuple[MagicMock, MagicMock]:
    """构造一个 cursor 作为 context manager 的 mock 连接。"""
    cur = MagicMock()
    cur.fetchall.return_value = fetch_rows or []
    cur.fetchone.return_value = fetch_rows[0] if fetch_rows else None
    if rowcounts is not None:
        type(cur).rowcount = MagicMock()
        cur.rowcount = 0
        # execute 每次调用后设置 rowcount
        rc_iter = iter(rowcounts)
        def _exec(*_a: Any, **_k: Any) -> None:
            cur.rowcount = next(rc_iter)
        cur.execute.side_effect = _exec
    conn = MagicMock()
    conn.cursor.return_value.__enter__.return_value = cur
    conn.cursor.return_value.__exit__.return_value = False
    return conn, cur


def test_insert_articles_counts_new_rows() -> None:
    arts = [
        AiArticle("OpenAI", "en", 10, "https://a", "T1", "body", "https://img", None),
        AiArticle("量子位", "zh", 8, "https://b", "T2", None, None, None),
    ]
    conn, cur = _mock_conn(rowcounts=[1, 0])  # 第二篇 URL 冲突
    n = storage.insert_articles(conn, arts)
    assert n == 1
    assert cur.execute.call_count == 2


def test_insert_articles_empty_noop() -> None:
    conn, cur = _mock_conn()
    assert storage.insert_articles(conn, []) == 0
    cur.execute.assert_not_called()


def test_fetch_candidates_maps_rows() -> None:
    rows = [
        ("id1", "OpenAI", "en", 10, "https://a", "标题一", "正文", "https://img"),
        ("id2", "量子位", "zh", 8, "https://b", "标题二", None, None),
    ]
    conn, cur = _mock_conn(fetch_rows=rows)
    cands = storage.fetch_candidates(conn, window_hours=24)
    assert len(cands) == 2
    assert cands[0].id == "id1"
    assert cands[1].source_name == "量子位"
    assert cands[1].content is None


def test_claim_pending_maps_rows() -> None:
    rows = [
        ("did1", "sid1", "a@x.com", date(2026, 7, 2), "主题", "<html>", "text", "tok1"),
    ]
    conn, cur = _mock_conn(fetch_rows=rows)
    pending = storage.claim_pending_deliveries(conn, limit=10)
    assert len(pending) == 1
    assert pending[0].delivery_id == "did1"
    assert pending[0].subject == "主题"
    assert pending[0].unsubscribe_token == "tok1"  # noqa: S105 - inert test value
    sql = cur.execute.call_args.args[0]
    assert "s.status <> 'active'" in sql
    assert "s.status = 'active'" in sql
    assert sql.count("%s::date IS NULL") == 2
    assert "FOR UPDATE OF d, s SKIP LOCKED" in sql


def test_lock_active_subscriber_holds_row_lock() -> None:
    conn, cur = _mock_conn(fetch_rows=[("active",)])
    assert storage.lock_active_subscriber(conn, subscriber_id="sid1") is True
    sql, params = cur.execute.call_args.args
    assert "FOR UPDATE" in sql
    assert params == ("sid1",)


def test_lock_active_subscriber_rejects_unsubscribed() -> None:
    conn, _cur = _mock_conn(fetch_rows=[("unsubscribed",)])
    assert storage.lock_active_subscriber(conn, subscriber_id="sid1") is False


def test_fetch_previous_brief_returns_content() -> None:
    conn, cur = _mock_conn(fetch_rows=[({"subject": "昨日"},)])
    content = storage.fetch_previous_brief(conn, date(2026, 7, 2))
    assert content == {"subject": "昨日"}


def test_fetch_previous_brief_none_on_first_day() -> None:
    conn, cur = _mock_conn(fetch_rows=[])
    assert storage.fetch_previous_brief(conn, date(2026, 7, 2)) is None
