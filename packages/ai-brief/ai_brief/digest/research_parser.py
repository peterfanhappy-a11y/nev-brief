"""解析 ai-research-digest HTML → 论文列表（AI研究 模块）。纯函数，不触网。

上游结构：每篇一个带 border-left 的 <div>：
  <h2>[Arxiv] 中文标题（English Title）</h2>
  <h3>Core Takeaways</h3>
  <p><strong>1)</strong> …</p>  ×3
  <p><a href="https://…">Link: …</a></p>
以每个 <h2> 为锚，取其所在 item <div>。来源标签（[Arxiv]/[HuggingFace]）与附件名匹配选头图。
"""
from __future__ import annotations

import re

from selectolax.parser import HTMLParser, Node

from ai_brief.digest.models import ResearchPaper

_TAG_RE = re.compile(r"^\s*[\[【]([^\]】]+)[\]】]\s*(.*)$", re.S)
_PAREN_TAIL_RE = re.compile(r"[（(][^（）()]*[）)]\s*$")  # 结尾的英文括注


def _clean(text: str) -> str:
    return " ".join((text or "").split()).strip()


def _item_div(node: Node) -> Node | None:
    cur = node.parent
    while cur is not None and cur.tag != "div":
        cur = cur.parent
    return cur


def _split_title(h2_text: str) -> tuple[str, str]:
    """「[Arxiv] 中文标题（English）」→ (source_tag, 中文标题去英文括注)。"""
    t = _clean(h2_text)
    m = _TAG_RE.match(t)
    tag, title = (m.group(1).strip(), m.group(2).strip()) if m else ("", t)
    title = _PAREN_TAIL_RE.sub("", title).strip()
    return tag, title


def _read_link(block: Node) -> str:
    for a in block.css("a"):
        href = (a.attributes.get("href") or "").strip()
        if href.startswith("http"):
            return href
    return ""


def _parse_current_markup(tree: HTMLParser) -> list[ResearchPaper]:
    """Parse current emails where each h2 and its paragraphs are direct body children."""
    papers: list[ResearchPaper] = []
    for h2 in tree.css("h2"):
        if h2.parent is None or h2.parent.tag != "body":
            continue
        tag, title = _split_title(h2.text())
        if not title:
            continue
        takeaways: list[str] = []
        url = ""
        sibling = h2.next
        while sibling is not None and sibling.tag != "h2":
            if sibling.tag == "p":
                txt = _clean(sibling.text())
                anchors = sibling.css("a")
                if anchors:
                    for anchor in anchors:
                        href = (anchor.attributes.get("href") or "").strip()
                        if href.startswith("https://"):
                            url = href
                            break
                elif txt and not txt.lower().startswith("link:"):
                    txt = re.sub(r"^\s*\d+(?:[^\w]|_)*\s*", "", txt, count=1).strip()
                    if txt:
                        takeaways.append(txt)
            sibling = sibling.next
        papers.append(
            ResearchPaper(source_tag=tag, title=title, takeaways=takeaways, url=url)
        )
    return papers


def parse_research_digest(html: str) -> list[ResearchPaper]:
    tree = HTMLParser(html or "")
    papers: list[ResearchPaper] = []
    for h2 in tree.css("h2"):
        block = _item_div(h2)
        if block is None:
            continue
        tag, title = _split_title(h2.text())
        if not title:
            continue
        url = _read_link(block)

        takeaways: list[str] = []
        for p in block.css("p"):
            txt = _clean(p.text())
            if not txt or txt.lower().startswith("link:"):
                continue
            # 去掉「1)」「2)」等序号前缀
            txt = re.sub(r"^\s*\d+\s*[)）.．、]\s*", "", txt).strip()
            if txt:
                takeaways.append(txt)

        papers.append(
            ResearchPaper(source_tag=tag, title=title, takeaways=takeaways, url=url)
        )
    return papers or _parse_current_markup(tree)
