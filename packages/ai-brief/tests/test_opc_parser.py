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
    ["¥100K MRR", "$100K", "100K MRR", "$many MRR"],
)
def test_rejects_ambiguous_or_incomplete_revenue(revenue_text: str) -> None:
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
