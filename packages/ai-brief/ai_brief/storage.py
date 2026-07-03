"""AI-brief 数据层 — 全部 psycopg I/O。

约定：本模块函数只执行 SQL，不 commit —— commit 由调用方（CLI/runner）在
逻辑单元边界显式执行，然后 close。这是 NEV 踩过的坑：psycopg close() 会静默
回滚未提交事务，生产 cron 变 no-op。

claim_pending_deliveries 用 FOR UPDATE SKIP LOCKED（同 nev_delivery.storage）。
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date

import psycopg


# ── ai_articles ───────────────────────────────────────────────────────
@dataclass(frozen=True)
class AiArticle:
    source_name: str
    locale: str
    authority: int
    url: str
    title: str
    content: str | None
    og_image: str | None
    published_at: str | None  # ISO8601 or None


def insert_articles(conn: psycopg.Connection, articles: list[AiArticle]) -> int:
    """批量插入抓取的文章，ON CONFLICT (url) DO NOTHING。返回新插入行数。"""
    if not articles:
        return 0
    sql = """
        INSERT INTO ai_articles
            (source_name, locale, authority, url, title, content, og_image, published_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (url) DO NOTHING;
    """
    inserted = 0
    with conn.cursor() as cur:
        for a in articles:
            cur.execute(
                sql,
                (
                    a.source_name, a.locale, a.authority, a.url, a.title,
                    a.content, a.og_image, a.published_at,
                ),
            )
            inserted += cur.rowcount
    return inserted


@dataclass(frozen=True)
class Candidate:
    id: str
    source_name: str
    locale: str
    authority: int
    url: str
    title: str
    content: str | None
    og_image: str | None


def fetch_candidates(conn: psycopg.Connection, window_hours: int = 24) -> list[Candidate]:
    """拉取最近 window_hours 抓取的文章，供 Stage-1 排序分类。"""
    sql = """
        SELECT id::text, source_name, locale, authority, url, title, content, og_image
        FROM ai_articles
        WHERE crawled_at >= NOW() - make_interval(hours => %s)
        ORDER BY authority DESC, crawled_at DESC;
    """
    with conn.cursor() as cur:
        cur.execute(sql, (window_hours,))
        rows = cur.fetchall()
    return [
        Candidate(
            id=r[0], source_name=r[1], locale=r[2], authority=r[3],
            url=r[4], title=r[5], content=r[6], og_image=r[7],
        )
        for r in rows
    ]


def fetch_article_content(conn: psycopg.Connection, article_id: str) -> str | None:
    with conn.cursor() as cur:
        cur.execute("SELECT content FROM ai_articles WHERE id = %s;", (article_id,))
        row = cur.fetchone()
    return row[0] if row else None


# ── ai_daily_briefs ───────────────────────────────────────────────────
def upsert_daily_brief(
    conn: psycopg.Connection,
    *,
    brief_date: date,
    content: dict,
    model: str | None,
) -> None:
    """写入/更新当日简报文档。brief_date UNIQUE → 重跑覆盖。"""
    sql = """
        INSERT INTO ai_daily_briefs (brief_date, content, model, generated_at)
        VALUES (%s, %s, %s, NOW())
        ON CONFLICT (brief_date) DO UPDATE
        SET content = EXCLUDED.content,
            model = EXCLUDED.model,
            generated_at = NOW(),
            updated_at = NOW();
    """
    with conn.cursor() as cur:
        cur.execute(sql, (brief_date, json.dumps(content, ensure_ascii=False), model))


def fetch_brief(conn: psycopg.Connection, brief_date: date) -> dict | None:
    with conn.cursor() as cur:
        cur.execute("SELECT content FROM ai_daily_briefs WHERE brief_date = %s;", (brief_date,))
        row = cur.fetchone()
    return row[0] if row else None


def fetch_previous_brief(conn: psycopg.Connection, before: date) -> dict | None:
    """最近一期（< before）的简报，用于「昨日最热」。跳过的日期不会导致空白。"""
    sql = """
        SELECT content FROM ai_daily_briefs
        WHERE brief_date < %s
        ORDER BY brief_date DESC
        LIMIT 1;
    """
    with conn.cursor() as cur:
        cur.execute(sql, (before,))
        row = cur.fetchone()
    return row[0] if row else None


# ── ai_subscribers ────────────────────────────────────────────────────
@dataclass(frozen=True)
class ActiveSubscriber:
    id: str
    email: str
    unsubscribe_token: str


def fetch_active_subscribers(
    conn: psycopg.Connection,
    only_email: str | None = None,
) -> list[ActiveSubscriber]:
    sql = """
        SELECT id::text, email, unsubscribe_token::text
        FROM ai_subscribers
        WHERE status = 'active'
        {email_filter}
        ORDER BY created_at;
    """.format(email_filter="AND email = %s" if only_email else "")
    params = (only_email,) if only_email else ()
    with conn.cursor() as cur:
        cur.execute(sql, params)
        rows = cur.fetchall()
    return [ActiveSubscriber(id=r[0], email=r[1], unsubscribe_token=r[2]) for r in rows]


# ── ai_deliveries ─────────────────────────────────────────────────────
def upsert_delivery(
    conn: psycopg.Connection,
    *,
    delivery_id: str,
    subscriber_id: str,
    brief_date: date,
    subject: str,
    content_html: str,
    content_text: str,
) -> None:
    """插入/更新一封投递。delivery_id 由调用方生成（评分链接需在渲染前知道 id）。
    UNIQUE(subscriber_id, brief_date) → 重跑用现有 id 覆盖内容、重置为 pending。"""
    sql = """
        INSERT INTO ai_deliveries
            (id, subscriber_id, brief_date, subject, content_html, content_text, status)
        VALUES (%s, %s, %s, %s, %s, %s, 'pending')
        ON CONFLICT (subscriber_id, brief_date) DO UPDATE
        SET subject = EXCLUDED.subject,
            content_html = EXCLUDED.content_html,
            content_text = EXCLUDED.content_text,
            status = 'pending',
            error = NULL,
            updated_at = NOW();
    """
    with conn.cursor() as cur:
        cur.execute(
            sql,
            (delivery_id, subscriber_id, brief_date, subject, content_html, content_text),
        )


def get_existing_delivery_id(
    conn: psycopg.Connection,
    *,
    subscriber_id: str,
    brief_date: date,
) -> str | None:
    """重跑时复用已有 delivery id（保证已发出邮件里的评分链接仍有效）。"""
    with conn.cursor() as cur:
        cur.execute(
            "SELECT id::text FROM ai_deliveries WHERE subscriber_id = %s AND brief_date = %s;",
            (subscriber_id, brief_date),
        )
        row = cur.fetchone()
    return row[0] if row else None


@dataclass(frozen=True)
class PendingAiDelivery:
    delivery_id: str
    subscriber_id: str
    email: str
    brief_date: date
    subject: str
    content_html: str
    content_text: str
    unsubscribe_token: str


def claim_pending_deliveries(
    conn: psycopg.Connection,
    limit: int = 50,
) -> list[PendingAiDelivery]:
    """原子领取至多 limit 封 pending 投递，标记 sending 并返回内容。"""
    sql = """
        WITH claimed AS (
            SELECT d.id
            FROM ai_deliveries d
            WHERE d.status = 'pending'
            ORDER BY d.created_at
            FOR UPDATE SKIP LOCKED
            LIMIT %s
        )
        UPDATE ai_deliveries d
        SET status = 'sending', updated_at = NOW()
        FROM claimed
        WHERE d.id = claimed.id
        RETURNING
            d.id::text,
            d.subscriber_id::text,
            (SELECT email FROM ai_subscribers WHERE id = d.subscriber_id),
            d.brief_date,
            d.subject,
            d.content_html,
            d.content_text,
            (SELECT unsubscribe_token::text FROM ai_subscribers WHERE id = d.subscriber_id);
    """
    with conn.cursor() as cur:
        cur.execute(sql, (limit,))
        rows = cur.fetchall()
    return [
        PendingAiDelivery(
            delivery_id=r[0], subscriber_id=r[1], email=r[2], brief_date=r[3],
            subject=r[4], content_html=r[5], content_text=r[6], unsubscribe_token=r[7],
        )
        for r in rows
    ]


def mark_sent(conn: psycopg.Connection, *, delivery_id: str, resend_email_id: str) -> None:
    sql = """
        UPDATE ai_deliveries
        SET status = 'sent', resend_id = %s, sent_at = NOW(), error = NULL, updated_at = NOW()
        WHERE id = %s;
    """
    with conn.cursor() as cur:
        cur.execute(sql, (resend_email_id, delivery_id))


def mark_failed(conn: psycopg.Connection, *, delivery_id: str, error: str) -> None:
    sql = """
        UPDATE ai_deliveries
        SET status = 'failed', error = %s, retry_count = retry_count + 1, updated_at = NOW()
        WHERE id = %s;
    """
    with conn.cursor() as cur:
        cur.execute(sql, (error[:500], delivery_id))


def reset_to_pending(conn: psycopg.Connection, *, delivery_id: str, error: str) -> None:
    sql = """
        UPDATE ai_deliveries
        SET status = 'pending', error = %s, retry_count = retry_count + 1, updated_at = NOW()
        WHERE id = %s;
    """
    with conn.cursor() as cur:
        cur.execute(sql, (error[:500], delivery_id))
