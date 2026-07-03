"""Stage-2：DeepSeek 一次 mega-call 生成完整简报文档。

关键防幻觉设计：featured/tools/quick_hits 里的 url / og_image / source_name 一律由
代码从 DB 注入，LLM 只用整数 ref 引用文章并产出文字（标题/详情/意义）。LLM 编不出
不存在的链接。校验：pydantic schema + ref 越界丢弃。失败带错误反馈重试 1 次。
"""
from __future__ import annotations

import json
from dataclasses import dataclass

from nev_pipeline.deepseek_client import extract_json_with_retry
from nev_shared.logger import get_logger
from pydantic import ValidationError

from ai_brief import config
from ai_brief.schema import (
    AiBriefContent,
    DailyTip,
    FeaturedItem,
    QuickHit,
    Stage1Stats,
    Theme,
    Tool,
    YesterdayTop,
)
from ai_brief.selector import SelectionResult
from ai_brief.storage import Candidate

log = get_logger("ai_brief.summarizer")

SYSTEM_PROMPT = """你是 AIVIZENS 的 AI 行业主编，为中文读者写每日 AI 简报。文风参考 The Rundown AI：
专业、精炼、有洞见，让读者「5 分钟看懂今天 AI 圈发生了什么、为什么重要」。

【翻译与命名】公司/产品/模型名保留英文原名（GPT-5、Claude、Gemini、OpenAI）。译意不译词，
写成地道中文新闻编译体，不要机翻腔。

给你今日已选定的文章（featured 按四大主题排列，另有 tools/quick_hits 候选），每篇有编号 ref。
请产出严格 JSON：

{
  "subject": "邮件主题：当日最重磅新闻改写成最抓眼球的中文标题，≤22字，让人一看就想点开",
  "preheader": "以「另外：」开头 + 第二重磅新闻的吸睛短标题，≤28字",
  "intro_bullets": ["每个 featured 主题一句话导读，带 emoji 开头，≤20字", ...],
  "featured": [
    {
      "ref": 0,                    // 对应下方 featured 文章编号
      "theme": "model_research",   // 保持文章给定主题
      "headline": "≤18字中文标题",
      "details": ["详情要点1 ≤28字", "详情要点2", "详情要点3"],  // 2-4 条
      "significance": "意义：为什么这条重要，≤70字"
    }
  ],
  "tools": [ {"ref": 3, "one_liner": "这个工具能做什么，≤28字"} ],   // 0-5 条，从 tools 候选选
  "daily_tip": {"title": "≤14字", "body": "一条可立即上手的 AI 使用技巧/教程，≤180字"},
  "quick_hits": [ {"ref": 5, "text": "一句话速览这条新闻，≤36字"} ]   // 3-5 条，从 quick_hits 候选选
}

要求：
- intro_bullets 数量 = featured 数量，一一对应。
- featured 保持给定顺序与 theme，不要新增/凭空编造文章。
- daily_tip 可基于给定主题自由发挥，无需对应某篇文章。
- 只输出 JSON，不要解释。所有 ref 必须是给定编号。"""


@dataclass
class _RefArticle:
    ref: int
    candidate: Candidate
    theme: str | None  # featured 才有


def _lookup(cands_by_id: dict[str, Candidate], cid: str) -> Candidate | None:
    return cands_by_id.get(cid)


def _build_prompt(
    featured: list[_RefArticle],
    tools: list[_RefArticle],
    quick_hits: list[_RefArticle],
    tip_topic: str,
    yesterday_headline: str | None,
) -> str:
    parts = ["## Featured 文章（按主题顺序）"]
    for r in featured:
        c = r.candidate
        body = (c.content or "")[: config.STAGE2_ARTICLE_CHARS].replace("\n", " ")
        parts.append(
            f"[ref={r.ref}] theme={r.theme} 来源={c.source_name}\n"
            f"  标题：{c.title}\n  正文：{body or '（无正文，仅标题）'}"
        )
    if tools:
        parts.append("\n## Tools 候选")
        for r in tools:
            c = r.candidate
            snip = (c.content or "")[:150].replace("\n", " ")
            parts.append(f"[ref={r.ref}] {c.title} — {snip}")
    if quick_hits:
        parts.append("\n## Quick hits 候选")
        for r in quick_hits:
            c = r.candidate
            parts.append(f"[ref={r.ref}] {c.title}")
    parts.append(f"\n## 每日课堂主题建议：{tip_topic or '（自由选择今日相关的实用技巧）'}")
    if yesterday_headline:
        parts.append(f"\n## 昨日头条（仅供参考，不要写入 featured）：{yesterday_headline}")
    return "\n".join(parts)


