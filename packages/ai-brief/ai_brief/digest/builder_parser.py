"""解析 follow-builder-digest 纯文本 → 10 条 BuilderItem。纯函数，不触网。

结构（每条 3+ 行）：
  ★ [1] [人名/来源] 标题        ← ★=前5, 🔥=后5
     缩进正文（可能多行）
     https://...
按序号切块；[人名] 从标题开头的方括号提取（可缺省）。
"""
from __future__ import annotations

import re

from ai_brief.digest.models import BuilderItem

# 行首形如「★ [1] ...」或「🔥 [6] ...」
_HEADER_RE = re.compile(r"^\s*(★|🔥)\s*\[(\d+)\]\s*(.*)$")
_PERSON_RE = re.compile(r"^\[([^\]]+)\]\s*(.*)$")
_URL_RE = re.compile(r"https?://\S+")


def _split_person(head_rest: str) -> tuple[str, str]:
    m = _PERSON_RE.match(head_rest.strip())
    if m:
        return m.group(1).strip(), m.group(2).strip()
    return "", head_rest.strip()


def parse_builder_digest(text: str) -> list[BuilderItem]:
    lines = (text or "").splitlines()

    # 先按 header 行切出每条的行区间
    headers: list[tuple[int, str, int, str]] = []  # (line_no, marker, index, head_rest)
    for i, line in enumerate(lines):
        m = _HEADER_RE.match(line)
        if m:
            headers.append((i, m.group(1), int(m.group(2)), m.group(3)))

    items: list[BuilderItem] = []
    for h, (line_no, marker, index, head_rest) in enumerate(headers):
        end = headers[h + 1][0] if h + 1 < len(headers) else len(lines)
        person, headline = _split_person(head_rest)

        body_parts: list[str] = []
        url = ""
        for line in lines[line_no + 1:end]:
            s = line.strip()
            if not s:
                continue
            um = _URL_RE.search(s)
            if um and s.startswith(("http://", "https://")):
                url = um.group(0)
                continue
            body_parts.append(s)
        # 正文里若混入尾部 URL 也剥掉
        body = " ".join(body_parts).strip()

        items.append(
            BuilderItem(
                index=index,
                is_top5=(marker == "★"),
                person=person,
                headline=headline,
                body=body,
                url=url,
            )
        )
    return items
