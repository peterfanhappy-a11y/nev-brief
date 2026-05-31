"""DeepSeek Prompt 2 cluster summarizer with overflow retry + algorithmic fallback.

Spec §6.3. Returns ClusterSummary with title ≤25 chars, summary ≤120 chars
guaranteed (either via LLM compliance or algorithmic truncate).

Returns None if DeepSeek API fails completely (auth/network/JSON parse) — caller
filters None to satisfy fail-safe acceptance gate.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from nev_pipeline.deepseek_client import extract_json_with_retry
from nev_shared.logger import get_logger

from nev_summarizer.char_validator import (
    SUMMARY_MAX,
    TITLE_MAX,
    count_chars,
    is_within_limit,
    truncate,
)
from nev_summarizer.cluster_aggregator import Cluster

log = get_logger("summarizer")

# Spec §6.3 verbatim
SYSTEM_PROMPT = """你是新能源汽车行业资深编辑，为 B 端从业者撰写每日简报。

【写作准则】
1. 标题：客观陈述，无感叹号/标题党，≤25 中文字
2. 摘要：3 句话内，回答 "发生了什么 / 影响是什么 / 数据是什么"，≤120 中文字
3. 必须包含具体数据（销量/价格/百分比），无数据则注明"数据未披露"
4. 不输出主观判断
5. 多源矛盾数据 → 以官方源为准并标注
6. 未证实传闻 → 明确标"据 XX 报道，未经官方确认"

【严格 JSON】
{
  "title": "≤25字客观标题",
  "summary": "≤120字摘要",
  "key_data": { "type": "sales|price|funding|production|none", "values": {} },
  "brands": ["..."],
  "topics": ["..."],
  "primary_source": "权威性最高源名",
  "source_count": N
}
不要解释，只输出 JSON。"""


@dataclass(frozen=True)
class ClusterSummary:
    title: str                  # ≤25 chars guaranteed
    summary: str                # ≤120 chars guaranteed
    key_data: dict[str, Any]
    brands: list[str]
    topics: list[str]
    primary_source: str
    source_count: int
    used_truncation: bool       # True if algorithmic fallback kicked in
    retry_count: int            # 0 or 1


def _build_user_prompt(cluster: Cluster) -> str:
    """Same-event multi-source article body for Prompt 2."""
    # Sort by source_authority desc so primary_source 提示更清楚
    sorted_arts = sorted(cluster.articles, key=lambda a: -a.source_authority)
    lines: list[str] = ["同一事件的多家媒体报道：\n"]
    for i, a in enumerate(sorted_arts, 1):
        lines.append(f"【源 {i}：{a.source_name}（权威度 {a.source_authority}/10）】")
        lines.append(a.title)
        # Cap each article body to 800 chars to keep total prompt manageable
        lines.append((a.clean_text or "")[:800])
        lines.append("")
    return "\n".join(lines)


def _build_retry_prompt(prev_title_len: int, prev_summary_len: int) -> str:
    """Tells DeepSeek which fields overran on the first attempt."""
    parts = []
    if prev_title_len > TITLE_MAX:
        parts.append(f"标题前次 {prev_title_len} 字超出 {TITLE_MAX} 字限制")
    if prev_summary_len > SUMMARY_MAX:
        parts.append(f"摘要前次 {prev_summary_len} 字超出 {SUMMARY_MAX} 字限制")
    return "前次输出超字：" + "；".join(parts) + "。请严格精简后重新输出。"


def _validate(result: dict[str, Any]) -> tuple[bool, str, str]:
    title = str(result.get("title", "")).strip()
    summary = str(result.get("summary", "")).strip()
    ok = is_within_limit(title, TITLE_MAX) and is_within_limit(summary, SUMMARY_MAX)
    return ok, title, summary


async def summarize_cluster(cluster: Cluster) -> ClusterSummary | None:
    """Call Prompt 2 → validate → retry once if over → algorithmic truncate fallback.

    Returns None if DeepSeek API itself fails (auth / network / non-JSON).
    """
    user = _build_user_prompt(cluster)
    result = await extract_json_with_retry(
        SYSTEM_PROMPT, user, max_tokens=500, temperature=0.3,
    )
    if result is None:
        log.warning("summarize_deepseek_failed", cluster_id=cluster.cluster_id)
        return None

    ok, title, summary = _validate(result)
    retry_count = 0
    if not ok:
        retry_count = 1
        retry_user = user + "\n\n" + _build_retry_prompt(
            count_chars(title), count_chars(summary),
        )
        result2 = await extract_json_with_retry(
            SYSTEM_PROMPT, retry_user, max_tokens=500, temperature=0.3,
        )
        if result2 is not None:
            ok2, title2, summary2 = _validate(result2)
            # 用重试结果覆盖（即便仍然超），合并 key_data 等元数据从首次取
            title, summary = title2, summary2
            ok = ok2
            # Merge metadata: prefer retry's title/summary, keep first's other fields
            for k in ("key_data", "brands", "topics", "primary_source", "source_count"):
                if k not in result2 or not result2.get(k):
                    result2[k] = result.get(k)
            result = result2

    # Algorithmic truncate fallback
    used_truncation = not ok
    if used_truncation:
        title = truncate(title, TITLE_MAX)
        summary = truncate(summary, SUMMARY_MAX)
        log.warning(
            "summarize_truncated", cluster_id=cluster.cluster_id,
            title_len=count_chars(title), summary_len=count_chars(summary),
        )

    return ClusterSummary(
        title=title,
        summary=summary,
        key_data=dict(result.get("key_data") or {}),
        brands=list(result.get("brands") or []),
        topics=list(result.get("topics") or []),
        primary_source=str(result.get("primary_source") or ""),
        source_count=int(result.get("source_count") or len(cluster.articles)),
        used_truncation=used_truncation,
        retry_count=retry_count,
    )
