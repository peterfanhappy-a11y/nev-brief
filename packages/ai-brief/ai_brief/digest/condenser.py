"""DeepSeek 文本处理 —— 压缩 digest 正文 + 今日AI 生成 subject/导语 + AI大神 选5条。

标题（headline）按用户要求「直接应用」digest 原标题，不改写；LLM 只压缩正文、
做选择、写导语。url/label 由代码从 digest item 注入（防幻觉）。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from nev_pipeline.deepseek_client import extract_json_with_retry
from nev_shared.logger import get_logger

from ai_brief import config
from ai_brief.digest.models import (
    AgentTool,
    BuilderItem,
    EngineeringLecture,
    EventItem,
    ResearchPaper,
)
from ai_brief.schema import DigestStory

log = get_logger("ai_brief.condenser")

@dataclass(frozen=True)
class ModelOutcome[T]:
    """A value plus whether it came entirely from a valid model response."""

    value: T
    complete: bool

_SENT_END = "。！？!?…”）)"


def _clip_sentence(text: str, limit: int) -> str:
    """把摘要收在 limit 字内，且尽量成句：超限时截到 limit 内最后一个句末标点，
    避免从句子中间硬切出半截。找不到合适标点才退回硬截。"""
    t = (text or "").strip()
    if len(t) <= limit:
        return t
    window = t[:limit]
    cut = max(window.rfind(ch) for ch in _SENT_END)
    if cut >= limit * 0.45:  # 窗口内有靠后的句末标点 → 收在那里，成完整句
        return window[: cut + 1]
    return window.rstrip("，、；：,;: ") + "…"


@dataclass
class TodayAIResult:
    subject: str
    preheader: str
    editorial: str
    intro_bullets: list[str]
    stories: list[DigestStory]


_TODAY_AI_SYSTEM = """你是 AIVIZENS 的 AI 行业主编，为中文读者写每日 AI 简报，文风参考 The Rundown AI：专业、精炼、有洞见。
给你今天 3 条最重要的 AI 新闻（已带标题与长正文）。请：
1) 把每条正文压缩成 ≤150 字的精炼中文摘要，保留关键数字、结论与「为什么重要」，去掉冗余。公司/产品/模型名保留英文原名（Claude、GPT-5、OpenAI）。
2) 基于这 3 条生成邮件的 subject / preheader / editorial / intro_bullets。

