"""Single-article pipeline orchestrator."""
from __future__ import annotations

from typing import Any

from nev_pipeline.clustering import ClusterCandidate, find_or_create_cluster
from nev_pipeline.entity_extractor import extract_entities
from nev_pipeline.scoring import importance_score
from nev_pipeline.simhash import simhash
from nev_pipeline.text_cleaner import extract_clean_text


def _detect_language(text: str) -> str:
    # 朴素：中文字符占比 > 30% → zh，否则 en
    if not text:
        return "zh"
    cjk = sum(1 for c in text if "一" <= c <= "鿿")
    return "zh" if cjk / len(text) > 0.3 else "en"


async def process_article(
    raw: dict[str, Any], recent: list[ClusterCandidate]
) -> dict[str, Any]:
    raw_content = raw.get("content") or ""
    clean = extract_clean_text(raw_content)
    title = raw["title"]

    entities = await extract_entities(title, clean)
    sh = simhash(f"{title} {clean}")

    # HTML scrape sources (汽车之家, 车质网) often lack published_at.
    # Fall back to "now" so clustering + scoring don't crash.
    from datetime import datetime, timezone
    pub_at = raw.get("published_at") or datetime.now(tz=timezone.utc)

    article_candidate = ClusterCandidate(
        brands=entities.brands,
        models=entities.models,
        simhash=sh,
        published_at=pub_at,
        cluster_id=None,
    )
    cluster_id = find_or_create_cluster(article_candidate, recent)

    score = importance_score(
        authority=raw.get("source_authority", 5),
        brands=entities.brands,
        topics=entities.topics,
        published_at=pub_at,
    )

    return {
        "raw_id": str(raw["id"]),
        "source_id": str(raw["source_id"]),
        "title": title,
        "clean_text": clean,
        "simhash": sh,
        "cluster_id": cluster_id,
        "brands": entities.brands,
        "models": entities.models,
        "topics": entities.topics,
        "people": entities.people,
        "importance_score": score,
        "language": _detect_language(clean or title),
    }
