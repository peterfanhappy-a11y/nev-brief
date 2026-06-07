from datetime import date
from unittest.mock import MagicMock

import pytest

from nev_composer.sales_card import (
    SalesEntry,
    extract_from_candidates,
    fetch_latest_sales,
    rank_for_user,
)


def _entry(code, name, units, yoy=None, wow=None):
    return SalesEntry(brand_code=code, brand_name=name, units=units, yoy=yoy, wow=wow)


def test_rank_followed_first():
    entries = [
        _entry("BYD", "比亚迪", 300_000),
        _entry("Tesla", "特斯拉", 55_000),
        _entry("NIO", "蔚来", 21_000),
    ]
    out = rank_for_user(entries, user_brands=["NIO"])
    assert out[0].brand_code == "NIO"


def test_others_sorted_by_units():
    entries = [
        _entry("BYD", "比亚迪", 300_000),
        _entry("Tesla", "特斯拉", 55_000),
        _entry("NIO", "蔚来", 21_000),
    ]
    out = rank_for_user(entries, user_brands=[])
    assert [e.brand_code for e in out] == ["BYD", "Tesla", "NIO"]


def test_caps_at_top_k_max():
    entries = [_entry(f"B{i}", f"name{i}", 100_000 - i*1000) for i in range(10)]
    out = rank_for_user(entries, user_brands=[], top_k_max=6)
    assert len(out) == 6


def test_returns_all_if_below_top_k_min():
    entries = [_entry("BYD", "比亚迪", 300_000), _entry("Tesla", "特斯拉", 55_000)]
    out = rank_for_user(entries, user_brands=[], top_k_min=4)
    assert len(out) == 2  # not forcing 4


def test_empty_returns_empty():
    assert rank_for_user([], user_brands=["BYD"]) == []


def _cand(key_data, **extra):
    return {"cluster_id": "c1", "key_data": key_data, **extra}


def test_extract_from_candidates_basic():
    cands = [
        _cand({
            "type": "sales",
            "values": {
                "brand_sales": [
                    {"brand": "BYD", "units": 349000, "period": "2026-05", "yoy_pct": 42},
                    {"brand": "Li Auto", "units": 34377, "period": "2026-05", "yoy_pct": 82},
                ],
            },
        }),
    ]
    out = extract_from_candidates(cands)
    assert [e.brand_code for e in out] == ["BYD", "Li Auto"]
    assert out[0].units == 349000
    assert out[0].brand_name == "比亚迪"
    assert out[0].yoy == 0.42
    assert out[1].brand_name == "理想"
    assert out[1].yoy == 0.82


def test_extract_skips_non_sales_type():
    cands = [
        _cand({"type": "price", "values": {"brand_sales": [{"brand": "BYD", "units": 1}]}}),
        _cand({"type": "none", "values": {}}),
        _cand({}),
    ]
    assert extract_from_candidates(cands) == []


def test_extract_dedupes_by_brand_keeps_largest():
    cands = [
        _cand({"type": "sales", "values": {"brand_sales": [
            {"brand": "BYD", "units": 100000, "period": "2026-04"},
            {"brand": "BYD", "units": 349000, "period": "2026-05"},
        ]}}),
    ]
    out = extract_from_candidates(cands)
    assert len(out) == 1
    assert out[0].units == 349000


def test_extract_canonicalizes_brand_aliases():
    # canonicalize_brand maps "比亚迪" / "byd" → "BYD"
    cands = [
        _cand({"type": "sales", "values": {"brand_sales": [
            {"brand": "比亚迪", "units": 349000},
            {"brand": "byd", "units": 200000},  # alias, should dedupe with 比亚迪
        ]}}),
    ]
    out = extract_from_candidates(cands)
    assert len(out) == 1
    assert out[0].brand_code == "BYD"
    assert out[0].units == 349000  # largest wins


def test_extract_skips_malformed_rows():
    cands = [
        _cand({"type": "sales", "values": {"brand_sales": [
            {"brand": "BYD", "units": "not-an-int"},
            {"brand": "Tesla", "units": -5},
            {"brand": "", "units": 100},
            {"units": 200},  # missing brand
            {"brand": "NIO", "units": 21000},  # valid
            "not-a-dict",
        ]}}),
        _cand({"type": "sales", "values": {"brand_sales": "not-a-list"}}),
        _cand({"type": "sales", "values": None}),
    ]
    out = extract_from_candidates(cands)
    assert [e.brand_code for e in out] == ["NIO"]


def test_extract_sorts_by_units_desc():
    cands = [
        _cand({"type": "sales", "values": {"brand_sales": [
            {"brand": "NIO", "units": 21000},
            {"brand": "BYD", "units": 349000},
            {"brand": "Tesla", "units": 55000},
        ]}}),
    ]
    out = extract_from_candidates(cands)
    assert [e.units for e in out] == [349000, 55000, 21000]


def test_extract_yoy_handles_missing_or_null():
    cands = [
        _cand({"type": "sales", "values": {"brand_sales": [
            {"brand": "BYD", "units": 349000, "yoy_pct": None},
            {"brand": "Tesla", "units": 55000},  # no yoy_pct key
        ]}}),
    ]
    out = extract_from_candidates(cands)
    assert all(e.yoy is None for e in out)


def test_fetch_latest_sales_sql_shape():
    conn = MagicMock()
    cur = MagicMock()
    cur.__enter__ = lambda s: cur
    cur.__exit__ = lambda *a: None
    cur.fetchall.return_value = []
    conn.cursor.return_value = cur
    fetch_latest_sales(conn, date(2026, 5, 31))
    sql = cur.execute.call_args[0][0]
    assert "DISTINCT ON (brand_code)" in sql
    assert "ORDER BY brand_code, week_date DESC" in sql
    assert cur.execute.call_args[0][1] == (date(2026, 5, 31),)
