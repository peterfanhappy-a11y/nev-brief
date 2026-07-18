"""Daily 步骤驱动 — digest 驱动版。

今日AI / AI大神 两模块从 Gmail digest 邮件生成（见 ai_brief.digest.generate）。
模块③大模型研究 ④智能体研究 + 工具/课堂 内容生成方式尚未定义，暂不产出
（模板会自动省略空板块），后续和用户逐个定义后再接 crawler/summarizer。

流程：build_digest_modules → 组装 AiBriefContent → upsert → compose → deliver。
今日AI digest 缺失 = 内容主干缺失 → 告警并中止。与 NEV daily 完全独立。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

import psycopg
from nev_shared.config import get_settings
from nev_shared.feishu import AlertLevel, send_alert
from nev_shared.logger import get_logger

from ai_brief import composer, config, deliverer, storage
from ai_brief.digest.generate import build_digest_modules
from ai_brief.schema import AiBriefContent, YesterdayTop

log = get_logger("ai_brief.runner")


@dataclass
class DailyResult:
    brief_date: str
    modules: int = 0
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


def _yesterday_top(conn: psycopg.Connection, brief_date: date) -> YesterdayTop | None:
    prev = storage.fetch_previous_brief(conn, brief_date)
    if not prev:
        return None
    ta = prev.get("today_ai") or {}
    stories = ta.get("stories") or []
    if stories:
        s0 = stories[0]
        if s0.get("headline") and s0.get("url"):
            return YesterdayTop(headline=s0["headline"], url=s0["url"])
    # 兼容旧结构（featured）
    feat = prev.get("featured") or []
    if feat and feat[0].get("headline") and feat[0].get("url"):
        return YesterdayTop(headline=feat[0]["headline"], url=feat[0]["url"])
    return None


async def run_daily(
    conn: psycopg.Connection,
    brief_date: date,
    *,
    only_email: str | None = None,
    dry_run: bool = False,
    skip_crawl: bool = False,  # 保留签名兼容；digest 版不抓取
) -> DailyResult:
    r = DailyResult(brief_date=str(brief_date))
    date_str = str(brief_date)

    # ── 1. digest 模块（今日AI / AI大神）─────────────────────────
    bundle = await build_digest_modules(date_str)
    if bundle.today_ai is None:
        r.aborted_at = "digest"
        _alert(AlertLevel.P1, "AI 简报中止", f"{date_str} 今日AI digest 缺失/解析失败，未发送")
        return r
    r.steps.append("digest")
    if bundle.ai_masters is None:
        _alert(AlertLevel.P2, "AI大神 digest 缺失", f"{date_str} AI大神模块空缺，仅发今日AI")

    # ── 2. 组装 brief 文档 ────────────────────────────────────────
    intro = bundle.intro_bullets or [s.headline for s in bundle.today_ai.stories]
    subject = bundle.subject or bundle.today_ai.stories[0].headline
    brief = AiBriefContent(
        brief_date=date_str,
        subject=subject[:44],
        preheader=bundle.preheader[:60],
        editorial=bundle.editorial[:220],
        intro_bullets=intro[:4],
        today_ai=bundle.today_ai,
        ai_masters=bundle.ai_masters,
        featured=[],
        yesterday_top=_yesterday_top(conn, brief_date),
        model=config.get_model(),
    )
    storage.upsert_daily_brief(
        conn, brief_date=brief_date, content=brief.model_dump(mode="json"), model=brief.model
    )
    conn.commit()
    r.modules = 1 + (1 if bundle.ai_masters else 0)
    r.steps.append("assemble")
    log.info("ai_runner.assembled", subject=brief.subject, modules=r.modules)

    if dry_run:
        log.info("ai_runner.dry_run_stop", brief_date=date_str)
        return r

    # ── 3. compose ────────────────────────────────────────────────
    comp = composer.compose_for_date(conn, brief_date, only_email=only_email)
    conn.commit()
    r.composed = comp.get("composed", 0)
    r.steps.append("compose")

    # ── 4. deliver ────────────────────────────────────────────────
    send_res = deliverer.send_pending(conn)
    r.sent = send_res.sent
    r.failed = send_res.failed
    r.steps.append("deliver")

    if r.failed > 0:
        _alert(AlertLevel.P1, "AI 简报部分投递失败", f"{date_str} sent={r.sent} failed={r.failed}")
    else:
        _alert(
            AlertLevel.INFO, "AI 简报已发送",
            f"{date_str} · {brief.subject}\nmodules={r.modules} sent={r.sent}",
        )
    return r


def connect() -> psycopg.Connection:
    return psycopg.connect(get_settings().database_url)
