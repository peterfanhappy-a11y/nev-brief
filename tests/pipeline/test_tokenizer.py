"""Tests for nev_pipeline.tokenizer."""
from nev_pipeline.tokenizer import tokenize


def test_tokenize_chinese():
    tokens = tokenize("比亚迪秦 PLUS 新车上市")
    assert "比亚迪" in tokens or "秦" in tokens
    assert "PLUS" in tokens or "plus" in tokens


def test_tokenize_english():
    tokens = tokenize("Tesla Model Y price drop 5%")
    assert "tesla" in tokens
    assert "model" in tokens


def test_tokenize_empty():
    assert tokenize("") == []
    assert tokenize("   ") == []
