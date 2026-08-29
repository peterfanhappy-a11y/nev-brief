"""Privacy boundary tests for CLI operational statistics."""

from unittest.mock import MagicMock

from ai_brief.stats import fetch_stats


def test_stats_queries_only_aggregate_views_and_never_recipient_rows() -> None:
    conn = MagicMock()
    cursor = conn.cursor.return_value.__enter__.return_value
    cursor.description = []
    cursor.fetchall.return_value = []

    fetch_stats(conn)

    sql = " ".join(str(call.args[0]) for call in cursor.execute.call_args_list)
    assert "ai_subscription_stats" in sql
    assert "ai_delivery_stats" in sql
    assert "ai_rating_stats" in sql
    assert "ai_daily_operations" in sql
    for forbidden in ("ai_subscribers", "email", "token", "content_html", "content_text"):
        assert forbidden not in sql.lower()
