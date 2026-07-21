"""解析 ai-events-digest HTML → EventItem 列表（今日AI 模块）。纯函数，不触网。

上游结构（2026-07-21 起改版）：每条一个 <div class="item">：
  <div class="label">海外大模型公司·最有价值</div>   分类·价值
  <div class="title">1. 标题…</div>                 序号 + 标题
  <div class="summary">长正文…</div>
  <div class="meta">来源: X | <a href="…">阅读原文</a></div>
序号 = 附件前缀（01_/02_/03_…）。上游一次给多条（如 8 条），下游取 TOP-N。
"""
from __future__ import annotations

import re

from selectolax.parser import HTMLParser, Node

from ai_brief.digest.models import EventItem

_TITLE_NUM_RE = re.compile(r"^\s*(\d+)\s*[.、)．]\s*(.*)$", re.S)
_SOURCE_RE = re.compile(r"来源[:：]\s*([^|｜]+)")


def _clean(text: str) -> str:
    return " ".join((text or "").split()).strip()


def _split_label(label_text: str) -> tuple[str, str]:
    """「海外大模型公司·最有价值」→ (category, value_tag)。去 emoji 前缀，按·拆。"""
    t = _clean(label_text)
    t = re.sub(r"^[^一-鿿A-Za-z]+", "", t).strip()
    if "·" in t:
        cat, _, val = t.partition("·")
        return cat.strip(), val.strip()
    return t, ""


def _read_link(meta: Node | None) -> str:
    if meta is None:
        return ""
    for a in meta.css("a"):
        href = (a.attributes.get("href") or "").strip()
        if href.startswith("http"):
            return href
    return ""


def parse_events_digest(html: str) -> list[EventItem]:
    tree = HTMLParser(html or "")
    items: list[EventItem] = []
    for div in tree.css("div.item"):
        title_node = div.css_first(".title")
        if title_node is None:
            continue
        raw_title = _clean(title_node.text())
        m = _TITLE_NUM_RE.match(raw_title)
        if m:
            index, headline = int(m.group(1)), m.group(2).strip()
        else:
            index, headline = len(items) + 1, raw_title

        label_node = div.css_first(".label")
        category, value_tag = _split_label(label_node.text() if label_node else "")

        summary_node = div.css_first(".summary")
        body = _clean(summary_node.text()) if summary_node else ""

        meta = div.css_first(".meta")
        url = _read_link(meta)
        source = ""
        if meta is not None:
            sm = _SOURCE_RE.search(_clean(meta.text()))
            if sm:
                source = sm.group(1).strip()

        if not headline or not url:
            continue
        items.append(
            EventItem(
                index=index,
                category=category,
                value_tag=value_tag,
                headline=headline,
                url=url,
                body=body,
                image_note=source,  # 新格式无头图说明，借该字段留档来源名
            )
        )
    return items
