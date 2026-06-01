"""Renderer tests + snapshot."""
from __future__ import annotations

import pytest

from nev_composer.renderer import render_html, render_text


def _sample_ctx():
    return {
        "brief_date": "2026-05-31",
        "brief_date_human": "2026年5月31日",
        "subscriber_email": "test@example.com",
        "manage_url": "https://nev-brief.com/manage?token=abc",
        "unsubscribe_url": "https://nev-brief.com/unsubscribe?token=abc",
        "web_url": "https://nev-brief.com/d/2026-05-31",
        "sales_card": [
            {"brand_code": "BYD", "brand_name": "比亚迪", "units": 305000, "yoy": 0.25, "wow": None},
            {"brand_code": "Tesla", "brand_name": "特斯拉", "units": 55000, "yoy": -0.03, "wow": 0.12},
        ],
        "top_items": [
            {
                "title": "比亚迪海豹06 EV上市",
                "summary": "5月30日，比亚迪发布全新海豹06 EV，售价8.98-13.98万元。",
                "brands": ["BYD"],
                "topics": ["new_car", "sales"],
                "source_links": [
                    {"name": "36氪", "url": "https://36kr.com/x"},
                    {"name": "电车汇", "url": "https://dcwauto.com/y"},
                ],
                "web_url": "https://nev-brief.com/d/2026-05-31/cl1",
            },
            {
                "title": "Tesla Model Y 焕新版6月交付",
                "summary": "Model Y 焕新版起售26.4万元，6月起交付。",
                "brands": ["Tesla"],
                "topics": ["new_car"],
                "source_links": [{"name": "Reuters", "url": "https://reuters.com/z"}],
                "web_url": "https://nev-brief.com/d/2026-05-31/cl2",
            },
        ],
        "overseas_items": [
            {"title": "Rivian R2 EPA认证", "web_url": "https://nev-brief.com/d/2026-05-31/cl3"},
        ],
    }


def test_html_includes_brand_color():
    out = render_html(_sample_ctx())
    assert "#0066FF" in out
    assert "#00C896" in out


def test_html_includes_unsubscribe_url():
    out = render_html(_sample_ctx())
    assert "https://nev-brief.com/unsubscribe?token=abc" in out


def test_html_renders_all_top_items():
    ctx = _sample_ctx()
    out = render_html(ctx)
    for item in ctx["top_items"]:
        assert item["title"] in out


def test_html_topic_labels_in_chinese():
    out = render_html(_sample_ctx())
    assert "新车" in out  # topic 'new_car' translated
    assert "销量" in out


def test_html_no_sales_card_section_when_empty():
    ctx = {**_sample_ctx(), "sales_card": []}
    out = render_html(ctx)
    assert "昨日核心数据" not in out


def test_text_includes_all_titles():
    ctx = _sample_ctx()
    out = render_text(ctx)
    for item in ctx["top_items"]:
        assert item["title"] in out


def test_text_no_html_tags():
    out = render_text(_sample_ctx())
    # plain text should not leak any HTML tags
    assert "<table" not in out
    assert "<div" not in out
    assert "</a>" not in out


def test_text_includes_unsubscribe_url():
    out = render_text(_sample_ctx())
    assert "https://nev-brief.com/unsubscribe?token=abc" in out


def test_text_overseas_section_when_present():
    out = render_text(_sample_ctx())
    assert "海外动态" in out
    assert "Rivian R2" in out


def test_text_no_overseas_section_when_empty():
    ctx = {**_sample_ctx(), "overseas_items": []}
    out = render_text(ctx)
    assert "海外动态" not in out
