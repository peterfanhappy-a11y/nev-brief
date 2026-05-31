"""Aggregate articles_processed rows into cluster-level structures."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime

import psycopg


@dataclass(frozen=True)
class ClusterArticle:
    raw_id: str
    title: str
    clean_text: str
    url: str
    source_id: str
    source_name: str
    source_authority: int
    published_at: datetime
    importance_score: float


@dataclass(frozen=True)
class Cluster:
    cluster_id: str
    articles: list[ClusterArticle]
    brands: list[str]  # union of all article brands, dedup'd, sorted
    models: list[str]
    topics: list[str]
    earliest_published: datetime


def aggregate_clusters(conn: psycopg.Connection, brief_date: date) -> list[Cluster]:
    """Read articles_processed for brief_date and group by cluster_id.

    Uses articles_raw.published_at (not created_at) to define brief_date window,
    with ±2h buffer to avoid losing tail-of-day articles to next day. brief_date
    is interpreted as a UTC date.

    Articles with NULL cluster_id are skipped.
    """
    sql = """
        SELECT
            p.raw_id, p.title, p.clean_text, r.url,
            p.cluster_id, p.brands, p.models, p.topics,
            p.importance_score,
            r.source_id, s.name AS source_name, s.authority AS source_authority,
            r.published_at
        FROM articles_processed p
        JOIN articles_raw r ON r.id = p.raw_id
        JOIN sources s ON s.id = r.source_id
        WHERE p.cluster_id IS NOT NULL
          AND r.published_at >= %s - INTERVAL '2 hours'
          AND r.published_at < %s + INTERVAL '26 hours'
        ORDER BY p.cluster_id, r.published_at;
    """
    with conn.cursor() as cur:
        cur.execute(sql, (brief_date, brief_date))
        cols = [c.name for c in cur.description]
        rows = [dict(zip(cols, r, strict=True)) for r in cur.fetchall()]

    by_cluster: dict[str, list[dict]] = {}
    for row in rows:
        by_cluster.setdefault(str(row["cluster_id"]), []).append(row)

    clusters: list[Cluster] = []
    for cluster_id, group in by_cluster.items():
        articles = [
            ClusterArticle(
                raw_id=str(r["raw_id"]),
                title=r["title"],
                clean_text=r["clean_text"],
                url=r["url"],
                source_id=str(r["source_id"]),
                source_name=r["source_name"],
                source_authority=int(r["source_authority"]),
                published_at=r["published_at"],
                importance_score=float(r["importance_score"] or 0.0),
            )
            for r in group
        ]
        brands = sorted({b for r in group for b in (r["brands"] or [])})
        models = sorted({m for r in group for m in (r["models"] or [])})
        topics = sorted({t for r in group for t in (r["topics"] or [])})
        earliest = min(a.published_at for a in articles)
        clusters.append(
            Cluster(
                cluster_id=cluster_id,
                articles=articles,
                brands=brands,
                models=models,
                topics=topics,
                earliest_published=earliest,
            )
        )
    return clusters
