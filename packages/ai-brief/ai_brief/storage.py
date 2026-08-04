"""AI-brief 数据层 — 全部 psycopg I/O。

约定：本模块函数只执行 SQL，不 commit —— commit 由调用方（CLI/runner）在
逻辑单元边界显式执行，然后 close。这是 NEV 踩过的坑：psycopg close() 会静默
回滚未提交事务，生产 cron 变 no-op。

claim_pending_deliveries 用 FOR UPDATE SKIP LOCKED（同 nev_delivery.storage）。
"""
from __future__ import annotations

import json
import math
import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from typing import Any, Literal
from uuid import UUID

import psycopg

DigestRunStatus = Literal["running", "blocked", "awaiting_approval", "failed", "completed"]
_DIGEST_METADATA_FIELDS = (
    "kind",
    "message_id",
    "subject",
    "received_at",
    "requested_date",
    "matched_date",
    "used_fallback",
)
_ATTACHMENT_METADATA_FIELDS = ("filename", "content_type", "size_bytes")
_ALLOWED_ERROR_CODES = frozenset(
    {
        "brief_generation_failed",
        "digest_fetch_failed",
        "digest_parse_failed",
        "pipeline_failed",
        "quality_gate_failed",
        "source_timeout",
        "storage_write_failed",
    }
)
_ALLOWED_QUALITY_ISSUE_CODES = frozenset(
    {
        "ai_masters_story_count_below_minimum",
        "brief_status_protected",
        "critical_url_missing",
        "deepseek_incomplete",
        "digest_date_fallback",
        "editorial_blank",
        "intro_blank",
        "non_core_items_filtered",
        "parse_failed",
        "placeholder_url",
        "qwen_image_fallback",
        "required_digest_stale",
        "schema_invalid",
        "source_domain_unknown",
        "subject_blank",
        "summary_near_limit",
        "today_ai_story_count_below_minimum",
        "tool_module_count_below_minimum",
        "tool_module_missing",
        "url_not_https",
    }
)
_ALLOWED_QUALITY_METRICS = frozenset(
    {
        "agent_freshness_hours",
        "agent_story_count",
        "ai_masters_story_count",
        "blocker_count",
        "builder_freshness_hours",
        "deepseek_complete",
        "digest_date_fallback",
        "editorial_length",
        "engineering_freshness_hours",
        "engineering_story_count",
        "events_freshness_hours",
        "existing_brief_protected",
        "filtered_non_core_item_count",
        "intro_bullet_count",
        "max_digest_freshness_hours",
        "missing_tool_module_count",
        "parsed_items",
        "quality_passed",
        "qwen_complete",
        "qwen_image_fallback",
        "required_digests_fresh",
        "research_freshness_hours",
        "research_story_count",
        "schema_valid",
        "subject_length",
        "summary_near_limit_count",
        "today_ai_story_count",
        "tool_module_count",
        "unknown_source_domain_count",
        "warning_count",
    }
)
_BRIEF_QUALITY_PATHS = frozenset(
    {
        "editorial",
        "intro_bullets",
        "preheader",
        "subject",
    }
)
_DIGEST_SECTION_ROOTS = frozenset(
    {
        "agent_tools",
        "ai_engineering",
        "ai_masters",
        "ai_research",
        "today_ai",
    }
)
_DIGEST_SECTION_FIELDS = frozenset(
    {"cta_label", "header_image", "header_image_alt", "stories", "subtitle", "theme"}
)
_DIGEST_STORY_FIELDS = frozenset({"headline", "label", "summary", "url"})
_DIGEST_SOURCE_KINDS = frozenset(
    {"agent", "builder", "engineering", "events", "research"}
)
_DIGEST_SOURCE_FIELDS = frozenset(
    {"matched_date", "received_at", "requested_date", "used_fallback"}
)
_INDEXED_STORY_PATH = re.compile(r"^stories\[(?:0|[1-9][0-9]*)\](?:\.([a-z_]+))?$")


class DigestRunAlreadyFinishedError(RuntimeError):
    """Raised when a terminal digest run is completed a second time."""


def _safe_digest_run_payloads(
    digest_sources: Mapping[str, Mapping[str, Any] | None],
) -> tuple[dict[str, dict[str, Any] | None], dict[str, int]]:
    safe_sources: dict[str, dict[str, Any] | None] = {}
    parse_counts: dict[str, int] = {}
    for source, metadata in digest_sources.items():
        if metadata is None:
            safe_sources[source] = None
            continue

        safe_metadata = {
            field: metadata[field]
            for field in _DIGEST_METADATA_FIELDS
            if field in metadata
        }
        attachments = metadata.get("attachments")
        if isinstance(attachments, (list, tuple)):
            safe_metadata["attachments"] = [
                {
                    field: attachment[field]
                    for field in _ATTACHMENT_METADATA_FIELDS
                    if field in attachment
                }
                for attachment in attachments
                if isinstance(attachment, Mapping)
            ]
        safe_sources[source] = safe_metadata

        parse_count = metadata.get("parse_count")
        if isinstance(parse_count, int) and not isinstance(parse_count, bool) and parse_count >= 0:
            parse_counts[source] = parse_count
    return safe_sources, parse_counts