def _assemble(
    raw: dict,
    ref_map: dict[int, _RefArticle],
    brief_date: str,
    yesterday_top: YesterdayTop | None,
    stats: Stage1Stats,
    model: str,
) -> AiBriefContent:
    """把 LLM 文字 + DB 事实（url/og_image/source）组装成 AiBriefContent。"""
    featured: list[FeaturedItem] = []
    for f in raw.get("featured", []):
        ref = f.get("ref")
        ra = ref_map.get(ref)
        if ra is None:
            continue
        c = ra.candidate
        theme_key = ra.theme or f.get("theme")
        try:
            theme = Theme(theme_key)
        except ValueError:
            continue
        featured.append(
            FeaturedItem(
                theme=theme,
                theme_label=config.THEME_META[theme.value]["label"],
                headline=str(f.get("headline", ""))[:40],
                details=[str(d) for d in (f.get("details") or []) if str(d).strip()][:5]
                or ["详情待补"],
                significance=str(f.get("significance", ""))[:160],
                url=c.url,
                source_name=c.source_name,
                og_image=c.og_image,
                article_id=c.id,
            )
        )

    tools: list[Tool] = []
    for t in raw.get("tools", []):
        ra = ref_map.get(t.get("ref"))
        if ra is None:
            continue
        tools.append(
            Tool(
                name=ra.candidate.title[:40],
                one_liner=str(t.get("one_liner", ""))[:60],
                url=ra.candidate.url,
            )
        )

    quick_hits: list[QuickHit] = []
    for q in raw.get("quick_hits", []):
        ra = ref_map.get(q.get("ref"))
        if ra is None:  # 无效 ref = LLM 幻觉，整条丢弃
            continue
        text = str(q.get("text", "")).strip()
        if text:
            quick_hits.append(QuickHit(text=text[:80], url=ra.candidate.url))

    tip = None
    if raw.get("daily_tip"):
        dt = raw["daily_tip"]
        if dt.get("title") and dt.get("body"):
            tip = DailyTip(title=str(dt["title"])[:30], body=str(dt["body"])[:260])

    intro = [str(b)[:40] for b in (raw.get("intro_bullets") or []) if str(b).strip()]
    if not intro:
        intro = [f.headline for f in featured]

    return AiBriefContent(
        brief_date=brief_date,
        subject=str(raw.get("subject", ""))[:44] or (featured[0].headline if featured else "AI 简报"),
        preheader=str(raw.get("preheader", ""))[:60],
        intro_bullets=intro[: len(featured)] or intro[:1],
        featured=featured,
        tools=tools[:5],
        daily_tip=tip,
        quick_hits=quick_hits[:6],
        yesterday_top=yesterday_top,
        model=model,
        stage1_stats=stats,
    )


async def summarize(
    selection: SelectionResult,
    candidates: list[Candidate],
    *,
    brief_date: str,
    yesterday_top: YesterdayTop | None,
) -> AiBriefContent | None:
    """跑 Stage-2。返回校验通过的 AiBriefContent，或 None（API/校验彻底失败）。"""
    by_id = {c.id: c for c in candidates}

    # 给选中文章分配连续 ref 编号
    ref_map: dict[int, _RefArticle] = {}
    featured_refs: list[_RefArticle] = []
    n = 0
    for key in config.THEME_ORDER:
        pick = selection.themes.get(key, {}).get("pick")
        c = by_id.get(pick) if pick else None
        if c:
            ra = _RefArticle(ref=n, candidate=c, theme=key)
            ref_map[n] = ra
            featured_refs.append(ra)
            n += 1

    if not featured_refs:
        log.error("ai_summarizer.no_featured")
        return None

    tool_refs: list[_RefArticle] = []
    for cid in selection.tool_candidates:
        c = by_id.get(cid)
        if c:
            ra = _RefArticle(ref=n, candidate=c, theme=None)
            ref_map[n] = ra
            tool_refs.append(ra)
            n += 1

    quick_refs: list[_RefArticle] = []
    featured_ids = {r.candidate.id for r in featured_refs}
    for cid in selection.quick_hits:
        c = by_id.get(cid)
        if c and c.id not in featured_ids:
            ra = _RefArticle(ref=n, candidate=c, theme=None)
            ref_map[n] = ra
            quick_refs.append(ra)
            n += 1

    user_prompt = _build_prompt(
        featured_refs, tool_refs, quick_refs,
        selection.daily_tip_topic,
        yesterday_top.headline if yesterday_top else None,
    )
    stats = Stage1Stats(candidates=selection.candidate_count, dupe_groups=selection.dupe_group_count)
    model = config.get_model()

    err_feedback = ""
    for attempt in (1, 2):
        prompt = user_prompt + (f"\n\n上次输出有误：{err_feedback}，请修正后重新输出。" if err_feedback else "")
        raw = await extract_json_with_retry(
            SYSTEM_PROMPT, prompt, model=model,
            max_tokens=config.STAGE2_MAX_TOKENS, temperature=config.STAGE2_TEMPERATURE,
        )
        if raw is None:
            log.error("ai_summarizer.deepseek_failed", attempt=attempt)
            return None
        try:
            brief = _assemble(raw, ref_map, brief_date, yesterday_top, stats, model)
            log.info(
                "ai_summarizer.done",
                featured=len(brief.featured), tools=len(brief.tools),
                quick=len(brief.quick_hits), attempt=attempt,
            )
            return brief
        except ValidationError as e:
            err_feedback = json.dumps(
                [{"loc": err["loc"], "msg": err["msg"]} for err in e.errors()[:5]],
                ensure_ascii=False,
            )
            log.warning("ai_summarizer.validation_failed", attempt=attempt, err=err_feedback[:200])

    log.error("ai_summarizer.gave_up")
    return None
