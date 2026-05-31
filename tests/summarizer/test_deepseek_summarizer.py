"""T5 tests — mock extract_json_with_retry to control DeepSeek behavior."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from nev_summarizer.cluster_aggregator import Cluster, ClusterArticle
from nev_summarizer.deepseek_summarizer import (
    SUMMARY_MAX,
    TITLE_MAX,
    summarize_cluster,
)


def _cluster(n_articles=2):
    now = datetime.now(timezone.utc)
    arts = [
        ClusterArticle(
            raw_id=f"r{i}", title=f"t{i}", clean_text=f"c{i}",
            url=f"https://x/{i}", source_id=f"s{i}", source_name=f"src{i}",
            source_authority=8, published_at=now, importance_score=50.0,
        )
        for i in range(n_articles)
    ]
    return Cluster(
        cluster_id="cl1", articles=arts, brands=[], models=[], topics=[],
        earliest_published=now,
    )


@pytest.mark.asyncio
async def test_first_attempt_within_limits(monkeypatch):
    async def fake(system, user, **kw):
        return {
            "title": "比亚迪海豹06上市",
            "summary": "5月30日发布，售价8.98万起。" * 3,  # ~36 chars
            "key_data": {"type": "price", "values": {"start_price": 89800}},
            "brands": ["BYD"], "topics": ["new_car"],
            "primary_source": "36氪", "source_count": 2,
        }
    monkeypatch.setattr("nev_summarizer.deepseek_summarizer.extract_json_with_retry", fake)
    r = await summarize_cluster(_cluster())
    assert r is not None
    assert r.retry_count == 0
    assert r.used_truncation is False
    assert len(r.title) <= TITLE_MAX
    assert len(r.summary) <= SUMMARY_MAX
    assert r.brands == ["BYD"]


@pytest.mark.asyncio
async def test_retry_succeeds_when_first_overruns(monkeypatch):
    calls = []
    async def fake(system, user, **kw):
        calls.append(user)
        if len(calls) == 1:
            return {
                "title": "比" * 30,  # over 25
                "summary": "正常摘要内容。",
                "key_data": {},
                "brands": ["BYD"], "topics": [],
                "primary_source": "src", "source_count": 2,
            }
        return {
            "title": "比亚迪短标题",
            "summary": "正常摘要内容。",
            "key_data": {},
            "brands": ["BYD"], "topics": [],
            "primary_source": "src", "source_count": 2,
        }
    monkeypatch.setattr("nev_summarizer.deepseek_summarizer.extract_json_with_retry", fake)
    r = await summarize_cluster(_cluster())
    assert r is not None
    assert r.retry_count == 1
    assert r.used_truncation is False
    assert len(r.title) <= TITLE_MAX
    assert "比亚迪短标题" in r.title


@pytest.mark.asyncio
async def test_algorithmic_truncate_when_retry_also_overruns(monkeypatch):
    async def fake(system, user, **kw):
        # Both attempts return over-limit
        return {
            "title": "比" * 50,
            "summary": "字" * 200,
            "key_data": {},
            "brands": [], "topics": [],
            "primary_source": "src", "source_count": 1,
        }
    monkeypatch.setattr("nev_summarizer.deepseek_summarizer.extract_json_with_retry", fake)
    r = await summarize_cluster(_cluster())
    assert r is not None
    assert r.retry_count == 1
    assert r.used_truncation is True
    assert len(r.title) == TITLE_MAX
    assert r.title.endswith("…")
    assert len(r.summary) == SUMMARY_MAX
    assert r.summary.endswith("…")


@pytest.mark.asyncio
async def test_returns_none_when_deepseek_fails(monkeypatch):
    async def fake(*a, **kw):
        return None
    monkeypatch.setattr("nev_summarizer.deepseek_summarizer.extract_json_with_retry", fake)
    r = await summarize_cluster(_cluster())
    assert r is None


@pytest.mark.asyncio
async def test_user_prompt_orders_by_authority(monkeypatch):
    captured = {}
    async def fake(system, user, **kw):
        captured["user"] = user
        return {
            "title": "OK", "summary": "OK", "key_data": {},
            "brands": [], "topics": [],
            "primary_source": "high", "source_count": 2,
        }
    monkeypatch.setattr("nev_summarizer.deepseek_summarizer.extract_json_with_retry", fake)

    now = datetime.now(timezone.utc)
    cluster = Cluster(
        cluster_id="cl1",
        articles=[
            ClusterArticle(raw_id="r1", title="low_auth_title", clean_text="x",
                           url="u", source_id="s1", source_name="low",
                           source_authority=3, published_at=now, importance_score=0.0),
            ClusterArticle(raw_id="r2", title="high_auth_title", clean_text="x",
                           url="u", source_id="s2", source_name="high",
                           source_authority=10, published_at=now, importance_score=0.0),
        ],
        brands=[], models=[], topics=[], earliest_published=now,
    )
    await summarize_cluster(cluster)
    # High authority article should come BEFORE low one in the prompt
    user = captured["user"]
    assert user.index("high_auth_title") < user.index("low_auth_title")
