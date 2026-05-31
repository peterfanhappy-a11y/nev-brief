from datetime import date
from unittest.mock import MagicMock

import pytest

from nev_summarizer.sales.caam_parser import (
    SalesRecord, extract_sales_from_article, run_caam_extraction,
)
from nev_summarizer.sales.storage import upsert_vehicle_sales_records


@pytest.mark.asyncio
async def test_extract_returns_records(monkeypatch):
    async def fake(system, user, **kw):
        return {
            "month": "2026-05",
            "records": [
                {"brand_canonical": "BYD", "brand_name_zh": "比亚迪",
                 "units": 300000, "yoy": 0.25, "wow": None},
                {"brand_canonical": "Tesla", "brand_name_zh": "特斯拉",
                 "units": 55000, "yoy": -0.03, "wow": 0.12},
            ],
        }
    monkeypatch.setattr(
        "nev_summarizer.sales.caam_parser.extract_json_with_retry", fake,
    )
    records = await extract_sales_from_article("中汽协 5 月销量月报：比亚迪 30 万 ...")
    assert len(records) == 2
    assert records[0].brand_code == "BYD"
    assert records[0].units == 300000
    assert records[0].yoy == 0.25
    assert records[0].wow is None
    assert records[1].yoy == -0.03


@pytest.mark.asyncio
async def test_extract_returns_empty_when_deepseek_fails(monkeypatch):
    async def fake(*a, **kw):
        return None
    monkeypatch.setattr(
        "nev_summarizer.sales.caam_parser.extract_json_with_retry", fake,
    )
    records = await extract_sales_from_article("anything")
    assert records == []


@pytest.mark.asyncio
async def test_extract_skips_malformed_records(monkeypatch):
    async def fake(*a, **kw):
        return {
            "records": [
                {"brand_canonical": "BYD", "units": 100000},  # ok
                {"brand_canonical": "Tesla"},                  # missing units
                {"units": 50000},                              # missing brand
                {"brand_canonical": "X", "units": "300000"},   # str units
                "not a dict",                                  # wrong type
            ],
        }
    monkeypatch.setattr(
        "nev_summarizer.sales.caam_parser.extract_json_with_retry", fake,
    )
    records = await extract_sales_from_article("x")
    assert len(records) == 1
    assert records[0].brand_code == "BYD"


@pytest.mark.asyncio
async def test_extract_canonicalizes_alias(monkeypatch):
    async def fake(*a, **kw):
        return {"records": [{"brand_canonical": "比亚迪", "units": 100000}]}
    monkeypatch.setattr(
        "nev_summarizer.sales.caam_parser.extract_json_with_retry", fake,
    )
    records = await extract_sales_from_article("x")
    assert records[0].brand_code == "BYD"


def test_upsert_uses_on_conflict():
    conn = MagicMock()
    cur = MagicMock()
    cur.__enter__ = lambda s: cur
    cur.__exit__ = lambda *a: None
    conn.cursor.return_value = cur

    records = [
        SalesRecord(brand_code="BYD", brand_name="比亚迪", units=300000, yoy=0.25, wow=None),
    ]
    n = upsert_vehicle_sales_records(conn, records, date(2026, 5, 31), "CAAM")
    assert n == 1
    sql = cur.execute.call_args[0][0]
    assert "INSERT INTO vehicle_sales_daily" in sql
    assert "ON CONFLICT (brand_code, week_date, source) DO UPDATE" in sql
    args = cur.execute.call_args[0][1]
    assert args[:4] == ("BYD", "比亚迪", date(2026, 5, 31), 300000)


def test_upsert_dedup_count():
    conn = MagicMock()
    cur = MagicMock()
    cur.__enter__ = lambda s: cur
    cur.__exit__ = lambda *a: None
    conn.cursor.return_value = cur
    records = [
        SalesRecord(brand_code="BYD", brand_name="比亚迪", units=300000, yoy=0.25, wow=None),
        SalesRecord(brand_code="Tesla", brand_name="特斯拉", units=55000, yoy=None, wow=None),
    ]
    n = upsert_vehicle_sales_records(conn, records, date(2026, 5, 31), "CAAM")
    assert n == 2


def test_month_end_helper():
    from nev_summarizer.sales.caam_parser import _month_end
    assert _month_end("2026-02") == date(2026, 2, 28)
    assert _month_end("2024-02") == date(2024, 2, 29)  # leap
    assert _month_end("2026-05") == date(2026, 5, 31)
    assert _month_end("2026-04") == date(2026, 4, 30)
