"""OPC daily-sharing HTML parser contract tests."""
from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest
from ai_brief.digest.exchange_rates import select_highest_case
from ai_brief.digest.models import Revenue
from ai_brief.digest.opc_parser import parse_opc_digest, parse_revenue

LEGACY_FIXTURE = Path(__file__).parent / "fixtures/opc_sharing_2026-09-14.html"
FIXTURE = Path(__file__).parent / "fixtures/opc_sharing_v4.html"


def test_parses_two_structured_opc_cases_in_source_order() -> None:
    cases = parse_opc_digest(FIXTURE.read_text(encoding="utf-8"))

    assert [(case.index, case.sharer) for case in cases] == [(1, "Alice"), (2, "Bob")]
    assert cases[0].background == "第一款产品缺少稳定获客渠道。"
    assert cases[0].solution == "聚焦垂直用户并自动化交付。"
    assert cases[0].insight == "小团队要优先验证付费需求。"
    assert cases[0].revenue == Revenue(Decimal("2000"), "USD", "MRR", "$2K MRR")
    assert cases[1].revenue == Revenue(Decimal("120000"), "USD", "ARR", "$120K ARR")
    assert cases[1].url == "https://example.com/second"


def test_rejects_legacy_unstructured_cases_without_rewriting_fixture() -> None:
    assert parse_opc_digest(LEGACY_FIXTURE.read_text(encoding="utf-8")) == []


def _structured_fields(
    *,
    background: str = "Background.",
    solution: str = "Solution.",
    insight: str = "Insight.",
    revenue: str = "$10K MRR",
) -> str:
    return (
        f"<p><strong>案例背景：</strong>{background}</p>"
        f"<div><strong>解决方案：</strong>{solution}</div>"
        f"<p><span><strong>案例启示：</strong></span>{insight}</p>"
        f"<p><strong>收入：</strong>{revenue}</p>"
    )


def _two_cases(first_fields: str | None = None) -> str:
    return (
        "<h3>案例1 · Alice：First</h3>" + (first_fields or _structured_fields())
        + '<p><a href="https://example.com/first">原文</a></p>'
        + '<h3>案例2 · Bob：Second</h3>' + _structured_fields(revenue="$2K MRR")
        + '<p><a href="https://example.com/second">原文</a></p>'
    )


def test_income_word_in_background_does_not_consume_or_overwrite_revenue() -> None:
    cases = parse_opc_digest(
        _two_cases(_structured_fields(background="这个产品的月度收入持续增长。"))
    )
    assert [case.index for case in cases] == [1, 2]
    assert cases[0].background == "这个产品的月度收入持续增长。"
    assert cases[0].revenue == Revenue(Decimal("10000"), "USD", "MRR", "$10K MRR")


@pytest.mark.parametrize(("old", "new"), [
    ("<p><strong>案例背景：</strong>Background.</p>", ""),
    ("<div><strong>解决方案：</strong>Solution.</div>", ""),
    ("<p><span><strong>案例启示：</strong></span>Insight.</p>", ""),
    ("<p><strong>收入：</strong>$10K MRR</p>", ""),
    ("Alice", ""),
    ("https://example.com/first", "http://example.com/first"),
])
def test_required_fields_independently_reject_case_one(old: str, new: str) -> None:
    html = _two_cases()
    assert [case.index for case in parse_opc_digest(html)] == [1, 2]
    assert [case.index for case in parse_opc_digest(html.replace(old, new, 1))] == [2]


@pytest.mark.parametrize("field", ["案例背景", "解决方案", "案例启示", "收入"])
def test_duplicate_labeled_field_rejects_case(field: str) -> None:
    extra = f"<p><strong>{field}：</strong>duplicate</p>"
    parsed = parse_opc_digest(_two_cases(_structured_fields() + extra))
    assert [case.index for case in parsed] == [2]


@pytest.mark.parametrize("field", ["案例背景", "解决方案", "案例启示"])
def test_empty_labeled_field_rejects_case(field: str) -> None:
    html = _two_cases().replace(field_map(field), "", 1)
    assert [case.index for case in parse_opc_digest(html)] == [2]


def field_map(field: str) -> str:
    return {"案例背景": "Background.", "解决方案": "Solution.", "案例启示": "Insight."}[field]


def test_preserves_case_header_source_order_independent_of_revenue() -> None:
    cases = parse_opc_digest(_two_cases(_structured_fields(revenue="$1 MRR")))
    assert [(case.index, case.headline) for case in cases] == [(1, "First"), (2, "Second")]


