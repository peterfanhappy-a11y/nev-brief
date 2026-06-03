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
    scored.sort(key=lambda c: -c["personal_score"])
    return scored[:n]


# Per-topic quotas — keeps brief multi-dimensional instead of all sales.
# Empirically 35-candidate briefs are 60%+ sales+new_car, which makes the
# email read as "X 家车企销量公告" rather than industry/tech/market overview.
_TOPIC_QUOTAS: dict[str, int] = {
    "sales": 1,        # 销量整合：所有 sales 类只保留 importance Top 1
    "new_car": 3,      # 新车上市
    "tech": 3,         # 技术趋势（电池/智驾/OTA 等子类未来细分）
    "policy": 2,       # 政策动向
    "overseas": 2,     # 海外动态
    "supply_chain": 1,
    "recall": 1,
    "finance": 1,
    "people": 1,
}

# Bucket priority when a candidate carries multiple topics — sales first so
# articles tagged both [sales, new_car] go to sales (compressed), not new_car.
_TOPIC_PRIORITY: tuple[str, ...] = (
    "sales", "recall", "policy", "tech", "supply_chain",
    "overseas", "new_car", "finance", "people",
)

# Hard-cap buckets: backfill cannot exceed quota. User asked for diversity
# (sales 1, new_car/tech 1-3, etc.) — letting backfill pile into one topic
# defeats the purpose. Better to ship 6 diverse items than 10 same-topic ones.
# Total quota sum is 15 (1+3+3+2+2+1+1+1+1), so when data is rich we still hit 10.
_HARD_CAP_TOPICS: frozenset[str] = frozenset({
    "sales", "new_car", "tech", "policy", "overseas",
    "supply_chain", "recall", "finance", "people",
})


def _primary_bucket(candidate: dict[str, Any]) -> str:
    cand_topics = set(candidate.get("topics") or [])
    for t in _TOPIC_PRIORITY:
        if t in cand_topics:
            return t
    return "other"


def select_diverse_top_n(
    candidates: list[dict[str, Any]],
    user: UserPreferences,
    brief_date: date,
    n: int = 10,
    today: date | None = None,
) -> list[dict[str, Any]]:
    """Topic-aware Top N: enforces per-topic quotas so brief stays diverse.

    Algorithm:
    1. Score all candidates via personal_score, sort desc.
    2. First pass: bucket by primary topic; admit a candidate iff its bucket
       still has quota. Skip otherwise.
    3. Second pass (if total < n): backfill with leftover candidates by score,
       ignoring quotas.
    """
    scored = [
        {**c, "personal_score": personal_score(c, user, brief_date, today=today)}
        for c in candidates
    ]
    scored.sort(key=lambda c: -c["personal_score"])

    selected: list[dict[str, Any]] = []
    bucket_count: dict[str, int] = {}
    used_ids: set[str] = set()

    for c in scored:
        if len(selected) >= n:
            break
        bucket = _primary_bucket(c)
        quota = _TOPIC_QUOTAS.get(bucket, 1)  # unknown topics: 1 each
        if bucket_count.get(bucket, 0) >= quota:
            continue
        selected.append(c)
        bucket_count[bucket] = bucket_count.get(bucket, 0) + 1
        used_ids.add(str(c.get("cluster_id", "")))

    # Backfill if quotas left us under target. Respects hard-cap topics
    # (e.g. sales) so we don't smuggle compressed-topic items back in.
    if len(selected) < n:
        for c in scored:
            if len(selected) >= n:
                break
            cid = str(c.get("cluster_id", ""))
            if cid in used_ids:
                continue
            bucket = _primary_bucket(c)
            if bucket in _HARD_CAP_TOPICS:
                continue  # never exceed hard cap, even when short on items
            selected.append(c)
            used_ids.add(cid)

    return selected
