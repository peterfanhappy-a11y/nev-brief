"""Per-user candidate scoring + Top-N selection (spec §3.4)."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any


@dataclass(frozen=True)
class UserPreferences:
    brands: list[str]   # canonical brand names user follows
    topics: list[str]   # spec topic enum subset


def personal_score(
    candidate: dict[str, Any],
    user: UserPreferences,
    brief_date: date,
    today: date | None = None,
) -> float:
    """spec §3.4: 0.4*global + 0.3*brand + 0.2*topic + 0.1*freshness. Returns 0-100."""
    today = today or date.today()

    global_imp = float(candidate.get("global_importance", 0.0)) / 100.0

    cand_brands = set(candidate.get("brands") or [])
    brand_match = (
        len(cand_brands & set(user.brands)) / max(len(user.brands), 1)
        if user.brands else 0.0
    )

    cand_topics = set(candidate.get("topics") or [])
    topic_match = (
        len(cand_topics & set(user.topics)) / max(len(user.topics), 1)
        if user.topics else 0.0
    )

    freshness = 1.0 if brief_date == today else 0.5

    return 100.0 * (
        global_imp * 0.4 + brand_match * 0.3 + topic_match * 0.2 + freshness * 0.1
    )


def select_top_n(
    candidates: list[dict[str, Any]],
    user: UserPreferences,
    brief_date: date,
    n: int = 10,
    today: date | None = None,
) -> list[dict[str, Any]]:
    """Personalized Top N. Annotates each with 'personal_score'; returns ranked.

    If candidates shorter than n, returns all available (no error).
    """
    scored = [
        {**c, "personal_score": personal_score(c, user, brief_date, today=today)}
        for c in candidates
    ]
    # Python's sort is stable; preserves original order for equal scores
    scored.sort(key=lambda c: -c["personal_score"])
    return scored[:n]