@pytest.mark.parametrize(("source", "alias", "expected_amount", "expected_display"), [
    ("USD 120000 ARR", "年度营收", Decimal("10000"), "约 $10K 美元月度营收"),
    ("CNY 720000 MRR", "月度营收", Decimal("120000"), "约 $120K 美元月度营收"),
])
def test_chinese_periods_preserve_conversion_selection_and_display(
    source: str, alias: str, expected_amount: Decimal, expected_display: str,
) -> None:
    for revenue_text in (source, source.rsplit(" ", 1)[0] + " " + alias):
        cases = parse_opc_digest(_two_cases(_structured_fields(revenue=revenue_text)))
        assert len(cases) == 2
        selected = select_highest_case(
            cases, lambda: {"EUR": Decimal("1"), "USD": Decimal("1.2"), "CNY": Decimal("7.2")}
        )
        assert selected.candidate.index == 1
        assert selected.monthly_revenue_usd == expected_amount
        assert selected.revenue_display == expected_display


@pytest.mark.parametrize("period", [
    "月收入", "周度营收", "MRR 年度营收", "ARR 月度营收", "月度营收 年度营收",
])
def test_rejects_unknown_or_conflicting_periods(period: str) -> None:
    assert parse_revenue(f"USD 120000 {period}") is None


@pytest.mark.parametrize(
    "revenue_text",
    ["¥100K MRR", "￥100K MRR", "$100K", "100K MRR", "$many MRR"],
)
def test_rejects_ambiguous_or_incomplete_revenue(revenue_text: str) -> None:
    assert parse_revenue(revenue_text) is None


@pytest.mark.parametrize(
    ("revenue_text", "currency"),
    [
        ("$1 MRR", "USD"),
        ("USD 1 MRR", "USD"),
        ("美元 1 MRR", "USD"),
        ("€1 MRR", "EUR"),
        ("EUR 1 MRR", "EUR"),
        ("欧元 1 MRR", "EUR"),
        ("£1 MRR", "GBP"),
        ("GBP 1 MRR", "GBP"),
        ("英镑 1 MRR", "GBP"),
        ("CNY 1 MRR", "CNY"),
        ("RMB 1 MRR", "CNY"),
        ("人民币 1 MRR", "CNY"),
        ("JPY 1 MRR", "JPY"),
        ("日元 1 MRR", "JPY"),
        ("CAD 1 MRR", "CAD"),
        ("AUD 1 MRR", "AUD"),
        ("XXX 1 MRR", "XXX"),
    ],
)
def test_parses_explicit_currency_tokens(revenue_text: str, currency: str) -> None:
    assert parse_revenue(revenue_text) == Revenue(Decimal("1"), currency, "MRR", revenue_text)


@pytest.mark.parametrize(
    ("revenue_text", "amount"),
    [("USD 1,234.5 MRR", Decimal("1234.5")), ("$1,000 MRR", Decimal("1000"))],
)
def test_parses_legally_grouped_thousands_separators(revenue_text: str, amount: Decimal) -> None:
    assert parse_revenue(revenue_text) == Revenue(amount, "USD", "MRR", revenue_text)


@pytest.mark.parametrize("revenue_text", ["USD 12,34 MRR", "USD 1,23,456 MRR", "USD ,123 MRR"])
def test_rejects_illegally_grouped_thousands_separators(revenue_text: str) -> None:
    assert parse_revenue(revenue_text) is None


def test_excludes_complete_cases_outside_indexes_one_and_two() -> None:
    fields = "<p>案例背景：背景</p><p>解决方案：方案</p><p>案例启示：启示</p>"
    html = (
        f"<h3>案例 0 · Zero：完整但越界</h3>{fields}<p>收入：$1 MRR</p>"
        '<p><a href="https://example.com/zero">阅读原文</a></p>'
        f"<h3>案例 1 · One：完整合法</h3>{fields}<p>收入：$1 MRR</p>"
        '<p><a href="https://example.com/one">阅读原文</a></p>'
        f"<h3>案例 3 · Three：完整但越界</h3>{fields}<p>收入：$1 MRR</p>"
        '<p><a href="https://example.com/three">阅读原文</a></p>'
    )

    assert [(case.index, case.sharer) for case in parse_opc_digest(html)] == [(1, "One")]


def test_excludes_complete_case_when_duplicate_header_is_incomplete() -> None:
    fields = "<p>案例背景：背景</p><p>解决方案：方案</p><p>案例启示：启示</p>"
    html = (
        "<h3>案例 1 · Missing fields：重复但不完整</h3><p>收入：$1 MRR</p>"
        '<p><a href="https://example.com/first">阅读原文</a></p>'
        f"<h3>案例 1 · Complete duplicate：重复且完整</h3>{fields}"
        '<p>收入：$1 MRR</p><p><a href="https://example.com/second">阅读原文</a></p>'
        f"<h3>案例 2 · Unique：唯一完整</h3>{fields}<p>收入：$1 MRR</p>"
        '<p><a href="https://example.com/unique">阅读原文</a></p>'
    )

    assert [(case.index, case.sharer) for case in parse_opc_digest(html)] == [(2, "Unique")]
