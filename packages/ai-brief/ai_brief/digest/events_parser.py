"""解析 ai-events-digest HTML → 3 条 EventItem。纯函数，不触网。

当前上游结构（2026-07 起）：每条新闻一个彩色 <div>，内含
  <h3> 分类·价值标签（带 emoji 前缀）
  <h4> 新闻标题
  <p>  长正文
  <a>  → 阅读原文 (来源名)      ← url + 括号里的来源
  <span>🖼️ 头图说明 ✅</span>
定位：以每个 <h4> 为锚，取其所在 item <div>。文档顺序 = 序号 = 附件前缀 01/02/03。
"""
from __future__ import annotations

import re

from selectolax.parser import HTMLParser, Node

from ai_brief.digest.models import EventItem

_SOURCE_RE = re.compile(r"[（(]([^）)]+)[）)]")
_URL_TEXT_NOISE = ("阅读原文", "→", "原文")


def _clean(text: str) -> str:
    return " ".join((text or "").split()).strip()


def _item_div(node: Node) -> Node | None:
    """向上找到最近的 div（一条新闻块）。"""
    cur = node.parent
    while cur is not None and cur.tag != "div":
        cur = cur.parent
    return cur


def _read_link(block: Node) -> tuple[str, str]:
    """返回 (url, source_name)。取 text 含「阅读原文」的 <a>；来源取括号内文字。"""
    for a in block.css("a"):
        txt = a.text() or ""
        href = (a.attributes.get("href") or "").strip()
        if href.startswith("http") and any(k in txt for k in _URL_TEXT_NOISE):
            m = _SOURCE_RE.search(txt)
            return href, (m.group(1).strip() if m else "")
    # 兜底：块内第一个 http 链接
    for a in block.css("a"):
        href = (a.attributes.get("href") or "").strip()
        if href.startswith("http"):
            m = _SOURCE_RE.search(a.text() or "")
            return href, (m.group(1).strip() if m else "")
    return "", ""


def _split_label(h3_text: str) -> tuple[str, str]:
    """「📦 海外大模型公司·最有价值」→ (category, value_tag)。去 emoji 前缀，按·拆。"""
    t = _clean(h3_text)
    # 去掉开头的 emoji/符号（保留首个 CJK 或字母起）
    t = re.sub(r"^[^一-鿿A-Za-z]+", "", t).strip()
    if "·" in t:
        cat, _, val = t.partition("·")
        return cat.strip(), val.strip()
    return t, ""


def parse_events_digest(html: str) -> list[EventItem]:
    tree = HTMLParser(html)
    items: list[EventItem] = []
    for idx, h4 in enumerate(tree.css("h4"), start=1):
        block = _item_div(h4)
        if block is None:
            continue

        headline = _clean(h4.text())
        url, source = _read_link(block)
        if not headline or not url:
            continue

        h3 = block.css_first("h3")
        category, value_tag = _split_label(h3.text() if h3 else "")
        if source and not value_tag:  # 来源名可补进展示（可选）
            value_tag = value_tag

        body = ""
        image_note = ""
        for node in block.css("p, span"):
            txt = (node.text() or "").strip()
            if txt.startswith("🖼️"):
                image_note = txt.lstrip("🖼️").strip("：: ").strip()
            elif txt.startswith("📌"):
                continue  # 编辑备注，跳过
            elif not body and len(txt) >= 20:
                body = _clean(txt)

        items.append(
            EventItem(
                index=idx,
                category=category,
                value_tag=value_tag,
                headline=headline,
                url=url,
                body=body,
                image_note=image_note,
            )
        )
    return items
