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
    [("GBP", RATES), ("CNY", {"EUR": Decimal("1"), "USD": Decimal("1.20")}), ("CNY", {**RATES, "CNY": Decimal("0")})],
)
def test_rejects_unknown_missing_or_zero_rates(currency: str, rates: dict[str, Decimal]) -> None:
    revenue = Revenue(Decimal("100"), currency, "MRR", f"{currency} 100 MRR")

    with pytest.raises(RevenueConversionError):
        monthly_revenue_usd(revenue, rates)


def test_rejects_not_exactly_two_cases() -> None:
    with pytest.raises(RevenueConversionError):
        select_highest_case(usd_cases()[:1], Mock())


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


def test_fetches_daily_ecb_rates_from_fixture(monkeypatch: pytest.MonkeyPatch) -> None:
    response = Mock()
    response.text = ECB_FIXTURE.read_text(encoding="utf-8")
    monkeypatch.setattr("ai_brief.digest.exchange_rates.httpx.get", Mock(return_value=response))

    rates = fetch_ecb_rates()

    assert rates == {"EUR": Decimal("1"), "USD": Decimal("1.20"), "CNY": Decimal("7.20")}
    from ai_brief.digest import exchange_rates

    exchange_rates.httpx.get.assert_called_once_with(
        ECB_DAILY_RATES_URL, timeout=10.0, follow_redirects=True
    )
    response.raise_for_status.assert_called_once_with()


def test_fetch_ecb_rates_rejects_http_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    request = httpx.Request("GET", ECB_DAILY_RATES_URL)
    response = httpx.Response(500, request=request)
    failing_response = Mock()
    failing_response.raise_for_status.side_effect = httpx.HTTPStatusError(
        "500 error", request=request, response=response
    )
    monkeypatch.setattr("ai_brief.digest.exchange_rates.httpx.get", Mock(return_value=failing_response))

    with pytest.raises(RevenueConversionError):
        fetch_ecb_rates()


def test_fetch_ecb_rates_rejects_malformed_xml(monkeypatch: pytest.MonkeyPatch) -> None:
    response = Mock()
    response.text = "<broken"
    monkeypatch.setattr("ai_brief.digest.exchange_rates.httpx.get", Mock(return_value=response))

    with pytest.raises(RevenueConversionError):
        fetch_ecb_rates()
