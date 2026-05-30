"""Entity extractor (T8) — DeepSeek Prompt 1 with entity_dict fallback.

Implements spec §6.2 Prompt 1: LLM-based brand / model / topic / people recognition.
When DeepSeek call or JSON parse fails, falls back to entity_dict.yaml dict lookup
(satisfies acceptance gate 4).
"""
from __future__ import annotations

from dataclasses import dataclass, field

from nev_shared.logger import get_logger

from nev_pipeline.deepseek_client import extract_json_with_retry
from nev_pipeline.entity_dict import find_brands_in_text

log = get_logger("entity_extractor")

# Spec §6.2 Prompt 1
_SYSTEM_PROMPT = """你是新能源汽车行业新闻分析助手。
从新闻文章中提取结构化信息。

【车企别名表】
比亚迪/BYD, 特斯拉/Tesla, 蔚来/NIO, 小鹏/XPeng, 理想/Li Auto,
华为/AITO/问界/鸿蒙智行, 小米/Xiaomi/SU7, 极氪/Zeekr, 零跑/Leapmotor,
广汽埃安/Aion, 上汽智己/IM, 长安阿维塔/Avatr, 长城/魏牌/欧拉,
吉利/银河, 奇瑞/iCAR, 五菱/MG, Stellantis/Jeep/标致/雪铁龙,
Volkswagen/大众, Toyota/丰田, Honda/本田, Ford/福特, GM/通用,
Rivian, Lucid, Polestar, Hyundai/现代, Kia/起亚, BMW/宝马,
Mercedes/奔驰, Audi/奥迪, Porsche/保时捷
(其他视情况识别)

【主题枚举】
new_car, sales, policy, tech, overseas, people, finance, recall, supply_chain

【严格 JSON 输出】
{
  "brands": ["canonical names"],
  "models": ["..."],
  "topics": ["1-3 个枚举值"],
  "people": ["关键人物"],
  "is_significant": true/false,
  "significance_reason": "若 false 给原因"
}
不要解释，只输出 JSON。"""


@dataclass(frozen=True)
class Entities:
    """Structured entities extracted from an article."""

    brands: list[str] = field(default_factory=list)
    models: list[str] = field(default_factory=list)
    topics: list[str] = field(default_factory=list)
    people: list[str] = field(default_factory=list)
    is_significant: bool = True
    significance_reason: str = ""
    used_fallback: bool = False  # True if DeepSeek failed and we used dict


def _build_user_prompt(title: str, clean_text: str) -> str:
    return f"标题: {title}\n正文（截断到 1500 字）: {clean_text[:1500]}"


async def extract_entities(title: str, clean_text: str) -> Entities:
    """Extract entities via DeepSeek; fall back to entity_dict on failure."""
    user = _build_user_prompt(title, clean_text)
    result = await extract_json_with_retry(
        _SYSTEM_PROMPT, user, max_tokens=400, temperature=0.0
    )

    if result is None:
        # Fallback: dict-based brand lookup. Topics/models/people unavailable.
        combined = f"{title} {clean_text}"
        brands = find_brands_in_text(combined)
        log.info("entity_extract_fallback", brands_found=len(brands))
        return Entities(brands=brands, used_fallback=True)

    return Entities(
        brands=list(result.get("brands", [])),
        models=list(result.get("models", [])),
        topics=list(result.get("topics", [])),
        people=list(result.get("people", [])),
        is_significant=bool(result.get("is_significant", True)),
        significance_reason=str(result.get("significance_reason", "")),
        used_fallback=False,
    )