只输出严格 JSON：
{
  "subject": "邮件主题：3条里最重磅那条改写成最抓眼球的中文标题，≤22字",
  "preheader": "以「另外：」开头 + 第二重磅新闻吸睛短标题，≤28字",
  "editorial": "编辑导语：2-3句串起今天最重要的AI动向，专业有洞见，≤120字，别用「今天」「以下」套话开头",
  "intro_bullets": ["每条一句话导读，emoji开头，≤20字（共3条，按给定顺序）"],
  "summaries": [ {"index": 1, "summary": "≤150字压缩摘要"} ]
}
summaries 必须含全部 3 条、index 用给定编号。只输出 JSON。"""


def _today_ai_prompt(items: list[EventItem]) -> str:
    parts = ["## 今天 3 条 AI 新闻"]
    for it in items:
        parts.append(
            f"[index={it.index}] 分类={it.label}\n"
            f"  标题：{it.headline}\n  正文：{it.body}"
        )
    return "\n".join(parts)


async def condense_today_ai(items: list[EventItem]) -> ModelOutcome[TodayAIResult] | None:
    if not items:
        return None
    raw = await extract_json_with_retry(
        _TODAY_AI_SYSTEM, _today_ai_prompt(items),
        model=config.get_model(), max_tokens=2000, temperature=0.4,
    )
    if raw is None:
        log.error("ai_condenser.today_ai_failed")
        return None

    sum_by_idx: dict[int, str] = {}
    summaries = raw.get("summaries")
    if isinstance(summaries, list):
        for summary in summaries:
            if not isinstance(summary, dict) or summary.get("index") is None:
                continue
            try:
                index = int(summary["index"])
            except (TypeError, ValueError):
                continue
            sum_by_idx[index] = str(summary.get("summary", "")).strip()
    stories: list[DigestStory] = []
    for it in items:
        summary = _clip_sentence(
            sum_by_idx.get(it.index, "") or it.body, config.TODAY_AI_SUMMARY_CHARS
        )
        stories.append(
            DigestStory(headline=it.headline[:80], summary=summary, url=it.url, label=it.label)
        )

    raw_intro = raw.get("intro_bullets")
    intro = (
        [str(b)[:40] for b in raw_intro if str(b).strip()]
        if isinstance(raw_intro, list)
        else []
    )
    subject = str(raw.get("subject", "")).strip()
    preheader = str(raw.get("preheader", "")).strip()
    editorial = str(raw.get("editorial", "")).strip()
    complete = (
        all(sum_by_idx.get(item.index) for item in items)
        and bool(subject)
        and bool(preheader)
        and bool(editorial)
        and bool(intro)
    )
    if not intro:
        intro = [story.headline for story in stories]

    return ModelOutcome(
        value=TodayAIResult(
            subject=subject[:44] or stories[0].headline,
            preheader=preheader[:60],
            editorial=editorial[:220],
            intro_bullets=intro[:4],
            stories=stories,
        ),
        complete=complete,
    )


_MASTERS_SYSTEM = """你是 AIVIZENS 的 AI 主编。给你 AI 领域 10 位从业者/大神的最新发声（前5条标 A 组、后5条标 B 组）。
每条给了一段较长的标题描述 + 正文。请：
1) 从 A 组（前5条）选 2 条、从 B 组（后5条）选 3 条，共 5 条。标准：对普通人的工作与生活影响度最大、最有启发或最具信号价值。
2) 对选中 5 条，各产出：
   - person：发声者的姓名/职务/来源（如 "Box CEO Aaron Levie"、"OpenAI Sam Altman"），从原文提取，英文原名保留；
   - headline：一句精炼中文标题，≤24字，抓住这条最核心的观点/事件；
   - summary：把这条提炼成【一个完整、成句、可独立读懂的核心观点】，≤120字。要点集中在"他说了什么、依据/影响是什么"，
     必须是完整通顺的句子、以句号收尾，宁可写短也不要写成半截或戛然而止；不要罗列多个要点堆到超字数。公司/产品/人名保留英文原名。

