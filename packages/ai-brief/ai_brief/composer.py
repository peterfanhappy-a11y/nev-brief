"""Composer — render frozen approved content into insert-only deliveries.

Delivery creation is reachable only from ``runner.release_approved``. Existing
rows are never rewritten, so sent/failed payloads and rating links stay frozen.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any, cast
from uuid import uuid4

import jinja2
import psycopg
from nev_shared.logger import get_logger

from ai_brief import config, storage
from ai_brief.schema import AiBriefContent

log = get_logger("ai_brief.composer")

_WEEKDAYS = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]


def _theme_color(theme: object) -> str:
    key = cast(str, theme.value if hasattr(theme, "value") else str(theme))
    return config.THEME_META.get(key, {}).get("color", "#4F46E5")


def _theme_label(theme: object) -> str:
    """渲染时从 config 实时取标签，而非用 brief 里存的旧值（改标签立即生效）。"""
    key = cast(str, theme.value if hasattr(theme, "value") else str(theme))
    return config.THEME_META.get(key, {}).get("label", key)


def _make_env(autoescape: bool) -> jinja2.Environment:
    env = jinja2.Environment(
        loader=jinja2.FileSystemLoader(str(config.TEMPLATES_DIR)),
        # Text-email templates intentionally render without HTML escaping.
        autoescape=(  # noqa: S701
            jinja2.select_autoescape(["html", "j2"]) if autoescape else False
        ),
        trim_blocks=True,
        lstrip_blocks=True,
    )
    env.globals["theme_color"] = _theme_color
    env.globals["theme_label"] = _theme_label
    return env


def _date_human(d: date) -> str:
    return f"{d.year}年{d.month}月{d.day}日 {_WEEKDAYS[d.weekday()]}"


def greeting_name(email: str) -> str:
    """从邮箱推断称呼名。peter.fan.happy@x → Peter；取不到像样的名就返回空串。"""
    local = (email or "").split("@")[0]
    token = ""
    for ch in local:
        if ch.isalpha():
            token += ch
        elif token:
            break
    if len(token) < 2 or len(token) > 20:
        return ""
    return token[:1].upper() + token[1:].lower()


def _base_ctx(brief: AiBriefContent, brief_date: date) -> dict[str, Any]:
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
    email: str = "",
) -> tuple[str, str]:
    """渲染单封邮件，返回 (html, text)。"""
    ctx = _base_ctx(brief, brief_date)
    ctx["delivery_id"] = delivery_id
    ctx["greeting_name"] = greeting_name(email)
    ctx["unsubscribe_url"] = f"{config.UNSUBSCRIBE_PREFIX}{unsubscribe_token}&product=ai"
    html = _make_env(autoescape=True).get_template("ai_brief.html.j2").render(**ctx)
    text = _make_env(autoescape=False).get_template("ai_brief.txt.j2").render(**ctx)
    return html, text


def render_preview(brief: AiBriefContent, brief_date: date) -> str:
    """预览用 HTML（假 delivery_id / token），不落库。"""
    html, _ = render(
        brief,
        brief_date,
        delivery_id="preview-0000",
        unsubscribe_token="preview-token",  # noqa: S106 - inert preview placeholder
    )
    return html


def compose_for_date(
    conn: psycopg.Connection,
    brief_date: date,
    *,
    only_email: str | None = None,
) -> dict[str, Any]:
    """Reject the retired pre-approval delivery-creation entry point."""
    del conn, brief_date, only_email
    raise RuntimeError("delivery creation requires runner.release_approved")


def compose_frozen_brief(
    conn: psycopg.Connection,
    brief_date: date,
    content: dict[str, Any],
    *,
    only_email: str | None = None,
) -> dict[str, Any]:
    """Render locked, frozen content and insert only missing delivery rows."""
    brief = AiBriefContent.model_validate(content)

    subs = storage.fetch_active_subscribers(conn, only_email=only_email)
    composed = 0
    for sub in subs:
        did = str(uuid4())
        html, text = render(
            brief, brief_date,
            delivery_id=did, unsubscribe_token=sub.unsubscribe_token, email=sub.email,
        )
        inserted = storage.insert_delivery_if_missing(
            conn,
            delivery_id=did,
            subscriber_id=sub.id,
            brief_date=brief_date,
            subject=brief.subject,
            content_html=html,
            content_text=text,
        )
        composed += int(inserted)
    log.info("ai_composer.done", brief_date=str(brief_date), composed=composed)
    return {"composed": composed, "subject": brief.subject}


def today() -> date:
    return datetime.now().date()
