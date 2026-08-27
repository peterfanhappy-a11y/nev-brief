"""RSS feed 解析 — 提取条目 URL + 标题 + 摘要 + 图片 + 发布时间。

关键：许多站点（OpenAI 等）对文章页返回 403 反爬，但 RSS feed 公开可取。
所以 feed 自带的 summary/image 作为内容基线；runner 再尝试抓文章页升级正文。
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import cast

import feedparser
from selectolax.parser import HTMLParser


@dataclass(frozen=True)
class FeedEntry:
    url: str
    title: str
    summary: str | None       # feed 自带摘要（可能含 HTML，已去标签）
    image: str | None         # media:content / thumbnail / enclosure / summary <img>
    published_at: str | None  # ISO8601 or None


def parse_feed(raw: bytes | str) -> list[FeedEntry]:
    fp = feedparser.parse(raw)
    out: list[FeedEntry] = []
    for e in fp.entries:
        url = (getattr(e, "link", "") or "").strip()
        title = (getattr(e, "title", "") or "").strip()
        if not url or not title:
            continue
        out.append(
            FeedEntry(
                url=url,
                title=title,
                summary=_entry_summary(e),
                image=_entry_image(e),
                published_at=_entry_time(e),
            )
        )
    return out


def _entry_summary(entry: object) -> str | None:
    # content:encoded 优先（通常全文），否则 summary
    raw = ""
    content = getattr(entry, "content", None)
    if content:
        raw = content[0].get("value", "")
    if not raw:
        raw = getattr(entry, "summary", "") or ""
    if not raw:
        return None
    text = HTMLParser(raw).text(separator="\n", strip=True) if "<" in raw else raw
    text = text.strip()
    return text or None


def _entry_image(entry: object) -> str | None:
    for key in ("media_content", "media_thumbnail"):
        items = getattr(entry, key, None)
        if items:
            for it in items:
                u = (it.get("url") or "").strip()
                if u.startswith("https://"):
                    return u
    for enc in getattr(entry, "enclosures", None) or []:
        href = (enc.get("href") or "").strip()
        if href.startswith("https://") and "image" in (enc.get("type") or ""):
            return href
    # summary HTML 里的首个 <img>
    for field in ("content", "summary"):
        raw = ""
        content = getattr(entry, "content", None)
        if field == "content" and content:
            raw = content[0].get("value", "")
        elif field == "summary":
            raw = getattr(entry, "summary", "") or ""
        if raw and "<img" in raw:
            img = HTMLParser(raw).css_first("img")
            if img:
                src = (img.attributes.get("src") or "").strip()
                if src.startswith("https://"):
                    return src
    return None


def _entry_time(entry: object) -> str | None:
    for attr in ("published_parsed", "updated_parsed"):
        t = getattr(entry, attr, None)
        if t:
            try:
                parts = cast(tuple[int, int, int, int, int, int], tuple(t[:6]))
                return datetime(*parts, tzinfo=UTC).isoformat()
            except (ValueError, TypeError):
                continue
    return None
