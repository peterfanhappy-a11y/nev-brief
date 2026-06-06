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


# Per-topic quotas — keeps brief multi-dimensional. User feedback 2026-06-04:
# also wants visibility into battery / autonomous_driving / smart_cockpit /
# chassis / exterior / OTA sub-topics. Total quota sum (≈25) > target n=10
# so rich data fills naturally; thin data shrinks brief honestly.
_TOPIC_QUOTAS: dict[str, int] = {
    # 综合
    "sales": 1,                # 销量整合（hard cap 1）
    "new_car": 3,              # 新车上市
    "policy": 2,
    "overseas": 2,
    "supply_chain": 1,
    "recall": 1,
    "finance": 1,
    "people": 1,
    # 技术细分（用户诉求）
    "battery_tech": 2,         # 电池
    "smart_cockpit": 2,        # 智能座舱
    "autonomous_driving": 2,   # 智能驾驶
    "chassis": 1,              # 底盘
    "exterior_design": 1,      # 外观/风阻
    "ota_update": 1,           # OTA
    "tech": 2,                 # 兜底通用技术（降权，避免泛 tech 占位）
}

# Bucket priority when a candidate carries multiple topics.细分 > 粗粒度 > sales。
# Articles tagged [tech, autonomous_driving] go to autonomous_driving bucket
# (specific), not tech (generic). [sales, new_car] still compressed to sales.
_TOPIC_PRIORITY: tuple[str, ...] = (
    # 细分技术优先（避免被 tech/new_car 吸收）
    "battery_tech", "autonomous_driving", "smart_cockpit",
    "ota_update", "chassis", "exterior_design",
    # 然后销量压缩
    "sales", "recall", "policy",
    # 然后其他
    "supply_chain", "overseas", "new_car", "finance", "people",
    # 兜底 tech 最后
    "tech",
)

# Hard-cap buckets: backfill cannot exceed quota. User asked for diversity
# (sales 1, new_car/tech 1-3, etc.) — letting backfill pile into one topic
# defeats the purpose. Better to ship 6 diverse items than 10 same-topic ones.
_HARD_CAP_TOPICS: frozenset[str] = frozenset({
    "sales", "new_car", "tech", "policy", "overseas",
    "supply_chain", "recall", "finance", "people",
    "battery_tech", "smart_cockpit", "autonomous_driving",
    "chassis", "exterior_design", "ota_update",
})

# Brand cap: user feedback 2026-06-05 — 比亚迪/特斯拉 6 条占 Top 10 太多。
# Each brand may appear in at most 2 of the selected 10 items. Applied to
# every brand in candidate.brands (a cluster mentioning [BYD, Li Auto] counts
# against both quotas).
_BRAND_CAP_PER_BRIEF = 2


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
    brand_count: dict[str, int] = {}
    used_ids: set[str] = set()

    def _brand_cap_violated(cand: dict[str, Any]) -> bool:
        """Any brand in the candidate already at the per-brief cap."""
        for b in (cand.get("brands") or []):
            if brand_count.get(b, 0) >= _BRAND_CAP_PER_BRIEF:
                return True
        return False

    def _admit(cand: dict[str, Any], bucket: str) -> None:
        selected.append(cand)
        bucket_count[bucket] = bucket_count.get(bucket, 0) + 1
        for b in (cand.get("brands") or []):
            brand_count[b] = brand_count.get(b, 0) + 1
        used_ids.add(str(cand.get("cluster_id", "")))

    for c in scored:
        if len(selected) >= n:
            break
        if _brand_cap_violated(c):
            continue
        bucket = _primary_bucket(c)
        quota = _TOPIC_QUOTAS.get(bucket, 1)
        if bucket_count.get(bucket, 0) >= quota:
            continue
        _admit(c, bucket)

    # Backfill respects both hard-cap topics AND brand caps.
    if len(selected) < n:
        for c in scored:
            if len(selected) >= n:
                break
            cid = str(c.get("cluster_id", ""))
            if cid in used_ids:
                continue
            if _brand_cap_violated(c):
                continue
            bucket = _primary_bucket(c)
            if bucket in _HARD_CAP_TOPICS:
                continue
            _admit(c, bucket)

    return selected
