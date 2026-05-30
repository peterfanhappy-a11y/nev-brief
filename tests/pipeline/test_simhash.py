"""Tests for nev_pipeline.simhash (60-bit SimHash per spec §5.2.5)."""
from nev_pipeline.simhash import are_similar, hamming_distance, simhash


def test_simhash_returns_60bit():
    h = simhash("特斯拉 Model Y 焕新版 6 月交付")
    assert 0 <= h < (1 << 60)


def test_simhash_stable():
    text = "比亚迪 5 月销量同比增长 30%"
    assert simhash(text) == simhash(text)


def test_hamming_distance_identical():
    h = simhash("test content")
    assert hamming_distance(h, h) == 0


def test_similar_texts_close():
    h1 = simhash("特斯拉 Model Y 6 月交付，起售 26.4 万元")
    h2 = simhash("特斯拉 Model Y 焕新版 6 月起交付 起售 26.4 万")
    assert hamming_distance(h1, h2) <= 9


def test_different_texts_far():
    h1 = simhash("比亚迪销量大涨")
    h2 = simhash("Apple 发布 iPhone 16")
    assert hamming_distance(h1, h2) > 20


def test_are_similar():
    h = simhash("test")
    assert are_similar(h, h, threshold=9)
