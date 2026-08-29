"""编排今日AI / AI大神：消费 digest envelope → 解析 → DeepSeek 压缩 → Qwen 选图 → 上传。

对 runner 暴露 build_digest_modules(brief_date_gmt8, digests)：返回 DigestBundle（含 subject/
preheader/editorial/intro + 两个 DigestSection）。任一 digest 缺失时对应 section = None，
由 runner 决定是否告警/中止。
"""
from __future__ import annotations

import io
import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from PIL import Image

from nev_shared.logger import get_logger

from ai_brief import config
from ai_brief.digest import condenser, image_judge, uploader
from ai_brief.digest.agent_parser import parse_agent_digest
from ai_brief.digest.builder_parser import parse_builder_digest
from ai_brief.digest.engineering_parser import parse_engineering_digest
from ai_brief.digest.events_parser import parse_events_digest
from ai_brief.digest.imap_client import Attachment
from ai_brief.digest.input import DigestEnvelope, DigestKind
from ai_brief.digest.models import AgentTool
from ai_brief.digest.research_parser import parse_research_digest
from ai_brief.schema import DigestSection, DigestStory, Theme

log = get_logger("ai_brief.digest.generate")

_NUM_RE = re.compile(r"(\d+)")
_EXCLUDED_AGENT_REPOS = frozenset(
    {
        "openai/codex",
        "anthropic/claude",
        "anthropics/claude",
        "google/gemini",
    }
)


def _filter_agent_tools(tools: list[AgentTool]) -> list[AgentTool]:
    """Remove first-party coding/model repositories from the reader tool list."""
    filtered: list[AgentTool] = []
    for tool in tools:
        haystack = f"{tool.name} {tool.url}".lower()
        if any(
            re.search(rf"(?<![a-z0-9]){re.escape(repo)}(?![a-z0-9_-])", haystack)
            for repo in _EXCLUDED_AGENT_REPOS
        ):
            continue
        filtered.append(tool)
    return filtered


@dataclass
class DigestBundle:
    subject: str
    preheader: str
    editorial: str
    intro_bullets: list[str]
    today_ai: DigestSection | None
    ai_masters: DigestSection | None
    ai_research: DigestSection | None = None
    ai_engineering: DigestSection | None = None
    agent_tools: DigestSection | None = None
    deepseek_complete: bool = True
    qwen_complete: bool = True


def _filename_index(filename: str) -> int | None:
    m = _NUM_RE.search(filename or "")
    return int(m.group(1)) if m else None


def _richness(im: Image.Image) -> float:
    """一横带里「非近白像素」的占比：正文页多为白底黑字→低；hero 图/照片→高。"""
    g = im.convert("L")
    if g.width > 200:
        g = g.resize((200, max(1, int(200 * g.height / g.width))))
    hist: list[int] = g.histogram()
    total = sum(hist) or 1
    white = sum(hist[235:])  # 近白
    return 1.0 - white / total


