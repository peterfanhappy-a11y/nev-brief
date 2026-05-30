"""Tests for nev_pipeline.text_cleaner (T5)."""
from pathlib import Path

from nev_pipeline.text_cleaner import extract_clean_text

FIXTURES = Path(__file__).parent / "fixtures"


def test_extract_synthetic_keeps_body():
    html = (FIXTURES / "article_synthetic.html").read_text(encoding="utf-8")
    text = extract_clean_text(html)
    assert len(text) > 50
    assert "比亚迪" in text or "海豹" in text
    assert "8.98" in text  # 关键数据保留
    assert "<script>" not in text
    assert "<style>" not in text


def test_extract_empty_returns_empty():
    assert extract_clean_text("") == ""
    assert extract_clean_text("   ") == ""
    assert extract_clean_text("<html></html>") == ""


def test_extract_drops_script_style():
    html = (
        "<html><body><article>Real content here that is long enough to be "
        "picked up by readability lxml as main content.</article>"
        "<script>track();</script><style>.x{}</style></body></html>"
    )
    text = extract_clean_text(html)
    assert "Real content" in text
    assert "track()" not in text
    assert ".x" not in text


def test_extract_truncates_to_max_chars():
    long_html = "<html><body><article>" + "字" * 3000 + "</article></body></html>"
    text = extract_clean_text(long_html, max_chars=1500)
    assert len(text) <= 1500
