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
_LINK_CARD_LABEL_RE = re.compile(
    r"^(?P<label>.+?)\s+(?P<index>\d+)/\d+\s*[·•]\s*(?P<source>.+)$"
)
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

    def direct_children(node: Node) -> list[Node]:
        children: list[Node] = []
        child = node.child
        while child is not None:
            if not child.tag.startswith("-"):
                children.append(child)
            child = child.next
        return children

    def is_flat_story_wrapper(node: Node) -> bool:
        children = direct_children(node)
        return [child.tag for child in children] == ["div", "h2", "p", "p"]

    items: list[EventItem] = []
    for label in tree.css("h2"):
        category, value_tag = _split_label(_clean(label.text()))
        first_card = next_element(label)
        if (
            value_tag not in _FLAT_VALUE_TAGS
            or first_card is None
            or first_card.tag != "div"
            or not is_flat_story_wrapper(first_card)
        ):
            continue

        card: Node | None = first_card
        for _ in range(2):
            if card is None or card.tag != "div" or not is_flat_story_wrapper(card):
                break
            children = direct_children(card)
            title_node = children[1]
            body_parts: list[str] = []
            source = ""
            url = ""
            for paragraph in children[2:]:
                text = _clean(paragraph.text())
                source_url_match = _SOURCE_URL_RE.search(text)
                source_match = _SOURCE_RE.search(text)
                if source_url_match is not None:
                    source = source_url_match.group(1).strip()
                    url = source_url_match.group(2)
                elif source_match is not None:
                    source = source_match.group(1).strip()
                elif (source_prefix := _SOURCE_PREFIX_RE.search(text)) is not None:
                    source = source_prefix.group(1).strip()
                    for anchor in paragraph.css("a"):
                        href = (anchor.attributes.get("href") or "").strip()
                        if href.startswith("https://"):
                            url = href
                            break
                elif text:
                    body_parts.append(text)

            raw_title = _clean(title_node.text())
            match = _TITLE_NUM_RE.match(raw_title)
            index = int(match.group(1)) if match else len(items) + 1
            headline = match.group(2).strip() if match else raw_title
            if headline and source and url:
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
            card = next_element(card)
    return items


def _parse_link_card_h3_markup(tree: HTMLParser) -> list[EventItem]:
    """Parse current h3 cards with a category/index/source label and direct link."""
    items: list[EventItem] = []
    for h3 in tree.css("h3"):
        card = h3.parent
        if card is None or card.tag != "div":
            continue

        children: list[Node] = []
        child = card.child
        while child is not None:
            if not child.tag.startswith("-"):
                children.append(child)
            child = child.next
        if [child.tag for child in children] != ["div", "h3", "p", "a"]:
            continue

        label_match = _LINK_CARD_LABEL_RE.match(_clean(children[0].text()))
        if label_match is None:
            continue
        category, value_tag = _split_label(label_match.group("label"))
        anchor = children[3]
        url = (anchor.attributes.get("href") or "").strip()
        if (
            value_tag not in _FLAT_VALUE_TAGS
            or "原文链接" not in _clean(anchor.text())
            or not url.startswith("https://")
        ):
            continue

        headline = _clean(h3.text())
        body = _clean(children[2].text())
        if headline and body:
            items.append(
                EventItem(
                    index=int(label_match.group("index")),
                    category=category,
                    value_tag=value_tag,
                    headline=headline,
                    url=url,
                    body=body,
                    image_note=label_match.group("source").strip(),
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
    return (
        items
        or _parse_current_markup(tree)
        or _parse_link_card_h3_markup(tree)
        or _parse_flat_h2_markup(tree)
    )
