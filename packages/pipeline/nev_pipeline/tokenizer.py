"""Tokenizer: jieba 中文分词 + 正则提取 ASCII 词。

Used by simhash (T4) and downstream clustering (T9).
"""
from __future__ import annotations

import re

import jieba

_WORD_RE = re.compile(r"[A-Za-z0-9]+")


def tokenize(text: str) -> list[str]:
    """Tokenize mixed CN/EN text.

    - Chinese segments via jieba (drops pure ASCII tokens, whitespace).
    - ASCII alphanumeric runs extracted separately and lowercased.
    - Returns empty list for empty / whitespace-only input.
    """
    if not text or not text.strip():
        return []
    chinese = [t for t in jieba.cut(text) if t.strip() and not _WORD_RE.fullmatch(t)]
    english = [m.group(0).lower() for m in _WORD_RE.finditer(text)]
    return chinese + english
