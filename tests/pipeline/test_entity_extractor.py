"""Tests for nev_pipeline.entity_extractor (T8)."""
import pytest

from nev_pipeline.entity_extractor import extract_entities


@pytest.mark.asyncio
async def test_extract_uses_deepseek_result(monkeypatch):
    async def fake(system, user, **kw):
        return {
            "brands": ["BYD"],
            "models": ["秦 PLUS"],
            "topics": ["new_car"],
            "people": ["王传福"],
            "is_significant": True,
            "significance_reason": "",
        }

    monkeypatch.setattr("nev_pipeline.entity_extractor.extract_json_with_retry", fake)
    r = await extract_entities("title", "content")
    assert r.brands == ["BYD"]
    assert r.models == ["秦 PLUS"]
    assert r.topics == ["new_car"]
    assert r.is_significant is True
    assert r.used_fallback is False


@pytest.mark.asyncio
async def test_extract_falls_back_to_dict_when_deepseek_fails(monkeypatch):
    async def fake(*a, **kw):
        return None  # DeepSeek failed

    monkeypatch.setattr("nev_pipeline.entity_extractor.extract_json_with_retry", fake)
    r = await extract_entities("比亚迪秦 PLUS 上市", "对标特斯拉 Model Y")
    # Fallback hits entity_dict find_brands_in_text
    assert "BYD" in r.brands
    assert "Tesla" in r.brands
    # No topic detected by dict fallback
    assert r.topics == []
    assert r.is_significant is True  # Default true when fallback used
    assert r.used_fallback is True


@pytest.mark.asyncio
async def test_extract_empty_when_no_signal(monkeypatch):
    async def fake(*a, **kw):
        return None

    monkeypatch.setattr("nev_pipeline.entity_extractor.extract_json_with_retry", fake)
    r = await extract_entities("random title", "random content no brands")
    assert r.brands == []
    assert r.models == []
