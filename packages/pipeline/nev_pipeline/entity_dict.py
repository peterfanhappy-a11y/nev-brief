"""Entity dict loader (T6) — singleton cache for entity_dict.yaml.

Used as the fallback path when DeepSeek JSON parsing fails, and to determine
"hot brand" bonuses in importance scoring (Acceptance gate 4).
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import yaml

# An alias is "ASCII" (treat with word-boundary matching) if it has no CJK chars.
# This avoids false positives like "ds" matching "brands".
_ASCII_RE = re.compile(r"^[\x00-\x7f]+$")


@dataclass(frozen=True)
class EntityDict:
    brands_by_canonical: dict[str, dict]
    alias_to_canonical: dict[str, str]  # 小写 alias → canonical
    hot_brands: frozenset[str]
    topics: tuple[str, ...]


@lru_cache(maxsize=1)
def load_entity_dict() -> EntityDict:
    path = Path(__file__).parent / "entity_dict.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    brands_by_canonical: dict[str, dict] = {}
    alias_to_canonical: dict[str, str] = {}
    hot: set[str] = set()
    for b in data.get("brands", []):
        canonical = b["canonical"]
        brands_by_canonical[canonical] = b
        for alias in b.get("aliases", []):
            alias_to_canonical[alias.lower()] = canonical
        # canonical itself is also a self-alias
        alias_to_canonical[canonical.lower()] = canonical
        if b.get("is_hot"):
            hot.add(canonical)
    return EntityDict(
        brands_by_canonical=brands_by_canonical,
        alias_to_canonical=alias_to_canonical,
        hot_brands=frozenset(hot),
        topics=tuple(data.get("topics", [])),
    )


def canonicalize_brand(alias_or_canonical: str) -> str | None:
    """Map an alias or canonical name → canonical (case-insensitive). None if unknown."""
    if not alias_or_canonical:
        return None
    d = load_entity_dict()
    return d.alias_to_canonical.get(alias_or_canonical.lower())


def canonicalize_brands(raw: list[str]) -> list[str]:
    """Map a list of DeepSeek-returned brand strings → canonical, dedup'd, order-preserved.

    Use this whenever a module calls DeepSeek to extract brands: the LLM often
    returns Chinese aliases ("比亚迪", "蔚来") instead of canonical English ("BYD",
    "NIO") even when the prompt explicitly asks for canonical names. entity_dict
    is the single source of truth.

    Unrecognized brands (not in entity_dict) are preserved as-is so novel-brand
    information isn't lost — downstream scoring/filtering can decide whether to
    drop them.

    See feedback_deepseek_brand_canonicalize.md for the painful history.
    """
    seen: set[str] = set()
    out: list[str] = []
    for b in raw:
        if not b or not b.strip():
            continue
        stripped = b.strip()
        canonical = canonicalize_brand(stripped) or stripped
        if canonical not in seen:
            seen.add(canonical)
            out.append(canonical)
    return out


def find_brands_in_text(text: str) -> list[str]:
    """Find canonical brand names mentioned in *text*.

    ASCII aliases (e.g. "BYD", "ds") are matched with word boundaries to avoid
    false positives like "ds" matching "brands". CJK aliases (e.g. "比亚迪")
    are substring-matched since Chinese has no whitespace word boundaries.
    Naive O(N*aliases) — fine for MVP (50 brands × few aliases each).
    """
    if not text:
        return []
    d = load_entity_dict()
    text_lower = text.lower()
    found: list[str] = []
    seen: set[str] = set()
    for alias, canonical in d.alias_to_canonical.items():
        if canonical in seen:
            continue
        if _ASCII_RE.match(alias):
            # Word-boundary match for ASCII aliases.
            if re.search(rf"\b{re.escape(alias)}\b", text_lower):
                found.append(canonical)
                seen.add(canonical)
        else:
            # Substring match for CJK aliases.
            if alias in text_lower:
                found.append(canonical)
                seen.add(canonical)
    return found
