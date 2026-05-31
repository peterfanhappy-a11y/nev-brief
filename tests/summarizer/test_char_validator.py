"""Unit tests for nev_summarizer.char_validator."""
from __future__ import annotations

from nev_summarizer.char_validator import (
    SUMMARY_MAX,
    TITLE_MAX,
    count_chars,
    is_within_limit,
    truncate,
)


def test_count_chars_basic():
    assert count_chars("比亚迪") == 3
    assert count_chars("BYD Model 3") == 11
    assert count_chars("") == 0
    assert count_chars("   spaces   ") == 6  # stripped, len of "spaces"


def test_constants():
    assert TITLE_MAX == 25
    assert SUMMARY_MAX == 120


def test_is_within_limit():
    assert is_within_limit("短标题", TITLE_MAX) is True
    assert is_within_limit("a" * 25, TITLE_MAX) is True
    assert is_within_limit("a" * 26, TITLE_MAX) is False


def test_truncate_keeps_short():
    assert truncate("短", 25) == "短"
    assert truncate("a" * 25, 25) == "a" * 25


def test_truncate_shortens_long():
    long = "a" * 50
    result = truncate(long, 25)
    assert len(result) == 25
    assert result.endswith("…")
    assert result[:-1] == "a" * 24


def test_truncate_chinese():
    long = "比亚迪销量大涨" * 10  # 70 chars
    result = truncate(long, 25)
    assert len(result) == 25
    assert result.endswith("…")


def test_truncate_strips_whitespace():
    assert truncate("  hello  ", 25) == "hello"
