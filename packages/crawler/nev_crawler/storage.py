"""articles_raw 写入层 — URL UNIQUE 容忍冲突。"""
from __future__ import annotations

import hashlib

import psycopg

from python.content import ArticleRaw


def hash_content(text: str | None) -> str | None:
    """生成 60-bit 内容哈希（用于 SimHash 之前的快速去重）。

    MVP 用 blake2b 8 字节做粗去重；pipeline 阶段（Agent-3）会算真正 SimHash。
    """
    if not text:
        return None
    h = hashlib.blake2b(text.encode("utf-8"), digest_size=8)
    return h.hexdigest()


def insert_articles_raw(conn: psycopg.Connection, articles: list[ArticleRaw]) -> int:
    """批量插入 articles_raw，URL 冲突跳过。返回实际插入条数。"""
    if not articles:
        return 0
    inserted = 0
    with conn.cursor() as cur:
        for a in articles:
            try:
                cur.execute(
                    """INSERT INTO articles_raw
                       (id, source_id, url, title, content, content_hash, published_at)
                       VALUES (%s, %s, %s, %s, %s, %s, %s)
                       ON CONFLICT (url) DO NOTHING""",
                    (
                        str(a.id), str(a.source_id), a.url, a.title,
                        a.content, hash_content(a.content), a.published_at,
                    ),
                )
                if cur.rowcount > 0:
                    inserted += 1
            except psycopg.errors.UniqueViolation:
                conn.rollback()
                continue
    return inserted
