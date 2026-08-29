"""Publication-state boundaries for persisted AI briefs."""

from __future__ import annotations

from datetime import date
from typing import Any
from unittest.mock import MagicMock

import pytest
from ai_brief import storage


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
