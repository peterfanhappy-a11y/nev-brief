"""Character-count validation for summary outputs.

Used by deepseek_summarizer (T5) to enforce title/summary length limits
per the brief schema.
"""
from __future__ import annotations

TITLE_MAX = 25
# User feedback 2026-06-05: 摘要字数 +10% (120 → 132) for more detail
SUMMARY_MAX = 132


def count_chars(text: str) -> int:
    return len(text.strip())


def is_within_limit(text: str, limit: int) -> bool:
    return count_chars(text) <= limit


def truncate(text: str, limit: int) -> str:
    """超长 → 截到 limit-1 + '…'。已合法则原样返回。"""
    text = text.strip()
    if len(text) <= limit:
        return text
    return text[: limit - 1] + "…"