只输出严格 JSON：
{
  "picks": [
    {"index": 2, "person": "Box CEO Aaron Levie", "headline": "≤24字标题", "summary": "≤120字摘要"},
    ...共5条，其中恰好2条来自A组、3条来自B组
  ]
}
index 用给定编号。只输出 JSON。"""


def _masters_prompt(items: list[BuilderItem]) -> str:
    parts = []
    a = [it for it in items if it.is_top5]
    b = [it for it in items if not it.is_top5]
    parts.append("## A 组（前5条，选2条）")
    for it in a:
        parts.append(f"[index={it.index}] {it.person}：{it.headline}\n  {it.body}")
    parts.append("\n## B 组（后5条，选3条）")
    for it in b:
        parts.append(f"[index={it.index}] {it.person}：{it.headline}\n  {it.body}")
    return "\n".join(parts)


def _rebalance(picks: list[int], items_by_idx: dict[int, BuilderItem]) -> list[int]:
    """确保恰好 2 条 A 组 + 3 条 B 组；模型选错就按原顺序补齐。"""
    a_all = [i for i in items_by_idx if items_by_idx[i].is_top5]
    b_all = [i for i in items_by_idx if not items_by_idx[i].is_top5]
    a_pick = [i for i in picks if i in a_all][: config.AI_MASTERS_PICK_TOP5]
    b_pick = [i for i in picks if i in b_all][: config.AI_MASTERS_PICK_FIRE5]
    for i in a_all:
        if len(a_pick) >= config.AI_MASTERS_PICK_TOP5:
            break
        if i not in a_pick:
            a_pick.append(i)
    for i in b_all:
        if len(b_pick) >= config.AI_MASTERS_PICK_FIRE5:
            break
        if i not in b_pick:
            b_pick.append(i)
    return a_pick + b_pick


async def select_masters(
    items: list[BuilderItem],
) -> ModelOutcome[list[tuple[BuilderItem, DigestStory]]] | None:
    """返回选中的 (item, story) 列表（story.summary 已压缩）。story 顺序 = A组2条 + B组3条。"""
    if not items:
        return None
    by_idx = {it.index: it for it in items}
    raw = await extract_json_with_retry(
        _MASTERS_SYSTEM, _masters_prompt(items),
        model=config.get_model(), max_tokens=2000, temperature=0.4,
    )
    if raw is None:
        log.error("ai_condenser.masters_failed")
        return None

    picks_by_idx: dict[int, dict[str, Any]] = {}
    raw_picks = raw.get("picks")
    if isinstance(raw_picks, list):
        for pick in raw_picks:
            if not isinstance(pick, dict) or pick.get("index") is None:
                continue
            try:
                index = int(pick["index"])
            except (TypeError, ValueError):
                continue
            if index in by_idx and index not in picks_by_idx:
                picks_by_idx[index] = pick
    order = _rebalance(list(picks_by_idx.keys()), by_idx)
    selected_a = [index for index in picks_by_idx if by_idx[index].is_top5]
    selected_b = [index for index in picks_by_idx if not by_idx[index].is_top5]
    complete = (
        len(picks_by_idx) == 5
        and len(selected_a) == config.AI_MASTERS_PICK_TOP5
        and len(selected_b) == config.AI_MASTERS_PICK_FIRE5
        and all(
            str(pick.get(field, "")).strip()
            for pick in picks_by_idx.values()
            for field in ("person", "headline", "summary")
        )
    )

    out: list[tuple[BuilderItem, DigestStory]] = []
    for idx in order:
        it = by_idx[idx]
        p = picks_by_idx.get(idx, {})
        summary = _clip_sentence(
            str(p.get("summary", "")).strip() or it.body, config.AI_MASTERS_SUMMARY_CHARS
        )
        # 上游新格式把人名内嵌进长标题、不再用 [人名] 括号；故 person/headline 由 LLM 提取，
        # 括号残留（旧格式）时回退到 parser 的 it.person / it.headline。
        person = str(p.get("person", "")).strip() or it.person
        headline = str(p.get("headline", "")).strip()[:80] or it.headline[:80]
        out.append((
            it,
            DigestStory(headline=headline, summary=summary, url=it.url, label=person),
        ))
    return ModelOutcome(value=out, complete=complete)


# ── AI研究：把选中论文的 Core Takeaways 压成一段可读内容 ────────────────

_RESEARCH_SYSTEM = """你是 AIVIZENS 的 AI 研究主编。给你一篇论文的中文标题与它的 Core Takeaways（核心贡献/方法/影响）。
请把它提炼成一段【面向从业者、完整成句、可独立读懂】的中文内容，说明这项研究做了什么、怎么做的、为什么重要。
要求：控制在 180 字以内（务必给结尾句留出空间），通顺连贯、必须以句号收尾、不得写成半截；保留关键结论与数字；公司/产品/模型名保留英文原名。

只输出严格 JSON：{"summary": "≤180字内容"}。只输出 JSON。"""


async def condense_research(paper: ResearchPaper) -> ModelOutcome[DigestStory] | None:
    """把一篇论文压成 AI研究 模块的单条 story。失败回退用原始 takeaways 拼接。"""
    if paper is None:
        return None
    joined = "\n".join(f"{i+1}) {t}" for i, t in enumerate(paper.takeaways))
    prompt = f"标题：{paper.title}\nCore Takeaways：\n{joined}"
    raw = await extract_json_with_retry(
        _RESEARCH_SYSTEM, prompt, model=config.get_model(), max_tokens=1200, temperature=0.4,
    )
    summary = ""
    if raw is not None:
        summary = str(raw.get("summary", "")).strip()
    if not summary:
        summary = " ".join(paper.takeaways)
    summary = _clip_sentence(summary, config.AI_RESEARCH_SUMMARY_CHARS)
    label = f"[{paper.source_tag}]" if paper.source_tag else ""
    return ModelOutcome(
        value=DigestStory(
            headline=paper.title[:80], summary=summary, url=paper.url, label=label
        ),
        complete=raw is not None and bool(str(raw.get("summary", "")).strip()),
    )


# ── AI工程：课程要点(主题) + 核心要点(内容)，无需 LLM，直接映射 + 收句 ──

_ENGINEERING_FIELD_ALIASES = {"行动": "启示"}


def _engineering_story_parts(subtitle: str, body: str) -> tuple[str, str]:
    """Normalize source labels into ``字段：短总结`` plus clean body text."""
    clean_body = (body or "").lstrip("：: \t\r\n")
    label, separator, takeaway = (subtitle or "").strip().partition("：")
    if not separator:
        label, separator, takeaway = (subtitle or "").strip().partition(":")
    label = _ENGINEERING_FIELD_ALIASES.get(label.strip(), label.strip())
    takeaway = takeaway.strip()
    if not takeaway:
        takeaway = _clip_sentence(clean_body, 30).rstrip(_SENT_END).strip()
    headline = f"{label}：{takeaway}" if takeaway else f"{label}："
    return headline[:80], clean_body


def build_engineering_stories(lecture: EngineeringLecture) -> tuple[str, list[DigestStory]]:
    """返回 (subtitle=课程要点, stories=核心要点各一条)。无链接。"""
    stories: list[DigestStory] = []
    for cp in lecture.core_points:
        headline, body = _engineering_story_parts(cp.subtitle, cp.body)
        stories.append(
            DigestStory(
                headline=headline,
                summary=_clip_sentence(body, config.AI_ENGINEERING_POINT_CHARS),
                url="",
                label="",
            )
        )
    return lecture.key_point, stories


# ── Agent工具：过滤后选 3 + 每个工具压一段介绍 ─────────────────────────

_AGENT_SYSTEM = """你是 AIVIZENS 的 AI 工具主编。给你 GitHub Trending 上 3 个 AI/Agent 开源工具，各带名称与「3 要点总结」。
请：
1) 从给定工具里选 3 个——标准：对读者的实际工作/学习帮助最大、最值得动手试用。
2) 对选中的每个工具，把它的 3 要点提炼成【一段完整、成句、可独立读懂】的中文介绍：这个工具是什么、解决什么问题、亮点在哪，尽量写满信息量。
   控制在 140 字以内（务必给结尾句留空间），通顺连贯、必须以句号收尾、不得写半截。产品/公司/技术名保留英文原名。

