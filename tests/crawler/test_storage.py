"""Unit tests for nev_crawler.storage — pure function behavior, no DB."""
from __future__ import annotations

from nev_crawler.storage import hash_content


def test_hash_content_basic() -> None:
    h = hash_content("hello world")
    assert isinstance(h, str)
    assert len(h) == 16  # blake2b 8-byte digest = 16 hex chars


def test_hash_content_stable() -> None:
    assert hash_content("same") == hash_content("same")


def test_hash_content_different_inputs_differ() -> None:
    assert hash_content("a") != hash_content("b")


def test_hash_content_empty_uses_fallback() -> None:
    """空 content + fallback → hash(fallback)，绝不返回 None。"""
    h = hash_content("", fallback="title text")
    assert h is not None
    assert len(h) == 16
    assert h == hash_content("title text")  # 与直接 hash fallback 一致


def test_hash_content_whitespace_uses_fallback() -> None:
    """纯空白 content 也走 fallback（strip 后判断）。"""
    h = hash_content("   \n  ", fallback="title text")
    assert h == hash_content("title text")


def test_hash_content_none_uses_fallback() -> None:
    h = hash_content(None, fallback="title")
    assert h == hash_content("title")


def test_hash_content_all_empty_returns_marker_hash() -> None:
    """text + fallback 都空 → 不抛错，hash 一个 sentinel。绝不 None。"""
    h = hash_content("", fallback="")
    assert isinstance(h, str)
    assert len(h) == 16
    assert h == hash_content(None, fallback=None or "")


def test_hash_content_prefers_text_over_fallback() -> None:
    """非空 content 不走 fallback。"""
    assert hash_content("real content", fallback="ignored") == hash_content("real content")
