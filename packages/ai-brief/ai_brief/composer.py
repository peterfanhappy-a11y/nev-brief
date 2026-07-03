"""Composer — 把 ai_daily_briefs 文档渲染成每订阅者一封的 HTML/text，写 ai_deliveries。

评分链接需在渲染前知道 delivery_id：重跑时复用已有 id（已发邮件里的链接仍有效），
首次用 uuid4。渲染顺序 = 定 id → 渲染 → upsert。psycopg 由调用方 commit。
"""
from __future__ import annotations

from datetime import date, datetime
from uuid import uuid4

import jinja2
import psycopg
from nev_shared.logger import get_logger

from ai_brief import config
from ai_brief.schema import AiBriefContent
from ai_brief import storage

log = get_logger("ai_brief.composer")

_WEEKDAYS = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]


def _theme_color(theme) -> str:  # noqa: ANN001
    key = theme.value if hasattr(theme, "value") else str(theme)
    return config.THEME_META.get(key, {}).get("color", "#4F46E5")


def _make_env(autoescape: bool) -> jinja2.Environment:
    env = jinja2.Environment(
        loader=jinja2.FileSystemLoader(str(config.TEMPLATES_DIR)),
        autoescape=jinja2.select_autoescape(["html", "j2"]) if autoescape else False,
        trim_blocks=True,
        lstrip_blocks=True,
    )
    env.globals["theme_color"] = _theme_color
    return env


def _date_human(d: date) -> str:
    return f"{d.year}年{d.month}月{d.day}日 {_WEEKDAYS[d.weekday()]}"


def _base_ctx(brief: AiBriefContent, brief_date: date) -> dict:
    return {
        "brief": brief,
        "date_human": _date_human(brief_date),
        "author_name": config.AUTHOR_NAME,
        "author_photo_url": config.AUTHOR_PHOTO_URL,
        "logo_email_url": config.LOGO_EMAIL_URL,
        "banner_tagline": config.BANNER_TAGLINE,
        "social_icons": config.SOCIAL_ICONS,
        "rate_base": config.RATE_BASE_URL,
        "web_base": config.WEB_BASE_URL,
    }


def render(
    brief: AiBriefContent,
    brief_date: date,
    *,
    delivery_id: str,
    unsubscribe_token: str,
) -> tuple[str, str]:
    """渲染单封邮件，返回 (html, text)。"""
    ctx = _base_ctx(brief, brief_date)
    ctx["delivery_id"] = delivery_id
    ctx["unsubscribe_url"] = f"{config.UNSUBSCRIBE_PREFIX}{unsubscribe_token}&product=ai"
    html = _make_env(autoescape=True).get_template("ai_brief.html.j2").render(**ctx)
    text = _make_env(autoescape=False).get_template("ai_brief.txt.j2").render(**ctx)
    return html, text


def render_preview(brief: AiBriefContent, brief_date: date) -> str:
    """预览用 HTML（假 delivery_id / token），不落库。"""
    html, _ = render(
        brief, brief_date,
        delivery_id="preview-0000", unsubscribe_token="preview-token",
    )
    return html


def compose_for_date(
    conn: psycopg.Connection,
    brief_date: date,
    *,
    only_email: str | None = None,
) -> dict:
    """为当日简报的所有 active 订阅者生成投递记录。返回统计。不 commit。"""
    raw = storage.fetch_brief(conn, brief_date)
    if raw is None:
        log.error("ai_composer.no_brief", brief_date=str(brief_date))
        return {"composed": 0, "reason": "no_brief"}
    brief = AiBriefContent.model_validate(raw)

    subs = storage.fetch_active_subscribers(conn, only_email=only_email)
    composed = 0
    for sub in subs:
        did = storage.get_existing_delivery_id(
            conn, subscriber_id=sub.id, brief_date=brief_date
        ) or str(uuid4())
        html, text = render(
            brief, brief_date,
            delivery_id=did, unsubscribe_token=sub.unsubscribe_token,
        )
        storage.upsert_delivery(
            conn,
            delivery_id=did,
            subscriber_id=sub.id,
            brief_date=brief_date,
            subject=brief.subject,
            content_html=html,
            content_text=text,
        )
        composed += 1
    log.info("ai_composer.done", brief_date=str(brief_date), composed=composed)
    return {"composed": composed, "subject": brief.subject}


def today() -> date:
    return datetime.now().date()
