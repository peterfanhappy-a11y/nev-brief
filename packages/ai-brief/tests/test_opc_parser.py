"""OPC daily-sharing HTML parser contract tests."""
from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest
from ai_brief.digest.exchange_rates import select_highest_case
from ai_brief.digest.models import Revenue
from ai_brief.digest.opc_parser import parse_opc_digest, parse_revenue

FIXTURE = Path(__file__).parent / "fixtures/opc_sharing_2026-09-14.html"


def test_parses_two_real_opc_cases() -> None:
    cases = parse_opc_digest(FIXTURE.read_text(encoding="utf-8"))

    assert [(case.index, case.sharer) for case in cases] == [(1, "Aurélien"), (2, "Ruslan")]
    assert cases[0].revenue == Revenue(Decimal("83000"), "USD", "MRR", "$83K+ MRR")
    assert cases[1].revenue == Revenue(Decimal("167000"), "USD", "MRR", "$167K MRR")
    assert cases[1].url == "https://www.indiehackers.com/post/UZm68xNgjDZBHH7Mvc54"


def _two_cases(first_paragraphs: str) -> str:
    return (
        "<h3>案例1 · Alice：First</h3>" + first_paragraphs
        + '<p><a href="https://example.com/first">原文</a></p>'
        + '<h3>案例2 · Bob：Second</h3><p>Second body.</p><p>收入：$2K MRR</p>'
        + '<p><a href="https://example.com/second">原文</a></p>'
    )


@pytest.mark.parametrize("paragraphs", [
    "<p>这个产品的月度收入持续增长。</p><p>收入：$10K MRR</p>",
    "<p>收入：$10K MRR</p><p>这个产品的月度收入持续增长。</p>",
    "<p>这个产品的月度收入持续增长。</p><p><strong>收入：</strong>$10K MRR</p>",
])
def test_income_word_in_body_does_not_consume_or_overwrite_revenue(paragraphs: str) -> None:
    cases = parse_opc_digest(_two_cases(paragraphs))
    assert [case.index for case in cases] == [1, 2]
    assert cases[0].body == "这个产品的月度收入持续增长。"
    assert cases[0].revenue == Revenue(Decimal("10000"), "USD", "MRR", "$10K MRR")


@pytest.mark.parametrize(("old", "new"), [
    ("<p>Body.</p>", ""),
    ("<p>收入：$10K MRR</p>", ""),
    ("Alice", ""),
    ("https://example.com/first", "http://example.com/first"),
])
def test_required_fields_independently_reject_case_one(old: str, new: str) -> None:
    html = _two_cases("<p>Body.</p><p>收入：$10K MRR</p>")
    assert [case.index for case in parse_opc_digest(html)] == [1, 2]
    assert [case.index for case in parse_opc_digest(html.replace(old, new))] == [2]


@pytest.mark.parametrize(("source", "alias", "expected_amount", "expected_display"), [
    ("USD 120000 ARR", "年度营收", Decimal("10000"), "约 $10K 美元月度营收"),
    ("CNY 720000 MRR", "月度营收", Decimal("120000"), "约 $120K 美元月度营收"),
])
def test_chinese_periods_preserve_conversion_selection_and_display(
    source: str, alias: str, expected_amount: Decimal, expected_display: str,
) -> None:
    for revenue_text in (source, source.rsplit(" ", 1)[0] + " " + alias):
        cases = parse_opc_digest(_two_cases(f"<p>Body.</p><p>收入：{revenue_text}</p>"))
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
    html = """
    <h3>案例 0 · Zero：完整但越界</h3><p>正文。</p>
    <p><strong>收入：</strong>$1 MRR</p><p><a href="https://example.com/zero">阅读原文</a></p>
    <h3>案例 1 · One：完整合法</h3><p>正文。</p>
    <p><strong>收入：</strong>$1 MRR</p><p><a href="https://example.com/one">阅读原文</a></p>
    <h3>案例 3 · Three：完整但越界</h3><p>正文。</p>
    <p><strong>收入：</strong>$1 MRR</p><p><a href="https://example.com/three">阅读原文</a></p>
    """

    assert [(case.index, case.sharer) for case in parse_opc_digest(html)] == [(1, "One")]


def test_excludes_complete_case_when_duplicate_header_is_incomplete() -> None:
    html = """
    <h3>案例 1 · Missing body：重复但不完整</h3>
    <p><strong>收入：</strong>$1 MRR</p><p><a href="https://example.com/first">阅读原文</a></p>
    <h3>案例 1 · Complete duplicate：重复且完整</h3><p>正文。</p>
    <p><strong>收入：</strong>$1 MRR</p><p><a href="https://example.com/second">阅读原文</a></p>
    <h3>案例 2 · Unique：唯一完整</h3><p>正文。</p>
    <p><strong>收入：</strong>$1 MRR</p><p><a href="https://example.com/unique">阅读原文</a></p>
    """

    assert [(case.index, case.sharer) for case in parse_opc_digest(html)] == [(2, "Unique")]
