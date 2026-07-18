"""编排今日AI / AI大神 两模块：IMAP 取 digest → 解析 → DeepSeek 压缩 → Qwen 选图 → 上传。

对 runner 暴露 build_digest_modules(brief_date_gmt8)：返回 DigestBundle（含 subject/
preheader/editorial/intro + 两个 DigestSection）。任一 digest 缺失时对应 section = None，
由 runner 决定是否告警/中止。
"""
from __future__ import annotations

import io
import re
from dataclasses import dataclass

from nev_shared.logger import get_logger

from ai_brief import config
from ai_brief.digest import condenser, image_judge, uploader
from ai_brief.digest.builder_parser import parse_builder_digest
from ai_brief.digest.events_parser import parse_events_digest
from ai_brief.digest.imap_client import Attachment, DigestEmail, fetch_latest
from ai_brief.schema import DigestSection, DigestStory, Theme

log = get_logger("ai_brief.digest.generate")

_NUM_RE = re.compile(r"(\d+)")


@dataclass
class DigestBundle:
    subject: str
    preheader: str
    editorial: str
    intro_bullets: list[str]
    today_ai: DigestSection | None
    ai_masters: DigestSection | None


def _filename_index(filename: str) -> int | None:
    m = _NUM_RE.search(filename or "")
    return int(m.group(1)) if m else None


def _brand_banner(aspect: float, width: int = 1200) -> tuple[bytes, str]:
    """生成一张干净无文字的品牌渐变横幅（当所有候选图都是文字截图时兜底）。"""
    from PIL import Image

    h = int(width / aspect)
    c0, c1 = (79, 70, 229), (14, 165, 233)  # 品牌靛蓝 → 天蓝
    im = Image.new("RGB", (width, h))
    px = im.load()
    for x in range(width):
        t = x / max(1, width - 1)
        col = tuple(int(c0[i] + (c1[i] - c0[i]) * t) for i in range(3))
        for y in range(h):
            px[x, y] = col
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=85)
    return buf.getvalue(), "image/jpeg"


def _to_banner(data: bytes, aspect: float, max_width: int = 1200) -> tuple[bytes, str]:
    """把（多为长截图的）头图居中裁成 宽:高=aspect 的矮横幅 JPEG。失败原样返回。"""
    try:
        from PIL import Image

        im = Image.open(io.BytesIO(data)).convert("RGB")
        w, h = im.size
        target_h = w / aspect
        if h > target_h:  # 太高 → 裁高（取中间横带）
            top = int((h - target_h) / 2)
            im = im.crop((0, top, w, top + int(target_h)))
        else:             # 已经够矮/够宽 → 裁宽以匹配比例
            target_w = int(h * aspect)
            left = int((w - target_w) / 2)
            im = im.crop((left, 0, left + target_w, h))
        if im.width > max_width:
            im = im.resize((max_width, int(im.height * max_width / im.width)))
        buf = io.BytesIO()
        im.save(buf, "JPEG", quality=85)
        return buf.getvalue(), "image/jpeg"
    except Exception as e:  # noqa: BLE001
        log.warning("ai_digest.banner_failed", err=str(e)[:120])
        return data, "image/png"


def _attachments_by_index(email: DigestEmail) -> dict[int, Attachment]:
    out: dict[int, Attachment] = {}
    for a in email.image_attachments():
        idx = _filename_index(a.filename)
        if idx is not None:
            out[idx] = a
    return out


def _pick_and_upload(
    candidates: list[tuple[int, Attachment, str]],  # (index, attachment, caption)
    *,
    mode: str,
    brief_date: str,
    module: str,
) -> tuple[str | None, str]:
    """Qwen 选图 → 上传 → (public_url, alt)。无候选返回 (None, "")。"""
    if not candidates:
        return None, ""
    images = [(a.data, a.content_type) for _, a, _ in candidates]
    captions = [cap for _, _, cap in candidates]
    pick = image_judge.pick_image(images, captions, mode=mode)

    # today_ai：pick=-1 表示所有候选都是文字截图 → 用干净品牌横幅兜底
    if pick == -1 and mode == "today_ai":
        data, ctype = _brand_banner(config.TODAY_AI_BANNER_ASPECT)
        path = uploader.image_path(brief_date, "today-ai-brand", data, ctype)
        url = uploader.upload_image(data, ctype, path=path)
        log.info("ai_digest.today_ai_brand_fallback", brief_date=brief_date)
        return url, ""

    if pick < 0 or pick >= len(candidates):
        pick = 0
    _, att, caption = candidates[pick]

    data, ctype = att.data, att.content_type
    if mode == "today_ai":  # 今日AI 头图裁成矮横幅（源多为长截图）；AI大神保持完整
        data, ctype = _to_banner(att.data, config.TODAY_AI_BANNER_ASPECT)

    path = uploader.image_path(brief_date, module, data, ctype)
    url = uploader.upload_image(data, ctype, path=path)
    return url, caption


async def _build_today_ai(brief_date: str) -> tuple[DigestSection | None, condenser.TodayAIResult | None]:
    email = fetch_latest(
        config.digest_sender(), config.DIGEST_EVENTS_SUBJECT_PREFIX, brief_date
    )
    if email is None or not email.html:
        log.warning("ai_digest.events_missing", date=brief_date)
        return None, None

    items = parse_events_digest(email.html)
    if not items:
        log.warning("ai_digest.events_empty")
        return None, None

    result = await condenser.condense_today_ai(items)
    if result is None:
        return None, None

    by_idx = _attachments_by_index(email)
    candidates = [(it.index, by_idx[it.index], it.headline) for it in items if it.index in by_idx]
    header_url, alt = _pick_and_upload(
        candidates, mode="today_ai", brief_date=brief_date, module="today-ai"
    )

    section = DigestSection(
        theme=Theme.MODEL_RESEARCH, header_image=header_url,
        header_image_alt=alt, stories=result.stories,
    )
    return section, result


async def _build_ai_masters(brief_date: str) -> DigestSection | None:
    email = fetch_latest(
        config.digest_sender(), config.DIGEST_BUILDER_SUBJECT_PREFIX, brief_date
    )
    if email is None or not email.text:
        log.warning("ai_digest.builder_missing", date=brief_date)
        return None

    items = parse_builder_digest(email.text)
    if not items:
        log.warning("ai_digest.builder_empty")
        return None

    picks = await condenser.select_masters(items)
    if not picks:
        return None
    stories: list[DigestStory] = [story for _, story in picks]

    # 头图只能来自被选中且有图的条目（即被选中的后5条 index 6-10）
    by_idx = _attachments_by_index(email)
    candidates = [
        (it.index, by_idx[it.index], it.headline)
        for it, _ in picks if it.has_image and it.index in by_idx
    ]
    header_url, alt = _pick_and_upload(
        candidates, mode="ai_masters", brief_date=brief_date, module="ai-masters"
    )

    return DigestSection(
        theme=Theme.PRODUCT_TOOLS, header_image=header_url,
        header_image_alt=alt, stories=stories,
    )


async def build_digest_modules(brief_date: str) -> DigestBundle:
    """brief_date = GMT+8 当日 YYYY-MM-DD。"""
    today_ai, meta = await _build_today_ai(brief_date)
    ai_masters = await _build_ai_masters(brief_date)

    return DigestBundle(
        subject=meta.subject if meta else "",
        preheader=meta.preheader if meta else "",
        editorial=meta.editorial if meta else "",
        intro_bullets=meta.intro_bullets if meta else [],
        today_ai=today_ai,
        ai_masters=ai_masters,
    )
