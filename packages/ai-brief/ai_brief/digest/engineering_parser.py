"""解析 ai-engineering-digest HTML → 一讲（AI工程 模块）。纯函数，不触网。

上游结构（扁平，无 <div> 包裹）：
  <h2>🔧 AI Engineering Digest</h2>
  <p>📅 2026年7月21日 · 第 2 讲</p>
  <p>📖 来源：<a href="…">课程名 — 小标题</a></p>
  <hr>
  <h3>💡 课程要点</h3>
  <p style="font-weight:bold">一句话课程要点</p>     ← 模块主题
  <h3>📋 核心要点</h3>
  <ol><li><strong>小标题</strong><br>正文</li> …</ol>  ← 模块内容
每天可能多讲；取哪封由 IMAP fetch_latest 按 Date 决定（最新一讲）。
"""
from __future__ import annotations

import re

from selectolax.parser import HTMLParser, Node

from ai_brief.digest.models import CorePoint, EngineeringLecture

_LECTURE_NO_RE = re.compile(r"第\s*(\d+)\s*讲")


def _clean(text: str) -> str:
    return " ".join((text or "").split()).strip()


def _next_elem(node: Node) -> Node | None:
    """下一个元素兄弟（跳过文本节点）。"""
    cur = node.next
    while cur is not None and cur.tag == "-text":
        cur = cur.next
    return cur


def _find_h3(tree: HTMLParser, keyword: str) -> Node | None:
    for h3 in tree.css("h3"):
        if keyword in (h3.text() or ""):
            return h3
    return None


def _core_points(ol: Node | None) -> list[CorePoint]:
    points: list[CorePoint] = []
    if ol is None:
        return points
    for li in ol.css("li"):
        full = _clean(li.text())
        strong = li.css_first("strong")
        sub = _clean(strong.text()) if strong else ""
        if sub and full.startswith(sub):
            body = full[len(sub):].strip()
        else:
            body = full
            sub = sub or (full[:24] + "…" if len(full) > 24 else full)
        points.append(CorePoint(subtitle=sub, body=body))
    return points


def parse_engineering_digest(html: str) -> EngineeringLecture | None:
    tree = HTMLParser(html or "")

    lecture_no = 0
    source_title = ""
    source_url = ""
    for p in tree.css("p"):
        txt = p.text() or ""
        if "讲" in txt and lecture_no == 0:
            m = _LECTURE_NO_RE.search(txt)
            if m:
                lecture_no = int(m.group(1))
        if "来源" in txt and not source_url:
            a = p.css_first("a")
            if a is not None:
                source_title = _clean(a.text())
                source_url = (a.attributes.get("href") or "").strip()

    kp_h3 = _find_h3(tree, "课程要点")
    key_node = _next_elem(kp_h3) if kp_h3 else None
    key_point = _clean(key_node.text()) if key_node else ""

    cp_h3 = _find_h3(tree, "核心要点")
    ol = _next_elem(cp_h3) if cp_h3 else None
    if ol is None or ol.tag != "ol":  # 容错：核心要点后不是紧邻 <ol> → 回退全文首个 <ol>
        ol = tree.css_first("ol")
    core_points = _core_points(ol)

    if not key_point and not core_points:
        return None
    return EngineeringLecture(
        lecture_no=lecture_no,
        source_title=source_title,
        source_url=source_url,
        key_point=key_point,
        core_points=core_points,
    )