def _safe_error_summary(error_summary: str | None) -> str | None:
    if error_summary is None:
        return None
    candidate = error_summary.strip()
    if not candidate:
        return None
    if candidate in _ALLOWED_ERROR_CODES:
        return candidate
    return "digest run failed"


def _safe_metric_value(value: object) -> int | float | bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    return None


def _safe_quality_issue(issue: Mapping[str, Any]) -> dict[str, object] | None:
    code = issue.get("code")
    if not isinstance(code, str) or code not in _ALLOWED_QUALITY_ISSUE_CODES:
        return None
    safe_issue: dict[str, object] = {"code": code}
    path = issue.get("path")
    if path is None:
        safe_issue["path"] = None
    elif isinstance(path, str) and _quality_path_is_allowed(path):
        safe_issue["path"] = path
    return safe_issue


def _quality_path_is_allowed(path: str) -> bool:
    if path in _BRIEF_QUALITY_PATHS or path in _DIGEST_SECTION_ROOTS:
        return True

    root, separator, remainder = path.partition(".")
    if not separator:
        return False
    if root == "digests":
        kind, field_separator, field = remainder.partition(".")
        return kind in _DIGEST_SOURCE_KINDS and (
            not field_separator or field in _DIGEST_SOURCE_FIELDS
        )
    if root not in _DIGEST_SECTION_ROOTS:
        return False
    if remainder in _DIGEST_SECTION_FIELDS:
        return True
    story_match = _INDEXED_STORY_PATH.fullmatch(remainder)
    return story_match is not None and (
        story_match.group(1) is None or story_match.group(1) in _DIGEST_STORY_FIELDS
    )


def _safe_quality_report(quality_report: Mapping[str, Any] | None) -> dict[str, object] | None:
    if quality_report is None:
        return None

    safe_report: dict[str, object] = {}
    passed = quality_report.get("passed")
    if isinstance(passed, bool):
        safe_report["passed"] = passed

    for field in ("blockers", "warnings"):
        issues = quality_report.get(field)
        if isinstance(issues, (list, tuple)):
            safe_issues = (
                _safe_quality_issue(issue)
                for issue in issues
                if isinstance(issue, Mapping)
            )
            safe_report[field] = [issue for issue in safe_issues if issue is not None]

    metrics = quality_report.get("metrics")
    if isinstance(metrics, Mapping):
        safe_metrics: dict[str, int | float | bool] = {}
        for key, value in metrics.items():
            safe_value = _safe_metric_value(value)
            if (
                isinstance(key, str)
                and key in _ALLOWED_QUALITY_METRICS
                and safe_value is not None
            ):
                safe_metrics[key] = safe_value
        safe_report["metrics"] = safe_metrics
    return safe_report


def start_digest_run(
    conn: psycopg.Connection,
    brief_date: date,
    source_adapter: str,
) -> UUID:
    """Create exactly one durable identity for a digest pipeline invocation."""
    sql = """
        INSERT INTO ai_digest_runs (brief_date, source_adapter, status, started_at)
        VALUES (%s, %s, %s, statement_timestamp())
        RETURNING id;
    """
    with conn.cursor() as cur:
        cur.execute(sql, (brief_date, source_adapter, "running"))
        row = cur.fetchone()
    if row is None:  # pragma: no cover - PostgreSQL RETURNING guarantees a row
        raise RuntimeError("digest run insert returned no id")
    run_id = row[0]
    return run_id if isinstance(run_id, UUID) else UUID(str(run_id))


def finish_digest_run(
    conn: psycopg.Connection,
    run_id: UUID,
    *,
    status: DigestRunStatus,
    digest_sources: Mapping[str, Mapping[str, Any] | None],
    quality_report: Mapping[str, Any] | None,
    stage: str | None,
    error_summary: str | None,
) -> None:
    """Finish a running invocation once, persisting only operational metadata."""
    if status == "running":
        raise ValueError("finished digest run requires a terminal status")
    if status == "failed" and (stage is None or not stage.strip()):
        raise ValueError("failed digest run requires a non-empty stage")
    safe_sources, parse_counts = _safe_digest_run_payloads(digest_sources)
    safe_quality_report = _safe_quality_report(quality_report)
    failed_stage = stage.strip() if stage and status in ("blocked", "failed") else None
    sql = """
        WITH finish_clock AS MATERIALIZED (
            SELECT statement_timestamp() AS finished_at
        )
        UPDATE ai_digest_runs AS run
        SET status = %s,
            digest_sources = %s::jsonb,
            parse_counts = %s::jsonb,
            quality_report = %s::jsonb,
            failed_stage = %s,
            error_summary = %s,
            finished_at = finish_clock.finished_at,
            duration_ms = GREATEST(
                0,
                ROUND(
                    EXTRACT(EPOCH FROM (finish_clock.finished_at - run.started_at)) * 1000
                )::bigint
            ),
            updated_at = finish_clock.finished_at
        FROM finish_clock
        WHERE run.id = %s
          AND run.status = 'running'
        RETURNING run.id;
    """
    with conn.cursor() as cur:
        cur.execute(
            sql,
            (
                status,
                json.dumps(safe_sources, ensure_ascii=False),
                json.dumps(parse_counts, ensure_ascii=False),
                json.dumps(safe_quality_report, ensure_ascii=False)
                if safe_quality_report is not None
                else None,
                failed_stage,
                _safe_error_summary(error_summary),
                run_id,
            ),
        )
        row = cur.fetchone()
    if row is None:
        raise DigestRunAlreadyFinishedError(f"digest run is missing or already finished: {run_id}")


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
BriefStatus = Literal[
    "generating",
    "blocked",
    "awaiting_approval",
    "approved",
    "published",
]
BriefWriteResult = Literal["written", "conflict"]


