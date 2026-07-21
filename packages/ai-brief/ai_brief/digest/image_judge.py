"""Qwen 选图 —— deepseek-chat 是纯文本，判不了图，故这一步用 Qwen 多模态模型。
模型由 QWEN_VL_MODEL 配置（默认 qwen3.7-plus）；须为支持视觉输入的模型，否则回退第0张。

DashScope OpenAI 兼容端点。给候选图 + 各自标题，让模型按标准挑 1 张：
  今日AI  → 文字最少、最能代表主题的（做模块头图）
  AI大神  → 内容最饱满的（信息量大、画面完整）
返回被选中图的下标（0-based）。失败 / 无候选 → 回退到第 0 张。
"""
from __future__ import annotations

import base64
import io
import re

import httpx
from nev_shared.logger import get_logger

from ai_brief import config

log = get_logger("ai_brief.image_judge")

_MAX_EDGE = 768  # 判图不需要原图（2-3MB 截图），缩到长边 768 省带宽/时延


def _downscale(data: bytes, content_type: str) -> tuple[bytes, str]:
    """缩到长边 ≤768 的 JPEG，显著减小请求体。失败则原样返回。"""
    try:
        from PIL import Image

        im = Image.open(io.BytesIO(data))
        im = im.convert("RGB")
        im.thumbnail((_MAX_EDGE, _MAX_EDGE))
        buf = io.BytesIO()
        im.save(buf, "JPEG", quality=80)
        return buf.getvalue(), "image/jpeg"
    except Exception as e:  # noqa: BLE001
        log.warning("ai_image_judge.downscale_failed", err=str(e)[:120])
        return data, content_type

_CRITERIA = {
    "today_ai": (
        "这些都是从新闻里裁出的横幅候选图。选出【文字最少、画面最干净、最像一张配图/照片/插画】的一张，"
        "尽量避开大段正文文字或满是 UI 文本的那张；在此前提下再挑最能代表新闻主题的。"
    ),
    "ai_masters": "选出内容最饱满、信息量最大、画面最完整的一张（优先展示完整推文/观点的截图）。",
    "research": (
        "这些是论文里的配图。选出【最清晰、最像一张干净的示意图/架构图/流程图】的一张，"
        "避开文字密集、像软件界面截图或满屏小字的那张；越清爽、越能一眼看懂结构的越好。"
    ),
}


def _b64(data: bytes, content_type: str) -> str:
    mime = content_type if content_type.startswith("image/") else "image/png"
    return f"data:{mime};base64,{base64.b64encode(data).decode()}"


def pick_image(
    images: list[tuple[bytes, str]],
    captions: list[str],
    *,
    mode: str,
    api_key: str | None = None,
    base_url: str | None = None,
    model: str | None = None,
    timeout: float = 180.0,
) -> int:
    """从 images 里挑 1 张，返回下标。images[i]=(bytes, content_type)。"""
    if not images:
        return -1
    if len(images) == 1:
        return 0

    api_key = api_key or config.qwen_api_key()
    if not api_key:
        log.warning("ai_image_judge.no_key_fallback_0")
        return 0

    criterion = _CRITERIA.get(mode, _CRITERIA["today_ai"])
    content: list[dict] = [{
        "type": "text",
        "text": (
            f"下面是 {len(images)} 张候选新闻配图，按顺序编号 0 到 {len(images)-1}。\n"
            "请先逐张判断每张是不是网页/文章/App 界面截图或含大段文字的图，再据此挑选。\n"
            f"{criterion}\n"
            "分析完后，务必在最后另起一行、严格按此格式输出结论：选择=N（N 为被选图片编号，只填一个数字）。"
        ),
    }]
    for i, (data, ctype) in enumerate(images):
        cap = captions[i] if i < len(captions) else ""
        sdata, sctype = _downscale(data, ctype)
        content.append({"type": "text", "text": f"[图{i}] {cap}"})
        content.append({"type": "image_url", "image_url": {"url": _b64(sdata, sctype)}})

    # 保留思维链：关掉后模型选图明显变差（会挑到文字截图）。日更批处理不在意 ~1 分钟延迟。
    payload = {
        "model": model or config.qwen_vl_model(),
        "messages": [{"role": "user", "content": content}],
        "temperature": 0.0,
        "max_tokens": 3000,  # 推理模型分析3图较长，留足空间避免「选择=N」标记被截断
    }
    try:
        resp = httpx.post(
            f"{(base_url or config.qwen_base_url()).rstrip('/')}/chat/completions",
            headers={"Authorization": f"Bearer {api_key}"},
            json=payload,
            timeout=timeout,
            trust_env=False,  # 不走 Clash/SOCKS 代理
        )
        resp.raise_for_status()
        msg = resp.json()["choices"][0]["message"]
        text = msg.get("content") or ""
        reasoning = msg.get("reasoning_content") or ""
    except Exception as e:  # noqa: BLE001
        log.warning("ai_image_judge.failed_fallback_0", err=str(e)[:200])
        return 0

    idx = _pick_index(text, reasoning, len(images))
    log.info("ai_image_judge.picked", mode=mode, idx=idx, raw=str(text)[-40:])
    return idx


_MARK_RE = re.compile(r"选择\s*[=＝:：]\s*(-?\d+)")


def _pick_index(content: str, reasoning: str, n: int) -> int:
    """先找最后一个「选择=N」标记（N 可为 -1 表示都不合格）；再回退 content 末尾的合法数字。

    回退只看 content：reasoning 里会提到图0/图1/图2，用它做 last-number 会误判。
    """
    for m in reversed(_MARK_RE.findall(f"{content}\n{reasoning}")):
        v = int(m)
        if v == -1 or 0 <= v < n:
            return v
    for i in (int(x) for x in reversed(re.findall(r"\d+", str(content)))):
        if 0 <= i < n:
            return i
    return 0


def _parse_index(text: str, n: int) -> int:  # 兼容旧测试
    return _pick_index(text, "", n)
