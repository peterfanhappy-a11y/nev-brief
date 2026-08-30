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
_SOURCE_RE = re.compile(r"来源\s*[:：]?\s*([^|｜]+)")
_SOURCE_URL_RE = re.compile(r"^\s*([^·•|｜]+?)\s*[·•]\s*(https://\S+)")
_SOURCE_PREFIX_RE = re.compile(r"^\s*([^·•|｜]+?)\s*[·•]")
_FLAT_VALUE_TAGS = frozenset({"最有价值", "最吸引眼球"})


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


def _parse_current_markup(tree: HTMLParser) -> list[EventItem]:
    """Parse the current upstream blocks: label div, h2, summary p, link p."""
    items: list[EventItem] = []
    for h2 in tree.css("h2, h3"):
        block = h2.parent
        if block is None or block.tag != "div":
            continue
        if h2.tag == "h3" and block.css_first("h2") is not None:
            continue
        if _SOURCE_RE.search(_clean(block.text())) is None:
            continue
        raw_title = _clean(h2.text())
        match = _TITLE_NUM_RE.match(raw_title)
        if match:
            index, headline = int(match.group(1)), match.group(2).strip()
        else:
            index, headline = len(items) + 1, raw_title

        label_node = next(
            (node for node in block.css("div") if node.css_first("h2") is None),
            None,
        )
        label_text = _clean(label_node.text()) if label_node else ""
        source_match = _SOURCE_RE.search(label_text)
        source = source_match.group(1).strip() if source_match else ""
        label_text = re.sub(r"\s*[·•]\s*来源\s*[:：]?\s*.+$", "", label_text)
        category, value_tag = _split_label(label_text)

        body_parts = [
            _clean(p.text()) for p in block.css("p") if not p.css_first("a")
        ]
        url = ""
        for anchor in block.css("a"):
            href = (anchor.attributes.get("href") or "").strip()
            if "阅读原文" in _clean(anchor.text()) and href.startswith("https://"):
                url = href
                break
        if headline and url:
            items.append(
                EventItem(
                    index=index,
                    category=category,
                    value_tag=value_tag,
                    headline=headline,
                    url=url,
                    body=" ".join(part for part in body_parts if part),
                    image_note=source,
                )
            )
    return items


def _parse_flat_h2_markup(tree: HTMLParser) -> list[EventItem]:
    """Parse the flat current email: category h2, story h2, then metadata siblings."""

    def next_element(node: Node) -> Node | None:
        sibling = node.next
        while sibling is not None and sibling.tag.startswith("-"):
            sibling = sibling.next
        return sibling

    def direct_h2_count(node: Node) -> int:
        count = 0
        child = node.child
        while child is not None:
            if child.tag == "h2":
                count += 1
            child = child.next
        return count

    items: list[EventItem] = []
    category = ""
    value_tag = ""
    stories_remaining = 0
    for h2 in tree.css("h2"):
        raw_title = _clean(h2.text())
        next_node = next_element(h2)
        candidate_category, candidate_value_tag = _split_label(raw_title)
        is_direct_story = next_node is not None and next_node.tag == "h2"
        is_story_wrapper = (
            next_node is not None
            and next_node.tag == "div"
            and direct_h2_count(next_node) == 2
        )
        if (
            candidate_value_tag in _FLAT_VALUE_TAGS
            and (is_direct_story or is_story_wrapper)
        ):
            category, value_tag = candidate_category, candidate_value_tag
            stories_remaining = 2
            continue
        if stories_remaining == 0:
            continue
        stories_remaining -= 1

        body_parts: list[str] = []
        source = ""
        url = ""
        node = next_node
        while node is not None and node.tag != "h2":
            if node.tag == "p":
                text = _clean(node.text())
                source_url_match = _SOURCE_URL_RE.search(text)
                source_match = _SOURCE_RE.search(text)
                if source_url_match is not None:
                    source = source_url_match.group(1).strip()
                    url = source_url_match.group(2)
                elif source_match is not None:
                    source = source_match.group(1).strip()
                elif (source_prefix := _SOURCE_PREFIX_RE.search(text)) is not None:
                    source = source_prefix.group(1).strip()
                    for anchor in node.css("a"):
                        href = (anchor.attributes.get("href") or "").strip()
                        if href.startswith("https://"):
                            url = href
                            break
                else:
                    if text:
                        body_parts.append(text)
            if url:
                break
            node = next_element(node)

        match = _TITLE_NUM_RE.match(raw_title)
        index = int(match.group(1)) if match else len(items) + 1
        headline = match.group(2).strip() if match else raw_title
        if category and headline and source and url:
            items.append(
                EventItem(
                    index=index,
                    category=category,
                    value_tag=value_tag,
                    headline=headline,
                    url=url,
                    body=" ".join(body_parts),
                    image_note=source,
                )
            )
    return items


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
    return items or _parse_current_markup(tree) or _parse_flat_h2_markup(tree)