def upsert_daily_brief(
    conn: psycopg.Connection,
    *,
    brief_date: date,
    content: dict[str, Any],
    model: str | None,
) -> BriefWriteResult:
    """Write a draft unless the date is already approved or published."""
    sql = """
        INSERT INTO ai_daily_briefs (brief_date, content, model, generated_at)
        VALUES (%s, %s, %s, NOW())
        ON CONFLICT (brief_date) DO UPDATE
        SET content = EXCLUDED.content,
            model = EXCLUDED.model,
            generated_at = NOW(),
            updated_at = NOW()
        WHERE ai_daily_briefs.status IN (%s, %s, %s)
        RETURNING status;
    """
    with conn.cursor() as cur:
        cur.execute(
            sql,
            (
                brief_date,
                json.dumps(content, ensure_ascii=False),
                model,
                "generating",
                "blocked",
                "awaiting_approval",
            ),
        )
        row = cur.fetchone()
    return "written" if row is not None else "conflict"


def fetch_brief(conn: psycopg.Connection, brief_date: date) -> dict[str, Any] | None:
    with conn.cursor() as cur:
        cur.execute("SELECT content FROM ai_daily_briefs WHERE brief_date = %s;", (brief_date,))
        row = cur.fetchone()
    return row[0] if row else None


def fetch_public_brief(
    conn: psycopg.Connection,
    brief_date: date,
) -> dict[str, Any] | None:
    """Return content only when the requested brief has been published."""
    sql = """
        SELECT content
        FROM ai_daily_briefs
        WHERE brief_date = %s
          AND status = %s;
    """
    with conn.cursor() as cur:
        cur.execute(sql, (brief_date, "published"))
        row = cur.fetchone()
    return row[0] if row else None


def list_public_briefs(
    conn: psycopg.Connection,
    limit: int,
) -> list[dict[str, Any]]:
    """Return published brief content from newest publication to oldest."""
    sql = """
        SELECT content
        FROM ai_daily_briefs
        WHERE status = %s
        ORDER BY published_at DESC, brief_date DESC
        LIMIT %s;
    """
    with conn.cursor() as cur:
        cur.execute(sql, ("published", limit))
        rows = cur.fetchall()
    return [row[0] for row in rows]


def fetch_previous_brief(conn: psycopg.Connection, before: date) -> dict[str, Any] | None:
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
    # The only interpolated fragment is a fixed literal selected by code.
    sql = """
        SELECT id::text, email, unsubscribe_token::text
        FROM ai_subscribers
        WHERE status = 'active'
        {email_filter}
        ORDER BY created_at;
    """.format(email_filter="AND email = %s" if only_email else "")  # noqa: S608
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
        WITH suppressed AS (
            UPDATE ai_deliveries d
            SET status = 'failed',
                error = 'subscriber inactive before claim',
                updated_at = NOW()
            FROM ai_subscribers s
            WHERE d.subscriber_id = s.id
              AND d.status = 'pending'
              AND s.status <> 'active'
        ),
        claimed AS (
            SELECT d.id
            FROM ai_deliveries d
            JOIN ai_subscribers s ON s.id = d.subscriber_id
            WHERE d.status = 'pending'
              AND s.status = 'active'
            ORDER BY d.created_at
            FOR UPDATE OF d, s SKIP LOCKED
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


def lock_active_subscriber(
    conn: psycopg.Connection,
    *,
    subscriber_id: str,
) -> bool:
    """Lock the subscriber through the transport call and confirm they remain active."""
    sql = """
        SELECT status
        FROM ai_subscribers
        WHERE id = %s
        FOR UPDATE;
    """
    with conn.cursor() as cur:
        cur.execute(sql, (subscriber_id,))
        row = cur.fetchone()
    return row is not None and row[0] == "active"


def mark_suppressed(conn: psycopg.Connection, *, delivery_id: str) -> None:
    """Terminally suppress a claimed delivery whose subscriber is no longer active."""
    sql = """
        UPDATE ai_deliveries
        SET status = 'failed',
            error = 'subscriber inactive before send',
            updated_at = NOW()
        WHERE id = %s;
    """
    with conn.cursor() as cur:
        cur.execute(sql, (delivery_id,))


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
