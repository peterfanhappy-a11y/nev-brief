"""Top 4-6 vehicle sales card with user-aware brand ordering."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

import psycopg

from nev_pipeline.entity_dict import canonicalize_brand

# Canonical → Chinese display name for the sales card (most common NEV brands).
# Used when extracting sales from candidate key_data, which has canonical codes
# but no Chinese display name attached.
_BRAND_DISPLAY_ZH: dict[str, str] = {
    "BYD": "比亚迪", "Tesla": "特斯拉", "NIO": "蔚来",
    "XPeng": "小鹏", "Li Auto": "理想", "AITO": "问界",
    "Xiaomi": "小米", "Zeekr": "极氪", "Leapmotor": "零跑",
    "Aion": "广汽埃安", "Geely": "吉利", "Chery": "奇瑞",
    "Great Wall": "长城", "BAIC": "北汽", "Wuling": "五菱",
    "Hongqi": "红旗", "Avatr": "阿维塔", "Deepal": "深蓝",
    "Voyah": "岚图", "IM Motors": "智己", "Neta": "哪吒",
}


@dataclass(frozen=True)
class SalesEntry:
    brand_code: str
    brand_name: str
    units: int
    yoy: float | None
    wow: float | None


def fetch_latest_sales(
    conn: psycopg.Connection,
    on_or_before: date,
) -> list[SalesEntry]:
    """Latest week_date <= given date, one row per brand_code (most recent)."""
    sql = """
        SELECT DISTINCT ON (brand_code)
            brand_code, brand_name, units, yoy, wow
        FROM vehicle_sales_daily
        WHERE week_date <= %s
        ORDER BY brand_code, week_date DESC;
    """
    with conn.cursor() as cur:
        cur.execute(sql, (on_or_before,))
        return [SalesEntry(*r) for r in cur.fetchall()]


def extract_from_candidates(
    candidates: list[dict[str, Any]],
) -> list[SalesEntry]:
    """Fallback: pull SalesEntry list from daily_briefs candidates when the
    vehicle_sales_daily table is empty.

    Looks for key_data.values.brand_sales in each candidate (Prompt 2 emits
    this standard schema for any 'sales'-typed cluster). Deduplicates by
    brand_code keeping the first / largest units entry.
    """
    by_brand: dict[str, SalesEntry] = {}
    for c in candidates:
        key_data = c.get("key_data") or {}
        if key_data.get("type") != "sales":
            continue
        rows = (key_data.get("values") or {}).get("brand_sales") or []
        if not isinstance(rows, list):
            continue
        for r in rows:
            if not isinstance(r, dict):
                continue
            brand = r.get("brand")
            units = r.get("units")
            if not brand or not isinstance(units, int) or units <= 0:
                continue
            canonical = canonicalize_brand(brand) or brand
            yoy_pct = r.get("yoy_pct")
            yoy = yoy_pct / 100.0 if isinstance(yoy_pct, (int, float)) else None
            entry = SalesEntry(
                brand_code=canonical,
                brand_name=_BRAND_DISPLAY_ZH.get(canonical, canonical),
                units=units,
                yoy=yoy,
                wow=None,
            )
            # Keep the largest units per brand (in case multiple periods)
            if canonical not in by_brand or by_brand[canonical].units < units:
                by_brand[canonical] = entry
    return sorted(by_brand.values(), key=lambda e: -e.units)


def rank_for_user(
    entries: list[SalesEntry],
    user_brands: list[str],
    top_k_min: int = 4,
    top_k_max: int = 10,
) -> list[SalesEntry]:
    """Reorder so user-followed brands come first; trim to [top_k_min, top_k_max].

    Both followed and unfollowed groups are sorted by units desc within their
    group, so the list always reads monotonically inside each section.
    If total entries < top_k_min, return all (no padding).

    top_k_max bumped to 10 (2026-06-07) so monthly CPCA TOP10 fully renders;
    daily / sparse sources naturally fall below 10 and self-trim.
    """
    if not entries:
        return []
    user_set = set(user_brands)
    # Within each group, sort by units desc — otherwise a followed micro-brand
    # appears above an unfollowed mega-brand and the list reads as unsorted.
    followed = sorted(
        (e for e in entries if e.brand_code in user_set),
        key=lambda e: -e.units,
    )
    others = sorted(
        (e for e in entries if e.brand_code not in user_set),
        key=lambda e: -e.units,
    )
    combined = followed + others
    # Aim for top_k_max when data is plentiful; fall back to all when below top_k_min
    if len(combined) < top_k_min:
        return combined
    k = min(top_k_max, len(combined))
    return combined[:k]
