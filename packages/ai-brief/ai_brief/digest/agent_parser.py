"""解析 ai-agent-digest HTML → 工具列表（Agent工具 模块，3 选 2）。纯函数，不触网。

上游结构（扁平）：
  <h2>🔬 AI Agent 日度分析报告</h2>
  <h3>1️⃣ Github/owner/repo — 一句话简介</h3>
  <p><strong>📊 Stars this week:</strong> 10,983</p>
  <p><strong>📝 3 要点总结：</strong></p>
  <ol><li><strong>核心功能：</strong>…</li> …</ol>
  <p>🔗 <a href="https://github.com/…">GitHub 仓库</a></p>
  <hr>  … 下一个工具
以每个 <h3> 为锚，向后取兄弟节点到下一个 <h3>。
"""
from __future__ import annotations

import re

from selectolax.parser import HTMLParser, Node

from ai_brief.digest.models import AgentTool

_STARS_RE = re.compile(r"([\d,]+)")
_LEAD_JUNK_RE = re.compile(r"^[\s\d0-9️⃣️⃣\W]+")  # 行首 emoji 序号/符号


def _clean(text: str) -> str:
    return " ".join((text or "").split()).strip()


def _next_elem(node: Node) -> Node | None:
    cur = node.next
    while cur is not None and cur.tag == "-text":
        cur = cur.next
    return cur


def _strip_rank(text: str) -> tuple[int, str]:
    """「1️⃣ Github/owner/repo — 简介」→ (1, owner/repo — 简介)。"""
    t = _clean(text)
    m = re.match(r"^\s*(\d)", t.replace("️⃣", ""))
    rank = int(m.group(1)) if m else 0
    name = _LEAD_JUNK_RE.sub("", t).strip()
    name = re.sub(r"^Github[/／]", "", name, flags=re.I).strip()
    return rank, name


def parse_agent_digest(html: str) -> list[AgentTool]:
    tree = HTMLParser(html or "")
    tools: list[AgentTool] = []
    for i, h3 in enumerate(tree.css("h3"), start=1):
        rank, name = _strip_rank(h3.text())
        if not name:
            continue
        stars = ""
        points: list[str] = []
        url = ""
        n = _next_elem(h3)
        while n is not None and n.tag != "h3":
            if n.tag == "p":
                txt = n.text() or ""
                if "Stars" in txt:
                    m = _STARS_RE.search(txt.split(":", 1)[-1])
                    if m:
                        stars = m.group(1)
                a = n.css_first("a")
                if a is not None:
                    href = (a.attributes.get("href") or "").strip()
                    if href.startswith("http") and not url:
                        url = href
            elif n.tag == "ol" and not points:
                for li in n.css("li"):
                    t = _clean(li.text())
                    if t:
                        points.append(t)
            n = _next_elem(n)

        tools.append(
            AgentTool(rank=rank or i, name=name, stars=stars, points=points, url=url)
        )
    return tools
