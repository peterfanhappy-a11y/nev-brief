"""Unit tests for nev_summarizer.cluster_aggregator."""
from __future__ import annotations

from datetime import date, datetime, timezone
from unittest.mock import MagicMock

from nev_summarizer.cluster_aggregator import (
    Cluster,
    ClusterArticle,
    aggregate_clusters,
)


def _mock_conn(rows: list[dict]):
    conn = MagicMock()
    cur = MagicMock()
    cur.__enter__ = lambda s: cur
    cur.__exit__ = lambda *a: None
    cur.description = [
        type("C", (), {"name": k})()
        for k in (
            rows[0].keys()
            if rows
            else [
                "raw_id",
                "title",
                "clean_text",
                "url",
                "cluster_id",
                "brands",
                "models",
                "topics",
                "importance_score",
                "source_id",
                "source_name",
                "source_authority",
                "published_at",
            ]
        )
    ]
    cur.fetchall.return_value = [tuple(r.values()) for r in rows]
    conn.cursor.return_value = cur
    return conn, cur


def _row(
    cluster_id: str,
    raw_id: str,
    source_id: str,
    source_name: str,
    brands=None,
    models=None,
    topics=None,
    published_at=None,
    score=50.0,
):
    return {
        "raw_id": raw_id,
        "title": f"t-{raw_id}",
        "clean_text": f"c-{raw_id}",
        "url": f"https://x/{raw_id}",
        "cluster_id": cluster_id,
        "brands": brands or [],
        "models": models or [],
        "topics": topics or [],
        "importance_score": score,
        "source_id": source_id,
        "source_name": source_name,
        "source_authority": 8,
        "published_at": published_at
        or datetime(2026, 5, 30, 12, 0, tzinfo=timezone.utc),
    }


def test_groups_by_cluster_id():
    rows = [
        _row("cl1", "r1", "s1", "36氪", brands=["BYD"], topics=["new_car"]),
        _row("cl1", "r2", "s2", "虎嗅", brands=["BYD"], topics=["sales"]),
        _row("cl2", "r3", "s1", "36氪", brands=["Tesla"]),
    ]
    conn, _ = _mock_conn(rows)
    clusters = aggregate_clusters(conn, date(2026, 5, 30))
    assert len(clusters) == 2
    cl_map = {c.cluster_id: c for c in clusters}
    assert len(cl_map["cl1"].articles) == 2
    assert len(cl_map["cl2"].articles) == 1


def test_entity_union_dedup_sorted():
    rows = [
        _row(
            "cl1",
            "r1",
            "s1",
            "36氪",
            brands=["Tesla", "BYD"],
            topics=["new_car", "sales"],
        ),
        _row("cl1", "r2", "s2", "虎嗅", brands=["BYD"], topics=["new_car"]),
    ]
    conn, _ = _mock_conn(rows)
    [c] = aggregate_clusters(conn, date(2026, 5, 30))
    assert c.brands == ["BYD", "Tesla"]  # sorted, dedup'd
    assert c.topics == ["new_car", "sales"]


def test_earliest_published_picked():
    early = datetime(2026, 5, 30, 8, 0, tzinfo=timezone.utc)
    late = datetime(2026, 5, 30, 20, 0, tzinfo=timezone.utc)
    rows = [
        _row("cl1", "r1", "s1", "36氪", published_at=late),
        _row("cl1", "r2", "s2", "虎嗅", published_at=early),
    ]
    conn, _ = _mock_conn(rows)
    [c] = aggregate_clusters(conn, date(2026, 5, 30))
    assert c.earliest_published == early


def test_empty_returns_empty():
    conn, _ = _mock_conn([])
    assert aggregate_clusters(conn, date(2026, 5, 30)) == []


def test_sql_uses_brief_date_window():
    conn, cur = _mock_conn([])
    aggregate_clusters(conn, date(2026, 5, 30))
    sql = cur.execute.call_args[0][0]
    assert "articles_processed" in sql
    assert "JOIN sources" in sql
    assert "cluster_id IS NOT NULL" in sql
    assert "2 hours" in sql or "INTERVAL" in sql