def _find_hero_band(data: bytes, aspect: float, max_width: int = 1200) -> tuple[bytes, str]:
    """从（多为整页长截图的）图里找出最像配图的横带 → 裁成 宽:高=aspect 的矮横幅。

    正文是白底黑字、非白占比低；hero 图/照片非白占比高。在顶部 ~2/3 滑窗取「非白占比最高」
    的一带（避开深处正文），既定位了 hero 又天然避开大段文字。失败回退居中裁剪。
    """
    try:
        from PIL import Image

        im = Image.open(io.BytesIO(data)).convert("RGB")
        w, h = im.size
        band_h = max(1, int(w / aspect))
        if h <= int(band_h * 1.25):  # 本就不高 → 居中 cover 裁
            top = max(0, (h - band_h) // 2)
            band = im.crop((0, top, w, min(h, top + band_h)))
        else:
            limit = int(h * 0.68)  # hero 通常在顶部 2/3
            step = max(1, band_h // 3)
            best_y, best = 0, -1.0
            y = 0
            while y + band_h <= min(h, limit + band_h):
                s = _richness(im.crop((0, y, w, y + band_h)))
                if s > best:
                    best, best_y = s, y
                y += step
            band = im.crop((0, best_y, w, best_y + band_h))
        if band.width > max_width:
            band = band.resize((max_width, int(band.height * max_width / band.width)))
        buf = io.BytesIO()
        band.save(buf, "JPEG", quality=85)
        return buf.getvalue(), "image/jpeg"
    except Exception as e:  # noqa: BLE001
        log.warning("ai_digest.hero_band_failed", err=str(e)[:120])
        return data, "image/png"


def _prep_header(data: bytes, content_type: str, max_width: int | None = None) -> tuple[bytes, str]:
    """头图上传前缩到最大宽度（研究/工程图可能很大）。失败原样返回。"""
    max_width = max_width or config.HEADER_IMAGE_MAX_WIDTH
    try:
        from PIL import Image

        im = Image.open(io.BytesIO(data)).convert("RGB")
        if im.width <= max_width:
            return data, content_type
        h = int(im.height * max_width / im.width)
        im = im.resize((max_width, h))
        buf = io.BytesIO()
        im.save(buf, "JPEG", quality=85)
        return buf.getvalue(), "image/jpeg"
    except Exception as e:  # noqa: BLE001
        log.warning("ai_digest.prep_header_failed", err=str(e)[:120])
        return data, content_type


def _image_attachments(digest: DigestEnvelope) -> list[Attachment]:
    return [
        attachment
        for attachment in digest.attachments
        if attachment.content_type.startswith("image/")
    ]


def _is_usable_header_image(data: bytes, content_type: str) -> bool:
    """Reject broken, transparent, or visually blank attachments before upload."""
    if not data or not content_type.startswith("image/"):
        return False
    try:
        from PIL import Image, ImageStat

        image = Image.open(io.BytesIO(data)).convert("RGBA")
        if image.getchannel("A").getextrema()[1] == 0:
            return False
        image.thumbnail((200, 200))
        rgb = image.convert("RGB")
        stats = ImageStat.Stat(rgb)
        return not (min(stats.mean) >= 245 and max(stats.var) < 4)
    except Exception as e:  # noqa: BLE001
        log.warning("ai_digest.header_image_invalid", err=str(e)[:120])
        return False


def _attachments_by_index(digest: DigestEnvelope) -> dict[int, Attachment]:
    out: dict[int, Attachment] = {}
    for a in _image_attachments(digest):
        idx = _filename_index(a.filename)
        if idx is not None:
            out[idx] = a
    return out


def _pick_and_upload(
    candidates: list[tuple[int, bytes, str, str]],  # (index, image_bytes, content_type, caption)
    *,
    mode: str,
    brief_date: str,
    module: str,
) -> tuple[str | None, str, bool]:
    """Qwen 从已备好的候选图里选 1 张 → 上传 → (public_url, alt)。图已按模块处理好，直接传。"""
    candidates = [
        candidate
        for candidate in candidates
        if _is_usable_header_image(candidate[1], candidate[2])
    ]
    if not candidates:
        return None, "", False
    images = [(data, ctype) for _, data, ctype, _ in candidates]
    captions = [cap for _, _, _, cap in candidates]
    outcome = image_judge.pick_image(images, captions, mode=mode)
    pick = outcome.index if 0 <= outcome.index < len(candidates) else 0
    _, data, ctype, caption = candidates[pick]
    path = uploader.image_path(brief_date, module, data, ctype)
    url = uploader.upload_image(data, ctype, path=path)
    return url, caption, outcome.complete


async def _build_today_ai(
    brief_date: str,
    digest: DigestEnvelope | None,
) -> tuple[DigestSection | None, condenser.TodayAIResult | None, bool, bool]:
    if digest is None or not digest.html:
        log.warning("ai_digest.events_missing", date=brief_date)
        return None, None, True, True

    items = parse_events_digest(digest.html)
    if not items:
        log.warning("ai_digest.events_empty")
        return None, None, True, True
    items = items[: config.TODAY_AI_TOP_N]  # 上游一次给 8 条，只取 TOP-N

    outcome = await condenser.condense_today_ai(items)
    if outcome is None:
        return None, None, False, True
    result = outcome.value

    # 源图多是整页长截图 → 先从每张里裁出最像配图的 hero 横幅带，再让 Qwen 在这些干净带里选
    by_idx = _attachments_by_index(digest)
    candidates: list[tuple[int, bytes, str, str]] = []
    for it in items:
        att = by_idx.get(it.index)
        if att is None or "svg" in (att.content_type or "").lower():
            continue  # SVG 无法 PIL 裁带 → 跳过，避免污染候选
        band, ctype = _find_hero_band(att.data, config.TODAY_AI_BANNER_ASPECT)
        candidates.append((it.index, band, ctype, it.headline))
    header_url, alt, qwen_complete = _pick_and_upload(
        candidates, mode="today_ai", brief_date=brief_date, module="today-ai"
    )

    section = DigestSection(
        theme=Theme.MODEL_RESEARCH, header_image=header_url,
        header_image_alt=alt, stories=result.stories,
    )
    return section, result, outcome.complete, qwen_complete


async def _build_ai_masters(
    brief_date: str,
    digest: DigestEnvelope | None,
) -> tuple[DigestSection | None, bool, bool]:
    if digest is None or not digest.text:
        log.warning("ai_digest.builder_missing", date=brief_date)
        return None, True, True

    items = parse_builder_digest(digest.text)
    if not items:
        log.warning("ai_digest.builder_empty")
        return None, True, True

    outcome = await condenser.select_masters(items)
    if outcome is None:
        return None, False, True
    picks = outcome.value
    stories: list[DigestStory] = [story for _, story in picks]

    # 头图只能来自被选中且有图的条目（即被选中的后5条 index 6-10）；推文截图保持完整，不裁 hero 带
    by_idx = _attachments_by_index(digest)
    candidates: list[tuple[int, bytes, str, str]] = [
        (it.index, by_idx[it.index].data, by_idx[it.index].content_type, it.headline)
        for it, _ in picks if it.has_image and it.index in by_idx
    ]
    header_url, alt, qwen_complete = _pick_and_upload(
        candidates, mode="ai_masters", brief_date=brief_date, module="ai-masters"
    )

    return (
        DigestSection(
            theme=Theme.PRODUCT_TOOLS,
            header_image=header_url,
            header_image_alt=alt,
            stories=stories,
        ),
        outcome.complete,
        qwen_complete,
    )


# ── 工具学习板块 ───────────────────────────────────────────────────────

async def _build_research(
    brief_date: str,
    digest: DigestEnvelope | None,
) -> tuple[DigestSection | None, bool, bool]:
    """AI研究：Qwen 从附件里选最清晰的图 → 用它对应的那篇论文做主题+内容+链接。"""
    if digest is None or not digest.html:
        log.warning("ai_digest.research_missing", date=brief_date)
        return None, True, True
    papers = parse_research_digest(digest.html)
    if not papers:
        log.warning("ai_digest.research_empty")
        return None, True, True

    imgs = _image_attachments(digest)
    # 每张图 → 缩放后的候选；caption 用图名，选中后按图名匹配回论文
    candidates: list[tuple[int, bytes, str, str]] = []
    for i, att in enumerate(imgs):
        data, ctype = _prep_header(att.data, att.content_type)
        candidates.append((i, data, ctype, att.filename))

    chosen_paper = papers[0]
    header_url, alt = None, ""
    if candidates:
        images = [(d, c) for _, d, c, _ in candidates]
        caps = [cap for _, _, _, cap in candidates]
        image_outcome = image_judge.pick_image(images, caps, mode="research")
        pick = image_outcome.index if 0 <= image_outcome.index < len(candidates) else 0
        picked_att = imgs[pick]
        # 图名匹配回论文（arxiv.png ↔ [Arxiv]）；匹配不到就用第一篇
        for p in papers:
            if p.matches_filename(picked_att.filename):
                chosen_paper = p
                break
        _, data, ctype, _ = candidates[pick]
        path = uploader.image_path(brief_date, "ai-research", data, ctype)
        header_url = uploader.upload_image(data, ctype, path=path)
        alt = chosen_paper.title
        qwen_complete = image_outcome.complete
    else:
        qwen_complete = False

    outcome = await condenser.condense_research(chosen_paper)
    if outcome is None:
        return None, False, qwen_complete
    return (
        DigestSection(
            theme=Theme.AI_RESEARCH,
            header_image=header_url,
            header_image_alt=alt,
            cta_label="阅读论文",
            stories=[outcome.value],
        ),
        outcome.complete,
        qwen_complete,
    )


async def _build_engineering(
    brief_date: str,
    digest: DigestEnvelope | None,
) -> DigestSection | None:
    """AI工程：附件图做头图；课程要点=主题；核心要点=内容（无链接，无需 LLM）。"""
    if digest is None or not digest.html:
        log.warning("ai_digest.engineering_missing", date=brief_date)
        return None
    lecture = parse_engineering_digest(digest.html)
    if lecture is None or not lecture.core_points:
        log.warning("ai_digest.engineering_empty")
        return None

    subtitle, stories = condenser.build_engineering_stories(lecture)
    if not stories:
        return None

    header_url, alt = None, ""
    imgs = _image_attachments(digest)
    if imgs:
        data, ctype = _prep_header(imgs[0].data, imgs[0].content_type)
        path = uploader.image_path(brief_date, "ai-engineering", data, ctype)
        header_url = uploader.upload_image(data, ctype, path=path)
        alt = subtitle

    return DigestSection(
        theme=Theme.AI_ENGINEERING, header_image=header_url, header_image_alt=alt,
        subtitle=subtitle, cta_label="", stories=stories,
    )


async def _build_agent(
    brief_date: str,
    digest: DigestEnvelope | None,
) -> tuple[DigestSection | None, bool]:
    """Agent工具：3 个工具选 2 个（DeepSeek 判影响度）；无头图（源无附件）。"""
    if digest is None or not digest.html:
        log.warning("ai_digest.agent_missing", date=brief_date)
        return None, True
    tools = _filter_agent_tools(parse_agent_digest(digest.html))
    if not tools:
        log.warning("ai_digest.agent_empty")
        return None, True

    outcome = await condenser.select_agent_tools(tools)
    if outcome is None:
        return None, False
    return (
        DigestSection(
            theme=Theme.AGENT_TOOLS,
            header_image=None,
            header_image_alt="",
            cta_label="查看仓库",
            stories=outcome.value,
        ),
        outcome.complete,
    )


async def build_digest_modules(
    brief_date: date,
    digests: Mapping[DigestKind, DigestEnvelope | None],
) -> DigestBundle:
    """Build modules for a GMT+8 brief date from transport-neutral inputs."""
    date_str = brief_date.isoformat()
    today_ai, meta, today_deepseek, today_qwen = await _build_today_ai(
        date_str, digests.get("events")
    )
    ai_masters, masters_deepseek, masters_qwen = await _build_ai_masters(
        date_str, digests.get("builder")
    )
    ai_research, research_deepseek, research_qwen = await _build_research(
        date_str, digests.get("research")
    )
    ai_engineering = await _build_engineering(date_str, digests.get("engineering"))
    agent_tools, agent_deepseek = await _build_agent(date_str, digests.get("agent"))

    return DigestBundle(
        subject=meta.subject if meta else "",
        preheader=meta.preheader if meta else "",
        editorial=meta.editorial if meta else "",
        intro_bullets=meta.intro_bullets if meta else [],
        today_ai=today_ai,
        ai_masters=ai_masters,
        ai_research=ai_research,
        ai_engineering=ai_engineering,
        agent_tools=agent_tools,
        deepseek_complete=all(
            (today_deepseek, masters_deepseek, research_deepseek, agent_deepseek)
        ),
        qwen_complete=all((today_qwen, masters_qwen, research_qwen)),
    )
