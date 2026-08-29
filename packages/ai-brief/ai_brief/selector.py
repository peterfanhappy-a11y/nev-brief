"""Stage-1：DeepSeek 排序 / 4 主题分类 / 中英跨源去重。

只送标题 + 首段（省 token），文章用整数序号引用（避免 LLM 篡改 uuid）。
输出经代码层校验后映射回真实 article id。返回 SelectionResult 供 enricher +
summarizer 使用。
"""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any, TypedDict, cast

from nev_pipeline.deepseek_client import extract_json_with_retry
from nev_shared.logger import get_logger

from ai_brief import config
from ai_brief.storage import Candidate

log = get_logger("ai_brief.selector")

SYSTEM_PROMPT = """你是 AIVIZENS 的 AI 行业主编，为对 AI 感兴趣的中文读者筛选每日最有价值的新闻。

给你一批今日抓取的 AI 新闻（编号 + 来源 + 标题 + 摘要片段）。请完成：

1. 跨源去重：同一事件被多个来源报道（含中英文各报一次）归为一组，duplicate_groups
   里列出编号数组。组内保留权威性最高（authority 大）或最原始的来源。
2. 四大主题分类，每个主题选出当日最有价值的 1 条（pick 为编号），可给 1-2 条备选：
   - model_research 模型研究（新模型发布、能力突破、论文、benchmark）
   - product_tools 产品工具（AI 产品/应用/平台的发布与更新）
   - skills_efficiency Skills效率（用 AI 提升工作效率的方法、agent、工作流）
   - ethics_regulation 伦理监管（政策、法规、安全、版权、社会影响）
   若某主题今日没有真正合适的新闻，pick 必须为 null，禁止硬凑。
3. top2_overall：全局最有价值的 2 条编号（用于邮件主题 + 副标题），第 1 条最重磅。
4. tool_candidates：3-5 条「值得一试的 AI 工具/产品」编号（必须来自给定新闻，不得编造）。
5. quick_hits：3-6 条适合做「一句话速览」的编号（排除已在 featured/duplicate 里的重复事件）。
6. daily_tip_topic：一句话，给出今天最适合写成「每日课堂」小教程的主题（可基于当日热点，
   自由发挥，不需对应某条新闻）。

【严格 JSON 输出】
{
  "duplicate_groups": [[3, 41]],
  "themes": {
    "model_research": {"pick": 12, "backups": [3]},
    "product_tools": {"pick": 7, "backups": []},
    "skills_efficiency": {"pick": null, "backups": []},
    "ethics_regulation": {"pick": 31, "backups": [9]}
  },
  "top2_overall": [12, 7],
  "tool_candidates": [7, 44, 61],
  "quick_hits": [5, 18, 29, 70],
  "daily_tip_topic": "用 Claude 写周报的三段式 prompt"
}
只输出 JSON，不要解释。所有编号必须是给定列表中的整数。"""


class ThemeSelection(TypedDict):
    pick: str | None
    backups: list[str]


@dataclass
class SelectionResult:
    themes: dict[str, ThemeSelection]
    top2_overall: list[str]             # article ids
    tool_candidates: list[str]
    quick_hits: list[str]
    daily_tip_topic: str
    duplicate_groups: list[list[str]] = field(default_factory=list)
    candidate_count: int = 0
    dupe_group_count: int = 0

    def featured_ids(self) -> list[str]:
        """按主题固定顺序返回已选中的 article id（跳过 null）。"""
        out: list[str] = []
        for key in config.THEME_ORDER:
            theme = self.themes.get(key)
            pick = theme["pick"] if theme else None
            if pick:
                out.append(pick)
        return out

    def all_referenced_ids(self) -> set[str]:
        ids: set[str] = set(self.top2_overall) | set(self.tool_candidates) | set(self.quick_hits)
        for key in config.THEME_ORDER:
            theme = self.themes.get(key)
            if theme is None:
                continue
            pick = theme["pick"]
            if pick:
                ids.add(pick)
            ids.update(theme["backups"])
        return ids


def _build_user_prompt(candidates: list[Candidate]) -> str:
    lines = []
    for i, c in enumerate(candidates):
        snippet = (c.content or "")[: config.STAGE1_SNIPPET_CHARS].replace("\n", " ")
        lines.append(
            f"[{i}] 来源={c.source_name}(locale={c.locale},auth={c.authority}) "
            f"标题={c.title}"
            + (f" 摘要={snippet}" if snippet else "")
        )
    return "今日候选新闻：\n" + "\n".join(lines)


def _idx_to_id(idx: object, candidates: list[Candidate]) -> str | None:
    if not isinstance(idx, int) or idx < 0 or idx >= len(candidates):
        return None
    return candidates[idx].id


def _map_list(raw: Sequence[object] | None, candidates: list[Candidate]) -> list[str]:
    out: list[str] = []
    for x in raw or []:
        cid = _idx_to_id(x, candidates)
        if cid and cid not in out:
            out.append(cid)
    return out


async def select(candidates: list[Candidate]) -> SelectionResult | None:
    """跑 Stage-1。candidates 已按 authority 排序、截断到上限。返回 None 表示 API 失败。"""
    if not candidates:
        log.warning("ai_selector.no_candidates")
        return None
    cands = candidates[: config.STAGE1_MAX_CANDIDATES]

    raw = await extract_json_with_retry(
        SYSTEM_PROMPT,
        _build_user_prompt(cands),
        model=config.get_model(),
        max_tokens=1500,
        temperature=0.2,
    )
    if raw is None:
        log.error("ai_selector.deepseek_failed")
        return None

    themes: dict[str, ThemeSelection] = {}
    for key in config.THEME_ORDER:
        t = (raw.get("themes") or {}).get(key) or {}
        t = cast(dict[str, Any], t)
        themes[key] = {
            "pick": _idx_to_id(t.get("pick"), cands),
            "backups": _map_list(t.get("backups"), cands),
        }

    dupe_groups = [_map_list(g, cands) for g in raw.get("duplicate_groups", [])]
    dupe_groups = [g for g in dupe_groups if len(g) >= 2]

    result = SelectionResult(
        themes=themes,
        top2_overall=_map_list(raw.get("top2_overall"), cands),
        tool_candidates=_map_list(raw.get("tool_candidates"), cands),
        quick_hits=_map_list(raw.get("quick_hits"), cands),
        daily_tip_topic=str(raw.get("daily_tip_topic") or "").strip(),
        duplicate_groups=dupe_groups,
        candidate_count=len(cands),
        dupe_group_count=len(dupe_groups),
    )
    if not result.featured_ids():
        log.warning("ai_selector.no_featured")  # 所有主题 null — 上层决定是否 abort
    log.info(
        "ai_selector.done",
        candidates=len(cands),
        featured=len(result.featured_ids()),
        dupes=len(dupe_groups),
    )
    return result
