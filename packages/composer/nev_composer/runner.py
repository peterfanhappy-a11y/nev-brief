"""Composer pipeline orchestrator — per-subscriber."""
from __future__ import annotations

import os
from dataclasses import asdict
from datetime import date
from typing import Any

import psycopg

from nev_shared.logger import get_logger

from nev_composer.personalization import UserPreferences, select_diverse_top_n
from nev_composer.renderer import render_html, render_text
from nev_composer.sales_card import fetch_latest_sales, rank_for_user
from nev_composer.storage import (
    ActiveSubscriber,
    fetch_active_subscribers,
    fetch_daily_brief_candidates,
    upsert_delivery,
)

log = get_logger("composer.runner")


OVERSEAS_TOPIC = "overseas"


def _build_render_context(
    sub: ActiveSubscriber,
    top_items: list[dict[str, Any]],
    overseas_items: list[dict[str, Any]],
    sales_card_entries: list,
    brief_date: date,
) -> dict[str, Any]:
    base_url = os.environ.get("WEB_BASE_URL", "https://nev-brief.com")
    return {
        "brief_date": str(brief_date),
        "brief_date_human": brief_date.strftime("%Y年%m月%d日"),
        "subscriber_email": sub.email,
        "manage_url": f"{base_url}/manage?token={sub.unsubscribe_token}",
        "unsubscribe_url": f"{base_url}/unsubscribe?token={sub.unsubscribe_token}",
        "web_url": f"{base_url}/d/{brief_date}",
        "sales_card": [asdict(s) for s in sales_card_entries],
        "top_items": top_items,
        "overseas_items": overseas_items,
    }


def _split_overseas(top_items: list[dict[str, Any]]) -> tuple[list[dict], list[dict]]:
    """Split top-N items into (main, overseas_folded). overseas = topics has 'overseas'."""
    main: list[dict] = []
    overseas: list[dict] = []
    for item in top_items:
        if OVERSEAS_TOPIC in (item.get("topics") or []):
            overseas.append(item)
        else:
            main.append(item)
    return main, overseas


def _add_web_urls(items: list[dict], brief_date: date, base_url: str) -> list[dict]:
    """Annotate each item with a web_url pointing to /d/[date]/[short-cluster-id]."""
    out = []
    for item in items:
        cluster_id = str(item.get("cluster_id", ""))
        out.append({
            **item,
            "web_url": f"{base_url}/d/{brief_date}/{cluster_id[:8]}",
        })
    return out


def run_for_date(
    conn: psycopg.Connection,
    brief_date: date,
    top_n: int = 10,
    only_subscriber_email: str | None = None,
) -> dict[str, Any]:
    """End-to-end composer run for brief_date.

    only_subscriber_email: if set, only compose for that one subscriber (testing).
    Each subscriber commits independently — one failure doesn't block others.
    """
    candidates = fetch_daily_brief_candidates(conn, brief_date)
    if not candidates:
        log.warning("no_candidates_for_date", brief_date=str(brief_date))
        return {"brief_date": str(brief_date), "subscribers": 0, "composed": 0,
                "reason": "no_candidates"}

    subscribers = fetch_active_subscribers(conn)
    if only_subscriber_email:
        subscribers = [
            s for s in subscribers
            if s.email.lower() == only_subscriber_email.lower()
        ]

    sales_entries = fetch_latest_sales(conn, brief_date)
    base_url = os.environ.get("WEB_BASE_URL", "https://nev-brief.com")

    composed = 0
    failed = 0
    for sub in subscribers:
        try:
            prefs = UserPreferences(brands=sub.pref_brands, topics=sub.pref_topics)
            ranked = select_diverse_top_n(candidates, prefs, brief_date, n=top_n)
            ranked_with_urls = _add_web_urls(ranked, brief_date, base_url)
            main_items, overseas = _split_overseas(ranked_with_urls)
            sales_card = rank_for_user(sales_entries, sub.pref_brands)

            ctx = _build_render_context(sub, main_items, overseas, sales_card, brief_date)
            html = render_html(ctx)
            text = render_text(ctx)
            selected_items = [str(item.get("cluster_id", "")) for item in ranked]

            upsert_delivery(conn, sub.id, brief_date, html, text, selected_items)
            conn.commit()  # 每个 subscriber 一次 commit (psycopg commit-before-close 教训)
            composed += 1
        except Exception as exc:  # noqa: BLE001
            log.warning("compose_failed", subscriber_id=sub.id, email=sub.email, error=str(exc))
            conn.rollback()
            failed += 1

    log.info("compose_done",
             brief_date=str(brief_date),
             subscribers=len(subscribers), composed=composed, failed=failed)
    return {
        "brief_date": str(brief_date),
        "subscribers": len(subscribers),
        "composed": composed,
        "failed": failed,
    }
