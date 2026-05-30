"""articles_raw ↔ articles_processed I/O for pipeline."""
from __future__ import annotations

import psycopg


def claim_pending(conn: psycopg.Connection, limit: int) -> list[dict]:
    """Atomically claim N pending raw articles → mark processing → return rows."""
    sql = """
        UPDATE articles_raw
        SET status='processing', updated_at=NOW()
        WHERE id IN (
            SELECT id FROM articles_raw
            WHERE status='pending'
            ORDER BY published_at DESC NULLS LAST
            LIMIT %s
            FOR UPDATE SKIP LOCKED
        )
        RETURNING id, source_id, title, content, content_hash, url, published_at;
    """
    with conn.cursor() as cur:
        cur.execute(sql, (limit,))
        cols = [c.name for c in cur.description]
        return [dict(zip(cols, r, strict=True)) for r in cur.fetchall()]


def upsert_processed(conn: psycopg.Connection, processed: dict) -> None:
    sql = """
        INSERT INTO articles_processed
            (raw_id, title, clean_text, simhash, cluster_id,
             brands, models, topics, people, importance_score, language, status)
        VALUES
            (%(raw_id)s, %(title)s, %(clean_text)s, %(simhash)s, %(cluster_id)s,
             %(brands)s, %(models)s, %(topics)s, %(people)s,
             %(importance_score)s, %(language)s, 'done')
        ON CONFLICT (raw_id) DO UPDATE SET
            cluster_id       = EXCLUDED.cluster_id,
            simhash          = EXCLUDED.simhash,
            brands           = EXCLUDED.brands,
            models           = EXCLUDED.models,
            topics           = EXCLUDED.topics,
            people           = EXCLUDED.people,
            importance_score = EXCLUDED.importance_score,
            status           = 'done',
            updated_at       = NOW();
    """
    with conn.cursor() as cur:
        cur.execute(sql, processed)


def mark_raw_done(conn: psycopg.Connection, raw_id: str) -> None:
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE articles_raw SET status='done', updated_at=NOW() WHERE id=%s",
            (raw_id,),
        )


def mark_raw_failed(conn: psycopg.Connection, raw_id: str, error: str) -> None:
    # error 暂未持久化（schema 没列）；structlog 已记录
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE articles_raw SET status='failed', updated_at=NOW() WHERE id=%s",
            (raw_id,),
        )


def load_recent_processed(conn: psycopg.Connection, hours: int = 24) -> list[dict]:
    """聚类匹配用：拉最近 N 小时的 cluster_id + simhash + brands/models + published_at。"""
    sql = """
        SELECT p.cluster_id, p.simhash, p.brands, p.models, r.published_at
        FROM articles_processed p
        JOIN articles_raw r ON r.id = p.raw_id
        WHERE p.cluster_id IS NOT NULL
          AND p.simhash IS NOT NULL
          AND r.published_at > NOW() - (%s || ' hours')::interval
        ORDER BY r.published_at DESC;
    """
    with conn.cursor() as cur:
        cur.execute(sql, (hours,))
        cols = [c.name for c in cur.description]
        return [dict(zip(cols, r, strict=True)) for r in cur.fetchall()]
