from datetime import date
from unittest.mock import MagicMock

import pytest

from nev_composer.sales_card import SalesEntry, fetch_latest_sales, rank_for_user


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
