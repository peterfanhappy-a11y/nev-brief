"""OPC daily-sharing HTML parser contract tests."""
from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest
from ai_brief.digest.models import Revenue
from ai_brief.digest.opc_parser import parse_opc_digest, parse_revenue

FIXTURE = Path(__file__).parent / "fixtures/opc_sharing_2026-09-14.html"


def test_parses_two_real_opc_cases() -> None:
    cases = parse_opc_digest(FIXTURE.read_text(encoding="utf-8"))

    assert [(case.index, case.sharer) for case in cases] == [(1, "Aurélien"), (2, "Ruslan")]
    assert cases[0].revenue == Revenue(Decimal("83000"), "USD", "MRR", "$83K+ MRR")
    assert cases[1].revenue == Revenue(Decimal("167000"), "USD", "MRR", "$167K MRR")
    assert cases[1].url == "https://www.indiehackers.com/post/UZm68xNgjDZBHH7Mvc54"


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


def test_excludes_candidates_missing_required_structure_or_with_duplicate_index() -> None:
    html = """
    <h3>案例 1 · Valid：有效案例</h3>
    <p>完整正文。</p>
    <p><strong>收入：</strong>$1.5M ARR</p>
    <p><a href="https://example.com/valid">阅读原文</a></p>

    <h3>案例 2 · ：缺少分享人</h3>
    <p>正文。</p><p><strong>收入：</strong>$10K MRR</p>
    <p><a href="https://example.com/no-sharer">阅读原文</a></p>

    <h3>案例 3 · No body：缺少正文</h3>
    <p><strong>收入：</strong>$10K MRR</p>
    <p><a href="https://example.com/no-body">阅读原文</a></p>

    <h3>案例 4 · No revenue：缺少收入</h3>
    <p>正文。</p><p><a href="https://example.com/no-revenue">阅读原文</a></p>

    <h3>案例 5 · HTTP only：非 HTTPS 链接</h3>
    <p>正文。</p><p><strong>收入：</strong>$10K MRR</p>
    <p><a href="http://example.com/http">阅读原文</a></p>

    <h3>案例 6 · First duplicate：重复序号</h3>
    <p>正文。</p><p><strong>收入：</strong>$10K MRR</p>
    <p><a href="https://example.com/duplicate-a">阅读原文</a></p>
    <h3>案例 6 · Second duplicate：重复序号</h3>
    <p>正文。</p><p><strong>收入：</strong>$10K MRR</p>
    <p><a href="https://example.com/duplicate-b">阅读原文</a></p>
    """

    cases = parse_opc_digest(html)

    assert [(case.index, case.sharer) for case in cases] == [(1, "Valid")]
    assert cases[0].revenue == Revenue(Decimal("1500000"), "USD", "ARR", "$1.5M ARR")


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
