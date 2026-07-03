"""Daily 步骤驱动 — 串起 crawl → select → summarize → compose → deliver。

单进程内直接调各阶段（不像 NEV orchestrator 用 subprocess）。每步失败发飞书告警。
dry_run 停在 compose 前（只到生成简报文档，不落投递、不发送）。

与 NEV daily 完全独立：独立 launchd plist、独立 DB 表、独立发件身份。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

import psycopg
from nev_shared.config import get_settings
from nev_shared.feishu import AlertLevel, send_alert
from nev_shared.logger import get_logger

from ai_brief import composer, deliverer, storage
from ai_brief.crawler import runner as crawl_runner
from ai_brief.schema import YesterdayTop
from ai_brief.selector import select
from ai_brief.summarizer import summarize

log = get_logger("ai_brief.runner")


@dataclass
class DailyResult:
    brief_date: str
    crawled: int = 0
    candidates: int = 0
    featured: int = 0
    composed: int = 0
    sent: int = 0
    failed: int = 0
    aborted_at: str | None = None
    steps: list[str] = field(default_factory=list)


def _alert(level: AlertLevel, title: str, body: str) -> None:
    try:
        send_alert(level=level, title=title, body=body)
    except Exception:  # noqa: BLE001 — 告警失败不阻塞主流程
        log.warning("ai_runner.alert_failed", title=title)


async def run_daily(
    conn: psycopg.Connection,
    brief_date: date,
    *,
    only_email: str | None = None,
    dry_run: bool = False,
    skip_crawl: bool = False,
) -> DailyResult:
    r = DailyResult(brief_date=str(brief_date))

    # ── 1. crawl ──────────────────────────────────────────────
    if not skip_crawl:
        articles = await crawl_runner.crawl_all()
        r.crawled = storage.insert_articles(conn, articles)
        conn.commit()
        r.steps.append("crawl")
        log.info("ai_runner.crawled", new=r.crawled, fetched=len(articles))

    # ── 2. select (Stage-1) ───────────────────────────────────
    candidates = storage.fetch_candidates(conn, window_hours=24)
    r.candidates = len(candidates)
    if not candidates:
        r.aborted_at = "select"
        _alert(AlertLevel.P1, "AI 简报中止", f"{brief_date} 无候选文章，crawl 可能失败")
        return r

    selection = await select(candidates)
    if selection is None or not selection.featured_ids():
        r.aborted_at = "select"
        _alert(AlertLevel.P1, "AI 简报中止", f"{brief_date} Stage-1 未选出任何主题内容")
        return r
    r.featured = len(selection.featured_ids())
    r.steps.append("select")

    # ── 3. summarize (Stage-2) ────────────────────────────────
    prev = storage.fetch_previous_brief(conn, brief_date)
    yesterday_top = None
    if prev and prev.get("featured"):
        top = prev["featured"][0]
        yesterday_top = YesterdayTop(headline=top["headline"], url=top["url"])

    brief = await summarize(
        selection, candidates, brief_date=str(brief_date), yesterday_top=yesterday_top
    )
    if brief is None:
        r.aborted_at = "summarize"
        _alert(AlertLevel.P1, "AI 简报中止", f"{brief_date} Stage-2 生成失败")
        return r
    storage.upsert_daily_brief(
        conn, brief_date=brief_date, content=brief.model_dump(mode="json"), model=brief.model
    )
    conn.commit()
    r.steps.append("summarize")
    log.info("ai_runner.summarized", subject=brief.subject)

    if dry_run:
        log.info("ai_runner.dry_run_stop", brief_date=str(brief_date))
        return r

    # ── 4. compose ────────────────────────────────────────────
    comp = composer.compose_for_date(conn, brief_date, only_email=only_email)
    conn.commit()
    r.composed = comp.get("composed", 0)
    r.steps.append("compose")

    # ── 5. deliver ────────────────────────────────────────────
    send_res = deliverer.send_pending(conn)
    r.sent = send_res.sent
    r.failed = send_res.failed
    r.steps.append("deliver")

    if r.failed > 0:
        _alert(AlertLevel.P1, "AI 简报部分投递失败", f"{brief_date} sent={r.sent} failed={r.failed}")
    else:
        _alert(
            AlertLevel.INFO,
            "AI 简报已发送",
            f"{brief_date} · {brief.subject}\ncandidates={r.candidates} "
            f"featured={r.featured} sent={r.sent}",
        )
    return r


def connect() -> psycopg.Connection:
    return psycopg.connect(get_settings().database_url)
