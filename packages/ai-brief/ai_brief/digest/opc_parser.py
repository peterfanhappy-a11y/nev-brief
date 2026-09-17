"""解析 OPC Daily Sharing HTML；纯函数，不触网。"""
from __future__ import annotations

import re
from collections import Counter
from decimal import Decimal
from typing import Literal, cast

from selectolax.parser import HTMLParser, Node

from ai_brief.digest.models import OpcCaseCandidate, Revenue

_HEADER_RE = re.compile(r"^案例\s*(\d+)\s*·\s*([^：]+?)\s*：\s*(.+)$")
_INCOME_LABEL_RE = re.compile(r"^收入\s*[:：]\s*")
_REVENUE_RE = re.compile(
    r"^(?P<currency>US\$|USD|美元|\$|EUR|欧元|€|GBP|英镑|£|CNY|RMB|人民币|JPY|日元|[A-Z]{3})\s*"
    r"(?P<amount>(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?)\s*"
    r"(?P<unit>[KMB])?\+?\s*(?P<period>MRR|ARR|月度营收|年度营收)$",
    re.IGNORECASE,
)
_MULTIPLIERS = {
    "": Decimal(1),
    "K": Decimal(1_000),
    "M": Decimal(1_000_000),
    "B": Decimal(1_000_000_000),
}
_CURRENCY_CODES = {
    "$": "USD", "US$": "USD", "USD": "USD", "美元": "USD",
    "€": "EUR", "EUR": "EUR", "欧元": "EUR",
    "£": "GBP", "GBP": "GBP", "英镑": "GBP",
    "CNY": "CNY", "RMB": "CNY", "人民币": "CNY",
    "JPY": "JPY", "日元": "JPY",
}


def _clean(text: str) -> str:
    return " ".join((text or "").split()).strip()


def parse_revenue(text: str) -> Revenue | None:
    raw = _clean(text)
    match = _REVENUE_RE.fullmatch(raw)
    if match is None:
        return None

    currency = match.group("currency")
    currency_code = _CURRENCY_CODES.get(currency.upper())
    if currency_code is None:
        currency_code = _CURRENCY_CODES.get(currency, currency.upper())
    unit = (match.group("unit") or "").upper()
    period = match.group("period").upper()
    period = {"月度营收": "MRR", "年度营收": "ARR"}.get(period, period)
    return Revenue(
        amount=Decimal(match.group("amount").replace(",", "")) * _MULTIPLIERS[unit],
        currency=currency_code,
        period=cast(Literal["MRR", "ARR"], period),
        raw=raw,
    )


def _element_siblings_after(node: Node) -> list[Node]:
    siblings: list[Node] = []
    sibling = node.next
    while sibling is not None and sibling.tag != "h3":
        if not sibling.tag.startswith("-"):
            siblings.append(sibling)
        sibling = sibling.next
    return siblings


def parse_opc_digest(html: str) -> list[OpcCaseCandidate]:
    headers = [
        (h3, header)
        for h3 in HTMLParser(html or "").css("h3")
        if (header := _HEADER_RE.fullmatch(_clean(h3.text()))) is not None
    ]
    header_counts = Counter(int(header.group(1)) for _, header in headers)
    candidates: list[OpcCaseCandidate] = []
    for h3, header in headers:
        index = int(header.group(1))
        if index not in {1, 2}:
            continue
        sharer, headline = header.group(2).strip(), header.group(3).strip()
        body = ""
        revenue: Revenue | None = None
        url = ""
        for sibling in _element_siblings_after(h3):
            text = _clean(sibling.text())
            if sibling.tag == "p" and _INCOME_LABEL_RE.match(text):
                income_text = _INCOME_LABEL_RE.sub("", text, count=1)
                revenue = parse_revenue(income_text)
            elif sibling.tag == "p" and not body and sibling.css_first("a") is None:
                body = text
            if not url:
                for anchor in sibling.css("a"):
                    href = (anchor.attributes.get("href") or "").strip()
                    if href.startswith("https://"):
                        url = href
                        break
        if sharer and headline and body and revenue is not None and url:
            candidates.append(OpcCaseCandidate(index, sharer, headline, body, revenue, url))

    return sorted(
        (candidate for candidate in candidates if header_counts[candidate.index] == 1),
        key=lambda candidate: candidate.index,
    )