只输出严格 JSON：
{"picks": [ {"rank": 1, "summary": "≤150字介绍"}, {"rank": 2, "summary": "≤150字介绍"}, {"rank": 3, "summary": "≤150字介绍"} ]}
rank 必须来自给定工具，恰好 3 个且每个 rank 只能出现一次。只输出 JSON。"""


def _agent_prompt(tools: list[AgentTool]) -> str:
    parts = []
    for t in tools:
        pts = "\n".join(f"  - {p}" for p in t.points)
        parts.append(f"[rank={t.rank}] {t.name}（本周 {t.stars} stars）\n{pts}")
    return "\n\n".join(parts)


async def select_agent_tools(
    tools: list[AgentTool],
) -> ModelOutcome[list[DigestStory]] | None:
    """从过滤后的工具里选 3 个，返回 story 列表（headline=名称、summary=压缩介绍、url=仓库）。"""
    if not tools:
        return None
    by_rank = {t.rank: t for t in tools}
    raw = await extract_json_with_retry(
        _AGENT_SYSTEM,
        _agent_prompt(tools),
        model=config.get_model(),
        max_tokens=1500,
        temperature=0.4,
    )
    picks: list[tuple[int, str]] = []
    if raw is not None and isinstance(raw.get("picks"), list):
        for p in raw["picks"]:
            if not isinstance(p, dict) or p.get("rank") is None:
                continue
            try:
                rank = int(p["rank"])
            except (TypeError, ValueError):
                continue
            picks.append((rank, str(p.get("summary", "")).strip()))
    # 回退/收敛：不足 3 个就按榜单顺序补齐
    chosen: list[int] = [r for r, _ in picks if r in by_rank][: config.AGENT_TOOLS_PICK]
    sum_by_rank = dict(picks)
    for t in tools:
        if len(chosen) >= config.AGENT_TOOLS_PICK:
            break
        if t.rank not in chosen:
            chosen.append(t.rank)

    out: list[DigestStory] = []
    for r in chosen:
        t = by_rank[r]
        summary = _clip_sentence(
            sum_by_rank.get(r, "") or " ".join(t.points),
            config.AGENT_TOOL_SUMMARY_CHARS,
        )
        label = f"⭐ {t.stars} stars/周" if t.stars else ""
        out.append(DigestStory(headline=t.name[:80], summary=summary, url=t.url, label=label))
    valid_model_picks = {
        rank: summary
        for rank, summary in picks
        if rank in by_rank and summary
    }
    complete = (
        len(valid_model_picks) == config.AGENT_TOOLS_PICK
    )
    return ModelOutcome(value=out, complete=complete)
