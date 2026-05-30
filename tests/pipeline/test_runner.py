"""Unit tests for nev_pipeline.runner."""
from __future__ import annotations

from datetime import UTC, datetime

import pytest
from nev_pipeline.entity_extractor import Entities
from nev_pipeline.runner import process_article


@pytest.mark.asyncio
async def test_process_article_flow(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_extract(title: str, content: str) -> Entities:
        return Entities(brands=["BYD"], models=["秦"], topics=["new_car"])

    monkeypatch.setattr("nev_pipeline.runner.extract_entities", fake_extract)
    raw = {
        "id": "raw-1",
        "source_id": "src-1",
        "title": "比亚迪秦 PLUS 上市",
        "content": (
            "<html><body><article>比亚迪 5 月发布全新秦 PLUS 售价 8.98 万。"
            "</article></body></html>"
        ),
        "published_at": datetime.now(UTC),
        "source_authority": 8,
    }
    result = await process_article(raw, recent=[])
    assert result["raw_id"] == "raw-1"
    assert result["title"] == "比亚迪秦 PLUS 上市"
    assert result["brands"] == ["BYD"]
    assert result["models"] == ["秦"]
    assert result["topics"] == ["new_car"]
    assert result["simhash"] > 0
    assert result["cluster_id"]
    assert result["importance_score"] > 0
    assert result["language"] == "zh"
    assert "比亚迪" in result["clean_text"] or "秦" in result["clean_text"]


@pytest.mark.asyncio
async def test_process_article_default_authority(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_extract(title: str, content: str) -> Entities:
        return Entities(brands=[], topics=[])

    monkeypatch.setattr("nev_pipeline.runner.extract_entities", fake_extract)
    raw = {
        "id": "raw-2",
        "source_id": "src-2",
        "title": "test",
        "content": "test",
        "published_at": datetime.now(UTC),
    }  # no source_authority key
    result = await process_article(raw, recent=[])
    assert result["importance_score"] >= 0  # 不报错即可


@pytest.mark.asyncio
async def test_process_article_merges_into_existing_cluster(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """新文章命中已有 cluster"""

    async def fake_extract(title: str, content: str) -> Entities:
        return Entities(brands=["Tesla"], models=["Model Y"], topics=["new_car"])

    monkeypatch.setattr("nev_pipeline.runner.extract_entities", fake_extract)
    from nev_pipeline.clustering import ClusterCandidate
    from nev_pipeline.simhash import simhash

    now = datetime.now(UTC)
    # 这里 sh 要匹配 process_article 内部计算的 simhash(title + " " + clean(content))，
    # 否则 Hamming 距离会超出阈值 (9)。clean 会保留正文原样（无 HTML 包装）。
    title_for_new = "特斯拉 Model Y 6 月交付"
    content_for_new = "特斯拉 Model Y 焕新版 6 月起交付 起售 26.4 万元 全系升级"
    sh = simhash(f"{title_for_new} {content_for_new}")
    existing_cid = "550e8400-e29b-41d4-a716-446655440000"
    recent = [
        ClusterCandidate(
            brands=["Tesla"],
            models=["Model Y"],
            simhash=sh,
            published_at=now,
            cluster_id=existing_cid,
        )
    ]
    raw = {
        "id": "raw-3",
        "source_id": "src-3",
        "title": title_for_new,
        "content": content_for_new,
        "published_at": now,
        "source_authority": 9,
    }
    result = await process_article(raw, recent=recent)
    assert result["cluster_id"] == existing_cid
