"""Tests for nev_pipeline.entity_dict (T6)."""
from nev_pipeline.entity_dict import (
    canonicalize_brand,
    find_brands_in_text,
    load_entity_dict,
)


def test_load_dict_has_brands():
    d = load_entity_dict()
    assert len(d.brands_by_canonical) >= 30
    assert "BYD" in d.brands_by_canonical
    assert "Tesla" in d.brands_by_canonical


def test_load_dict_has_topics():
    d = load_entity_dict()
    assert "new_car" in d.topics
    assert "sales" in d.topics


def test_alias_to_canonical():
    d = load_entity_dict()
    assert d.alias_to_canonical.get("比亚迪") == "BYD"
    assert d.alias_to_canonical.get("特斯拉") == "Tesla"


def test_canonicalize_alias():
    assert canonicalize_brand("比亚迪") == "BYD"
    assert canonicalize_brand("BYD") == "BYD"
    assert canonicalize_brand("不存在的品牌") is None


def test_canonicalize_case_insensitive():
    # Aliases may be stored as "BYD" / "Tesla"; user input could be "byd" / "tesla"
    assert canonicalize_brand("byd") == "BYD"
    assert canonicalize_brand("tesla") == "Tesla"


def test_find_brands_in_text():
    text = "比亚迪秦 PLUS 与特斯拉 Model Y 竞争"
    brands = find_brands_in_text(text)
    assert "BYD" in brands
    assert "Tesla" in brands


def test_find_brands_empty():
    assert find_brands_in_text("") == []
    assert find_brands_in_text("Random text with no brands") == []


def test_hot_brands_set():
    d = load_entity_dict()
    assert "BYD" in d.hot_brands
    assert "Tesla" in d.hot_brands
    # Roughly 7 hot brands per spec
    assert 5 <= len(d.hot_brands) <= 10
