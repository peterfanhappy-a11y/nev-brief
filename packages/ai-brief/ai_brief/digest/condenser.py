"""DeepSeek 文本处理 —— 压缩 digest 正文 + 今日AI 生成 subject/导语 + AI大神 选5条。

标题（headline）按用户要求「直接应用」digest 原标题，不改写；LLM 只压缩正文、
做选择、写导语。url/label 由代码从 digest item 注入（防幻觉）。
"""
from __future__ import annotations

from dataclasses import dataclass

from nev_pipeline.deepseek_client import extract_json_with_retry
from nev_shared.logger import get_logger

from ai_brief import config
from ai_brief.digest.models import BuilderItem, EventItem
from ai_brief.schema import DigestStory

log = get_logger("ai_brief.condenser")

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


async def condense_today_ai(items: list[EventItem]) -> TodayAIResult | None:
    if not items:
        return None
    raw = await extract_json_with_retry(
        _TODAY_AI_SYSTEM, _today_ai_prompt(items),
        model=config.get_model(), max_tokens=2000, temperature=0.4,
    )
    if raw is None:
        log.error("ai_condenser.today_ai_failed")
        return None

    sum_by_idx = {
        int(s.get("index")): str(s.get("summary", "")).strip()
        for s in raw.get("summaries", []) if s.get("index") is not None
    }
    stories: list[DigestStory] = []
    for it in items:
        summary = _clip_sentence(
            sum_by_idx.get(it.index, "") or it.body, config.TODAY_AI_SUMMARY_CHARS
        )
        stories.append(
            DigestStory(headline=it.headline[:80], summary=summary, url=it.url, label=it.label)
        )

    intro = [str(b)[:40] for b in (raw.get("intro_bullets") or []) if str(b).strip()]
    if not intro:
        intro = [s.headline for s in stories]

    return TodayAIResult(
        subject=str(raw.get("subject", "")).strip()[:44] or stories[0].headline,
        preheader=str(raw.get("preheader", "")).strip()[:60],
        editorial=str(raw.get("editorial", "")).strip()[:220],
        intro_bullets=intro[:4],
        stories=stories,
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


async def select_masters(items: list[BuilderItem]) -> list[tuple[BuilderItem, DigestStory]] | None:
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

    picks_by_idx = {
        int(p.get("index")): p
        for p in raw.get("picks", []) if p.get("index") is not None
    }
    order = _rebalance(list(picks_by_idx.keys()), by_idx)

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
    return out
