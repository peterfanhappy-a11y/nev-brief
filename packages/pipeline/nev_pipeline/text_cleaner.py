"""HTML → clean text extraction for pipeline (T5).

Used by runner before SimHash / entity extraction. Drops boilerplate (nav,
footer, aside, script, style) and truncates to a max char budget so downstream
prompts stay bounded.
"""
from __future__ import annotations

from readability import Document
from selectolax.parser import HTMLParser

_DROP_TAGS = ("script", "style", "nav", "footer", "aside")


def extract_clean_text(html: str, max_chars: int = 1500) -> str:
    """Extract main article text from raw HTML.

    Args:
        html: Raw HTML string.
        max_chars: Truncate output to this many characters (default 1500).

    Returns:
        Clean plain text, or empty string if input is empty/blank/no body.
    """
    if not html or not html.strip():
        return ""
    try:
        main_html = Document(html).summary()
    except Exception:  # noqa: BLE001 — readability may raise on malformed input
        main_html = html
    tree = HTMLParser(main_html)
    for tag in _DROP_TAGS:
        for node in tree.css(tag):
            node.decompose()
    text = tree.body.text(separator=" ", strip=True) if tree.body else ""
    return text[:max_chars]
