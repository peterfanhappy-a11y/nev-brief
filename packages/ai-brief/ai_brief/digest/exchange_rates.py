"""Normalize OPC case revenue into comparable monthly USD amounts."""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from typing import Callable, Mapping, Sequence
from xml.etree import ElementTree

import httpx

from ai_brief.digest.models import OpcCaseCandidate, Revenue

ECB_DAILY_RATES_URL = "https://www.ecb.europa.eu/stats/eurofxref/eurofxref-daily.xml"


class RevenueConversionError(ValueError):
    """A revenue amount cannot be safely converted to USD."""


@dataclass(frozen=True)
class SelectedOpcCase:
    candidate: OpcCaseCandidate
    monthly_revenue_usd: Decimal
    revenue_display: str
    converted: bool


def fetch_ecb_rates() -> dict[str, Decimal]:
    try:
        response = httpx.get(ECB_DAILY_RATES_URL, timeout=10.0, follow_redirects=True)
        response.raise_for_status()
        root = ElementTree.fromstring(response.text)
    except (httpx.HTTPError, ElementTree.ParseError) as error:
        raise RevenueConversionError("could not fetch ECB rates") from error

    rates = {"EUR": Decimal("1")}
    try:
        for cube in root.iter():
            currency = cube.attrib.get("currency")
            raw_rate = cube.attrib.get("rate")
            if currency is None or raw_rate is None:
                continue
            rate = Decimal(raw_rate)
            if not rate.is_finite() or rate <= 0:
                raise RevenueConversionError(f"invalid ECB rate for {currency}")
            rates[currency] = rate
    except (ValueError, ArithmeticError) as error:
        raise RevenueConversionError("invalid ECB rate") from error
    if "USD" not in rates:
        raise RevenueConversionError("missing ECB rate for USD")
    return rates


def _positive_rate(rates: Mapping[str, Decimal], currency: str) -> Decimal:
    try:
        rate = rates[currency]
    except KeyError as error:
        raise RevenueConversionError(f"missing ECB rate for {currency}") from error
    if not rate.is_finite() or rate <= 0:
        raise RevenueConversionError(f"invalid ECB rate for {currency}")
    return rate


def monthly_revenue_usd(revenue: Revenue, rates: Mapping[str, Decimal]) -> Decimal:
    period_amount = revenue.amount / Decimal(12) if revenue.period == "ARR" else revenue.amount
    if revenue.currency == "USD":
        usd_amount = period_amount
    else:
        _positive_rate(rates, "EUR")
        usd_amount = period_amount / _positive_rate(rates, revenue.currency) * _positive_rate(rates, "USD")
    return usd_amount.quantize(Decimal("1"), rounding=ROUND_HALF_UP)


def format_monthly_usd(amount: Decimal, *, approximate: bool) -> str:
    thousands = amount / Decimal(1000)
    compact = format(thousands.normalize(), "f")
    if "." in compact:
        compact = compact.rstrip("0").rstrip(".")
    prefix = "约 " if approximate else ""
    return f"{prefix}${compact}K 美元月度营收"


def select_highest_case(
    cases: Sequence[OpcCaseCandidate], rates_loader: Callable[[], Mapping[str, Decimal]]
) -> SelectedOpcCase:
    if len(cases) != 2:
        raise RevenueConversionError("exactly two OPC cases are required")

    rates: Mapping[str, Decimal] = {}
    if any(case.revenue.currency != "USD" for case in cases):
        rates = rates_loader()
    converted_cases = [(case, monthly_revenue_usd(case.revenue, rates)) for case in cases]
    candidate, monthly_amount = max(converted_cases, key=lambda item: (item[1], -item[0].index))
    converted = candidate.revenue.currency != "USD"
    return SelectedOpcCase(
        candidate=candidate,
        monthly_revenue_usd=monthly_amount,
        revenue_display=format_monthly_usd(monthly_amount, approximate=converted),
        converted=converted,
    )
