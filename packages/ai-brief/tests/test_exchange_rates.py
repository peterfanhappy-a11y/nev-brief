"""Revenue normalization contracts for OPC Daily Sharing."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from unittest.mock import Mock

import httpx
import pytest
from ai_brief.digest.exchange_rates import (
    ECB_DAILY_RATES_URL,
    RevenueConversionError,
    fetch_ecb_rates,
    format_monthly_usd,
    monthly_revenue_usd,
    select_highest_case,
)
from ai_brief.digest.models import OpcCaseCandidate, Revenue

RATES = {"EUR": Decimal("1"), "USD": Decimal("1.20"), "CNY": Decimal("7.20")}
ECB_FIXTURE = Path(__file__).parent / "fixtures/ecb_daily_rates.xml"


def usd_cases() -> list[OpcCaseCandidate]:
    return [
        OpcCaseCandidate(
            index=1,
            sharer="Aurélien",
            headline="案例一主题",
            body="案例一正文",
            revenue=Revenue(Decimal("83000"), "USD", "MRR", "$83K+ MRR"),
            url="https://www.indiehackers.com/post/case-one",
        ),
        OpcCaseCandidate(
            index=2,
            sharer="Ruslan",
            headline="Zipchat 再冲到 $2M ARR",
            body="案例二正文",
            revenue=Revenue(Decimal("167000"), "USD", "MRR", "$167K MRR"),
            url="https://www.indiehackers.com/post/case-two",
        ),
    ]


def test_arr_is_converted_to_monthly_usd() -> None:
    revenue = Revenue(Decimal("1200000"), "USD", "ARR", "$1.2M ARR")

    assert monthly_revenue_usd(revenue, RATES) == Decimal("100000")


def test_cny_mrr_uses_euro_cross_rate() -> None:
    revenue = Revenue(Decimal("720000"), "CNY", "MRR", "CNY 720K MRR")

    assert monthly_revenue_usd(revenue, RATES) == Decimal("120000")


def test_selects_case_two_and_does_not_fetch_rates_for_usd() -> None:
    loader = Mock(side_effect=AssertionError("USD selection must not fetch ECB"))

    selected = select_highest_case(usd_cases(), loader)

    assert selected.candidate.index == 2
    assert selected.monthly_revenue_usd == Decimal("167000")
    assert selected.revenue_display == "$167K 美元月度营收"
    assert selected.converted is False
    loader.assert_not_called()


def test_usd_arr_is_approximate_without_fetching_ecb_rates() -> None:
    loader = Mock(side_effect=AssertionError("USD selection must not fetch ECB"))
    usd_arr_case = OpcCaseCandidate(
        index=1,
        sharer="Aurélien",
        headline="ARR 案例",
        body="案例一正文",
        revenue=Revenue(Decimal("1200000"), "USD", "ARR", "$1.2M ARR"),
        url="https://www.indiehackers.com/post/arr-case",
    )

    selected = select_highest_case([usd_arr_case, usd_cases()[0]], loader)

    assert selected.candidate.index == 1
    assert selected.revenue_display == "约 $100K 美元月度营收"
    assert selected.converted is True
    loader.assert_not_called()


def test_equal_revenue_selects_case_one() -> None:
    cases = usd_cases()
    cases[1] = OpcCaseCandidate(
        index=2,
        sharer="Ruslan",
        headline="Zipchat 再冲到 $2M ARR",
        body="案例二正文",
        revenue=Revenue(Decimal("83000"), "USD", "MRR", "$83K MRR"),
        url="https://www.indiehackers.com/post/case-two",
    )

    assert select_highest_case(cases, Mock()).candidate.index == 1


@pytest.mark.parametrize(
    ("currency", "rates"),
    [
        ("GBP", RATES),
        ("CNY", {"EUR": Decimal("1"), "USD": Decimal("1.20")}),
        ("CNY", {**RATES, "CNY": Decimal("0")}),
    ],
)
def test_rejects_unknown_missing_or_zero_rates(currency: str, rates: dict[str, Decimal]) -> None:
    revenue = Revenue(Decimal("100"), currency, "MRR", f"{currency} 100 MRR")

    with pytest.raises(RevenueConversionError):
        monthly_revenue_usd(revenue, rates)


@pytest.mark.parametrize("cases", [[], usd_cases()[:1], [*usd_cases(), usd_cases()[0]]])
def test_rejects_case_counts_other_than_two(cases: list[OpcCaseCandidate]) -> None:
    with pytest.raises(RevenueConversionError):
        select_highest_case(cases, Mock())


def test_converted_case_uses_approximate_monthly_display() -> None:
    cny_case = OpcCaseCandidate(
        index=1,
        sharer="Chen",
        headline="人民币案例",
        body="正文",
        revenue=Revenue(Decimal("720000"), "CNY", "MRR", "CNY 720K MRR"),
        url="https://www.indiehackers.com/post/cny-case",
    )
    usd_case = usd_cases()[0]

    selected = select_highest_case([cny_case, usd_case], Mock(return_value=RATES))

    assert selected.revenue_display == "约 $120K 美元月度营收"
    assert selected.converted is True


@pytest.mark.parametrize(
    ("amount", "expected"),
    [
        (Decimal("120"), "$120 美元月度营收"),
        (Decimal("999"), "$999 美元月度营收"),
        (Decimal("1000"), "$1K 美元月度营收"),
        (Decimal("1500"), "$1.5K 美元月度营收"),
        (Decimal("999999"), "$999.999K 美元月度营收"),
        (Decimal("1000000"), "$1M 美元月度营收"),
        (Decimal("2500000"), "$2.5M 美元月度营收"),
        (Decimal("999999999"), "$999.999999M 美元月度营收"),
        (Decimal("1000000000"), "$1B 美元月度营收"),
    ],
)
def test_formats_monthly_usd_by_magnitude(amount: Decimal, expected: str) -> None:
    assert format_monthly_usd(amount, approximate=False) == expected


def test_rounds_half_up_to_whole_usd() -> None:
    revenue = Revenue(Decimal("1.5"), "USD", "MRR", "$1.5 MRR")

    assert monthly_revenue_usd(revenue, RATES) == Decimal("2")


def test_non_usd_arr_uses_monthly_euro_cross_rate() -> None:
    revenue = Revenue(Decimal("720"), "CNY", "ARR", "CNY 720 ARR")

    assert monthly_revenue_usd(revenue, RATES) == Decimal("10")


def test_fetches_daily_ecb_rates_from_fixture(monkeypatch: pytest.MonkeyPatch) -> None:
    response = Mock()
    response.text = ECB_FIXTURE.read_text(encoding="utf-8")
    get = Mock(return_value=response)
    monkeypatch.setattr("ai_brief.digest.exchange_rates.httpx.get", get)

    rates = fetch_ecb_rates()

    assert rates == {"EUR": Decimal("1"), "USD": Decimal("1.20"), "CNY": Decimal("7.20")}
    get.assert_called_once_with(ECB_DAILY_RATES_URL, timeout=10.0, follow_redirects=True)
    response.raise_for_status.assert_called_once_with()


def test_fetch_ecb_rates_rejects_http_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    request = httpx.Request("GET", ECB_DAILY_RATES_URL)
    response = httpx.Response(500, request=request)
    failing_response = Mock()
    failing_response.raise_for_status.side_effect = httpx.HTTPStatusError(
        "500 error", request=request, response=response
    )
    monkeypatch.setattr(
        "ai_brief.digest.exchange_rates.httpx.get", Mock(return_value=failing_response)
    )

    with pytest.raises(RevenueConversionError):
        fetch_ecb_rates()


def test_fetch_ecb_rates_rejects_connection_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "ai_brief.digest.exchange_rates.httpx.get", Mock(side_effect=httpx.ConnectError("offline"))
    )

    with pytest.raises(RevenueConversionError):
        fetch_ecb_rates()


def test_fetch_ecb_rates_rejects_malformed_xml(monkeypatch: pytest.MonkeyPatch) -> None:
    response = Mock()
    response.text = "<broken"
    monkeypatch.setattr("ai_brief.digest.exchange_rates.httpx.get", Mock(return_value=response))

    with pytest.raises(RevenueConversionError):
        fetch_ecb_rates()


@pytest.mark.parametrize(
    "xml",
    [
        "<Cube><Cube currency='CNY' rate='7.20'/></Cube>",
        "<Cube><Cube currency='USD' rate='not-a-number'/></Cube>",
        "<Cube><Cube currency='USD' rate='-1'/></Cube>",
        "<Cube><Cube currency='USD' rate='0'/></Cube>",
        "<Cube><Cube currency='USD' rate='NaN'/></Cube>",
        "<Cube><Cube currency='USD' rate='Infinity'/></Cube>",
    ],
)
def test_fetch_ecb_rates_rejects_missing_or_invalid_usd_rate(
    monkeypatch: pytest.MonkeyPatch, xml: str
) -> None:
    response = Mock()
    response.text = xml
    monkeypatch.setattr("ai_brief.digest.exchange_rates.httpx.get", Mock(return_value=response))

    with pytest.raises(RevenueConversionError):
        fetch_ecb_rates()
