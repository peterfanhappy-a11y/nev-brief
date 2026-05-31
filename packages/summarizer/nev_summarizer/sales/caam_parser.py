"""CAAM monthly sales extraction via DeepSeek."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

import psycopg

from nev_pipeline.deepseek_client import extract_json_with_retry
from nev_pipeline.entity_dict import canonicalize_brand
from nev_shared.logger import get_logger

from nev_summarizer.sales.storage import upsert_vehicle_sales_records

log = get_logger("sales.caam")

# DeepSeek prompt for sales extraction
SYSTEM_PROMPT_SALES = """你是汽车行业数据分析师。
从中汽协月报新闻中提取车企销量数据。

【车企别名表】
比亚迪/BYD, 特斯拉/Tesla, 蔚来/NIO, 小鹏/XPeng, 理想/Li Auto,
华为/AITO/问界, 小米/Xiaomi, 极氪/Zeekr, 零跑/Leapmotor,
广汽埃安/Aion, 长城/魏牌/欧拉, 吉利/银河, 奇瑞/iCAR, 五菱/MG
(canonical 用英文)

【严格 JSON】
{
  "month": "YYYY-MM",
  "records": [
    {
      "brand_canonical": "BYD",
      "brand_name_zh": "比亚迪",
      "units": 300000,
      "yoy": 0.25,
      "wow": null
    }
  ]
}
未提及的字段填 null。units 必须是整数（单位：辆）。yoy/wow 必须是小数（25% = 0.25）。
不要解释，只输出 JSON。"""


@dataclass(frozen=True)
class SalesRecord:
    brand_code: str       # canonical
    brand_name: str       # Chinese display name
    units: int
    yoy: float | None
    wow: float | None


async def extract_sales_from_article(text: str) -> list[SalesRecord]:
    """Call DeepSeek to extract sales records from a CAAM article body.

    Returns empty list on failure (DeepSeek API / JSON parse / missing fields).
    """
    if not text or not text.strip():
        return []
    user = f"中汽协月报正文（截断 2000 字）：\n{text[:2000]}"
    result = await extract_json_with_retry(
        SYSTEM_PROMPT_SALES, user, max_tokens=800, temperature=0.0,
    )
    if result is None:
        log.warning("sales_extract_failed", reason="deepseek_returned_none")
        return []

    records: list[SalesRecord] = []
    for r in result.get("records", []):
        if not isinstance(r, dict):
            continue
        units = r.get("units")
        canonical = r.get("brand_canonical") or r.get("brand_name_zh")
        if not canonical or not isinstance(units, int) or units < 0:
            continue
        # Canonicalize through entity_dict in case LLM returned alias
        canonical = canonicalize_brand(canonical) or str(canonical)
        records.append(SalesRecord(
            brand_code=canonical,
            brand_name=str(r.get("brand_name_zh") or canonical),
            units=units,
            yoy=float(r["yoy"]) if isinstance(r.get("yoy"), (int, float)) else None,
            wow=float(r["wow"]) if isinstance(r.get("wow"), (int, float)) else None,
        ))
    return records


def _month_end(month: str) -> date:
    """'2026-05' → date(2026,5,31). Uses calendar lib for safe last day."""
    import calendar
    year, mon = month.split("-")
    year, mon = int(year), int(mon)
    last_day = calendar.monthrange(year, mon)[1]
    return date(year, mon, last_day)


async def run_caam_extraction(
    conn: psycopg.Connection,
    month: str,
    limit: int = 10,
) -> dict[str, Any]:
    """Fetch CAAM articles for the month, extract sales, upsert into vehicle_sales_daily.

    month: 'YYYY-MM'. Targets articles_raw rows whose source category=='association'
    and source name LIKE '中汽协%' and published_at within the month.
    """
    # Query CAAM articles for this month
    year, mon = month.split("-")
    year, mon = int(year), int(mon)
    sql = """
        SELECT r.id, r.title, r.content
        FROM articles_raw r
        JOIN sources s ON s.id = r.source_id
        WHERE s.name LIKE '中汽协%%'
          AND EXTRACT(YEAR FROM r.published_at) = %s
          AND EXTRACT(MONTH FROM r.published_at) = %s
        ORDER BY r.published_at DESC
        LIMIT %s;
    """
    with conn.cursor() as cur:
        cur.execute(sql, (year, mon, limit))
        rows = cur.fetchall()

    log.info("caam_articles_loaded", month=month, n=len(rows))

    month_end = _month_end(month)
    all_records: list[SalesRecord] = []
    for raw_id, title, content in rows:
        text = f"{title}\n\n{content or ''}"
        recs = await extract_sales_from_article(text)
        all_records.extend(recs)
        log.info("caam_article_extracted", raw_id=str(raw_id), n_records=len(recs))

    # Dedupe by brand_code — keep first (DeepSeek may report same brand twice)
    seen: set[str] = set()
    unique: list[SalesRecord] = []
    for r in all_records:
        if r.brand_code in seen:
            continue
        seen.add(r.brand_code)
        unique.append(r)

    n_upserted = upsert_vehicle_sales_records(
        conn, records=unique, week_date=month_end, source="CAAM",
    )
    conn.commit()
    return {
        "month": month,
        "articles_processed": len(rows),
        "sales_upserted": n_upserted,
    }
