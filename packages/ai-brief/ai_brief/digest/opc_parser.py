"""解析 OPC Daily Sharing HTML；纯函数，不触网。"""
from __future__ import annotations

import re
from collections import Counter
from decimal import Decimal

from selectolax.parser import HTMLParser, Node

from ai_brief.digest.models import OpcCaseCandidate, Revenue

_HEADER_RE = re.compile(r"^案例\s*(\d+)\s*·\s*([^：]+?)\s*：\s*(.+)$")
_REVENUE_RE = re.compile(
    r"^(?P<currency>US\$|USD|\$)\s*(?P<amount>\d+(?:\.\d+)?)\s*"
    r"(?P<unit>[KMB])?\+?\s*(?P<period>MRR|ARR)$",
    re.IGNORECASE,
)
_MULTIPLIERS = {"": Decimal(1), "K": Decimal(1_000), "M": Decimal(1_000_000), "B": Decimal(1_000_000_000)}


def _clean(text: str) -> str:
    return " ".join((text or "").split()).strip()


def parse_revenue(text: str) -> Revenue | None:
    raw = _clean(text)
    match = _REVENUE_RE.fullmatch(raw)
    if match is None:
        return None

    currency = match.group("currency").upper()
    currency_code = "USD" if currency in {"$", "US$", "USD"} else ""
    if not currency_code:
        return None
    unit = (match.group("unit") or "").upper()
    period = match.group("period").upper()
    return Revenue(
        amount=Decimal(match.group("amount")) * _MULTIPLIERS[unit],
        currency=currency_code,
        period=period,  # type: ignore[arg-type]
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
    candidates: list[OpcCaseCandidate] = []
    for h3 in HTMLParser(html or "").css("h3"):
        header = _HEADER_RE.fullmatch(_clean(h3.text()))
        if header is None:
            continue
        index, sharer, headline = int(header.group(1)), header.group(2).strip(), header.group(3).strip()
        body = ""
        revenue: Revenue | None = None
        url = ""
        for sibling in _element_siblings_after(h3):
            text = _clean(sibling.text())
            if sibling.tag == "p" and "收入" in text:
                income_text = re.sub(r"^.*?收入\s*[:：]\s*", "", text)
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

    counts = Counter(candidate.index for candidate in candidates)
    return sorted(
        (candidate for candidate in candidates if counts[candidate.index] == 1),
        key=lambda candidate: candidate.index,
    )
