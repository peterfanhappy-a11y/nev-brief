"""storage.py 单测 — 用 mock cursor 验证 row 映射 + rowcount 累加逻辑。
真实 DB 往返在 T12 E2E 验证。"""
from __future__ import annotations

import json
from collections.abc import Sequence
from datetime import date
from typing import Any
from unittest.mock import MagicMock
from uuid import UUID

import pytest
from ai_brief import storage
from ai_brief.storage import AiArticle
from psycopg._queries import PostgresQuery
from psycopg.adapt import Transformer
from pydantic import ValidationError


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


def test_retry_transient_deliveries_uses_valid_psycopg_placeholders() -> None:
    conn, cur = _mock_conn(fetch_rows=[("delivery-1",), ("delivery-2",)])

    def adapt_query(query: str, params: tuple[object, ...]) -> None:
        PostgresQuery(Transformer()).convert(query, params)

    cur.execute.side_effect = adapt_query

    assert storage.retry_transient_deliveries(
        conn,
        brief_date=date(2026, 9, 12),
    ) == 2


def test_fetch_previous_brief_returns_content() -> None:
    conn, cur = _mock_conn(fetch_rows=[({"subject": "昨日"},)])
    content = storage.fetch_previous_brief(conn, date(2026, 7, 2))
    assert content == {"subject": "昨日"}


def test_fetch_previous_brief_none_on_first_day() -> None:
    conn, cur = _mock_conn(fetch_rows=[])
    assert storage.fetch_previous_brief(conn, date(2026, 7, 2)) is None


@pytest.mark.parametrize("version", [2, 3])
@pytest.mark.parametrize("operation", ["save", "upsert", "blocked"])
def test_current_content_normalization_preserves_opc_and_clears_legacy_fields(
    version: int, operation: str,
) -> None:
    opc_case = {
        "sharer": "Ruslan", "headline": "Zipchat", "summary": "案例正文",
        "original_revenue": "$167K MRR", "monthly_revenue_usd": 167_000,
        "revenue_display": "$167K 美元月度营收",
        "url": "https://www.indiehackers.com/post/case-two",
        "header_image": "https://aivizens.com/images/opc.png", "header_image_alt": "Zipchat 案例",
    }
    content = {
        "version": version, "brief_date": "2026-09-14", "subject": "Frozen candidate",
        "preheader": "OPC", "intro_bullets": ["一", "二", "三", "🧰 Agent 0"],
        "opc_case": opc_case if version == 3 else None,
        "ai_engineering": {"theme": "ai_engineering", "stories": [
            {"headline": "Old story", "summary": "Old summary"},
        ]},
        "featured": [{"theme": "model_research", "theme_label": "Old",
                      "headline": "Old feature", "details": ["Old detail"],
                      "significance": "Old significance", "url": "https://openai.com/old",
                      "source_name": "OpenAI"}],
        "tools": [{"name": "Old tool", "one_liner": "Old tool summary", "url": "https://openai.com"}],
        "quick_hits": [{"text": "Old quick hit", "url": "https://openai.com"}],
        "daily_tip": {"title": "Legacy tip", "body": "Legacy body"},
        "yesterday_top": {"headline": "Legacy top", "url": "https://openai.com/old"},
        "unknown": "private-unknown",
    }
    if operation == "blocked" and version == 3:
        content["intro_bullets"] = ["One", "Two", "Three", "Four", "Five"]
    conn, cur = _mock_conn(fetch_rows=[("awaiting_approval",)])
    if operation in ("save", "blocked"):
        storage.save_generated_brief(
            conn, brief_date=date(2026, 9, 14), content=content, model=None,
            digest_sources={}, quality_report={"passed": operation == "save"},
            source_run_id=UUID("31a9cf25-51f4-4e83-9c77-5574d8d6bc30"),
            status="awaiting_approval" if operation == "save" else "blocked",
        )
        persisted = json.loads(cur.execute.call_args.args[1][0])
    else:
        storage.upsert_daily_brief(conn, brief_date=date(2026, 9, 14), content=content, model=None)
        persisted = json.loads(cur.execute.call_args.args[1][1])
    assert persisted["opc_case"] == (opc_case if version == 3 else None)
    assert persisted["intro_bullets"] == content["intro_bullets"]
    assert "unknown" not in persisted
    assert persisted["ai_engineering"] is None
    assert persisted["daily_tip"] is None
    assert persisted["yesterday_top"] is None
    assert persisted["featured"] == persisted["tools"] == persisted["quick_hits"] == []


@pytest.mark.parametrize("operation", ["save", "upsert"])
@pytest.mark.parametrize("bullet_count", [4, 5])
def test_publishable_and_draft_v3_still_reject_schema_invalid_content(
    operation: str, bullet_count: int,
) -> None:
    conn, cur = _mock_conn()
    content = {
        "version": 3, "brief_date": "2026-09-14", "subject": "Invalid candidate",
        "preheader": "Missing OPC", "intro_bullets": ["Bullet"] * bullet_count,
        "opc_case": None,
    }
    with pytest.raises(ValidationError):
        if operation == "save":
            storage.save_generated_brief(
                conn, brief_date=date(2026, 9, 14), content=content, model=None,
                digest_sources={}, quality_report={"passed": True},
                source_run_id=UUID("31a9cf25-51f4-4e83-9c77-5574d8d6bc30"),
                status="awaiting_approval",
            )
        else:
            storage.upsert_daily_brief(
                conn, brief_date=date(2026, 9, 14), content=content, model=None,
            )
    cur.execute.assert_not_called()


@pytest.mark.parametrize("passed", [True, None, 0, "false"])
def test_rejected_candidate_path_requires_boolean_false_quality_report(passed: Any) -> None:
    conn, cur = _mock_conn()
    with pytest.raises(ValueError, match="workflow status must match the stored quality report"):
        storage.save_generated_brief(
            conn, brief_date=date(2026, 9, 14), content={"version": 3, "opc_case": None},
            model=None, digest_sources={}, quality_report={"passed": passed},
            source_run_id=UUID("31a9cf25-51f4-4e83-9c77-5574d8d6bc30"), status="blocked",
        )
    cur.execute.assert_not_called()
