"""文章页解析 — 从 HTML 提取正文 + og:image。

正文启发式：优先 <article>；否则取 <p> 密度最高的容器（近似最大文本块）；
再兜底 meta description。og:image 取 og:image → twitter:image，仅收 https 绝对 URL。
纯函数（输入 HTML 字符串），便于 fixture 测试，不触网。
"""
from __future__ import annotations

from selectolax.parser import HTMLParser

from ai_brief.config import ARTICLE_CONTENT_MAX_CHARS

_BLOCK_TAGS_TO_DROP = ("script", "style", "nav", "header", "footer", "aside", "form")


def extract_og_image(html: str) -> str | None:
    tree = HTMLParser(html)
    for sel, attr in (
        ('meta[property="og:image"]', "content"),
        ('meta[name="twitter:image"]', "content"),
        ('meta[name="twitter:image:src"]', "content"),
    ):
        node = tree.css_first(sel)
        if node:
            val = (node.attributes.get(attr) or "").strip()
            if val.startswith("https://"):
                return val
    return None


def extract_title(html: str) -> str | None:
    tree = HTMLParser(html)
    og = tree.css_first('meta[property="og:title"]')
    if og:
        val = (og.attributes.get("content") or "").strip()
        if val:
            return val
    if tree.css_first("h1"):
        txt = tree.css_first("h1").text(strip=True)
        if txt:
            return txt
    if tree.css_first("title"):
        return tree.css_first("title").text(strip=True) or None
    return None


def _text_of(node) -> str:  # noqa: ANN001
    for tag in _BLOCK_TAGS_TO_DROP:
        for n in node.css(tag):
            n.decompose()
    return node.text(separator="\n", strip=True)


def extract_content(html: str, max_chars: int = ARTICLE_CONTENT_MAX_CHARS) -> str | None:
    """提取正文。<article> 优先 → <p> 最密容器 → meta description。截断到 max_chars。"""
    tree = HTMLParser(html)

    article = tree.css_first("article")
    if article:
        text = _text_of(article)
        if len(text) >= 200:
            return text[:max_chars]

    # 找 <p> 数量最多的容器（近似正文区）
    best_text = ""
    best_p = 0
    seen: set[int] = set()
    for p in tree.css("p"):
        parent = p.parent
        if parent is None:
            continue
        pid = id(parent)
        if pid in seen:
            continue
        seen.add(pid)
        p_count = len(parent.css("p"))
        if p_count > best_p:
            text = _text_of(parent)
            if len(text) > len(best_text):
                best_text = text
                best_p = p_count
    if len(best_text) >= 200:
        return best_text[:max_chars]

    desc = tree.css_first('meta[name="description"]') or tree.css_first(
        'meta[property="og:description"]'
    )
    if desc:
        val = (desc.attributes.get("content") or "").strip()
        if val:
            return val[:max_chars]

    # 最后兜底：整页文本（若非空）
    body_text = _text_of(tree.body) if tree.body else ""
    return body_text[:max_chars] if len(body_text) >= 100 else None


def parse_article(html: str, *, fallback_title: str | None = None) -> dict:
    """一次性解析文章页，返回 {title, content, og_image}。"""
    return {
        "title": extract_title(html) or fallback_title,
        "content": extract_content(html),
        "og_image": extract_og_image(html),
    }
