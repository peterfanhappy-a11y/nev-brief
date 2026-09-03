"""Publication-state boundaries for persisted AI briefs."""

from __future__ import annotations

from datetime import date
from typing import Any
from unittest.mock import MagicMock
from uuid import UUID

import pytest
from ai_brief import storage
from ai_brief.schema import AiBriefContent


def _connection(
    *,
    fetchone: tuple[Any, ...] | None = None,
    fetchall: list[tuple[Any, ...]] | None = None,
) -> tuple[MagicMock, MagicMock]:
    cursor = MagicMock()
    cursor.fetchone.return_value = fetchone
    cursor.fetchall.return_value = fetchall or []
    connection = MagicMock()
    connection.cursor.return_value.__enter__.return_value = cursor
    connection.cursor.return_value.__exit__.return_value = False
    return connection, cursor


def test_fetch_public_brief_queries_only_published_content() -> None:
    brief_date = date(2026, 8, 3)
    connection, cursor = _connection(fetchone=({"subject": "Public issue"},))

    result = storage.fetch_public_brief(connection, brief_date)

    assert result == {"subject": "Public issue"}
    sql, params = cursor.execute.call_args.args
    assert "status = %s" in sql
    assert params == (brief_date, "published")


def test_fetch_public_brief_returns_none_when_no_published_row_matches() -> None:
    connection, _cursor = _connection(fetchone=None)

    assert storage.fetch_public_brief(connection, date(2026, 8, 3)) is None


def test_list_public_briefs_returns_only_published_content_newest_first() -> None:
    connection, cursor = _connection(
        fetchall=[
            ({"subject": "Newest"},),
            ({"subject": "Older"},),
        ]
    )

    result = storage.list_public_briefs(connection, limit=2)

    assert result == [{"subject": "Newest"}, {"subject": "Older"}]
    sql, params = cursor.execute.call_args.args
    normalized_sql = " ".join(sql.split())
    assert "WHERE status = %s" in normalized_sql
    assert "ORDER BY published_at DESC, brief_date DESC" in normalized_sql
    assert params == ("published", 2)


@pytest.mark.parametrize("existing_status", ["generating", "blocked", "awaiting_approval"])
def test_upsert_daily_brief_rewrites_only_regenerable_statuses(existing_status: str) -> None:
    connection, cursor = _connection(fetchone=(existing_status,))

    result = storage.upsert_daily_brief(
        connection,
        brief_date=date(2026, 8, 3),
        content={"subject": "Regenerated"},
        model="test-model",
    )

    assert result == "written"
    sql, params = cursor.execute.call_args.args
    normalized_sql = " ".join(sql.split())
    assert "WHERE ai_daily_briefs.status IN (%s, %s, %s)" in normalized_sql
    assert "RETURNING status" in normalized_sql
    assert params[-3:] == ("generating", "blocked", "awaiting_approval")
    assert existing_status in params[-3:]


@pytest.mark.parametrize("protected_status", ["approved", "published"])
def test_upsert_daily_brief_reports_conflict_for_protected_status(
    protected_status: str,
) -> None:
    connection, cursor = _connection(fetchone=None)

    result = storage.upsert_daily_brief(
        connection,
        brief_date=date(2026, 8, 3),
        content={"subject": f"Must not replace {protected_status}"},
        model="test-model",
    )

    assert result == "conflict"
    assert cursor.fetchone.call_count == 1
    _sql, params = cursor.execute.call_args.args
    assert protected_status not in params[-3:]


def test_upsert_daily_brief_normalizes_v2_content_before_storage() -> None:
    connection, cursor = _connection(fetchone=("generating",))
    content = AiBriefContent(
        version=2,
        brief_date="2026-08-03",
        subject="主题",
        preheader="另外：x",
        intro_bullets=["a"],
    ).model_dump(mode="json")
    content.update(
        {
            "ai_engineering": {
                "theme": "ai_engineering",
                "stories": [{"headline": "工程", "summary": "摘要"}],
            },
            "featured": [
                {
                    "theme": "model_research",
                    "theme_label": "模型研究",
                    "headline": "精选",
                    "details": ["详情"],
                    "significance": "意义",
                    "url": "https://example.com/featured",
                    "source_name": "来源",
                }
            ],
            "tools": [{"name": "旧工具", "one_liner": "旧工具说明", "url": "https://example.com/tool"}],
            "daily_tip": {"title": "旧技巧", "body": "旧技巧说明"},
            "quick_hits": [{"text": "旧快讯", "url": "https://example.com/hit"}],
            "yesterday_top": {"headline": "昨日焦点", "url": "https://example.com/yesterday"},
        }
    )

    storage.upsert_daily_brief(
        connection,
        brief_date=date(2026, 8, 3),
        content=content,
        model="test-model",
    )

    _sql, params = cursor.execute.call_args.args
    stored = storage.json.loads(params[1])
    assert stored["ai_engineering"] is None
    assert stored["featured"] == []
    assert stored["tools"] == []
    assert stored["daily_tip"] is None
    assert stored["quick_hits"] == []
    assert stored["yesterday_top"] is None

    storage.save_generated_brief(
        connection,
        brief_date=date(2026, 8, 3),
        content=content,
        model="test-model",
        digest_sources={},
        quality_report={"passed": True, "blockers": [], "warnings": [], "metrics": {}},
        source_run_id=UUID("aee85a2c-9c58-4be9-8a30-d4aed5fa4690"),
        status="awaiting_approval",
    )

    _sql, params = cursor.execute.call_args.args
    stored = storage.json.loads(params[0])
    assert stored["ai_engineering"] is None
    assert stored["featured"] == []
    assert stored["tools"] == []
    assert stored["daily_tip"] is None
    assert stored["quick_hits"] == []
    assert stored["yesterday_top"] is None
