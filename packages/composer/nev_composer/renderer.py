"""Jinja2 environment + render API."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import jinja2

_TEMPLATES_DIR = Path(__file__).parent / "templates"

# Display label + emoji + section heading per topic.
# Section heading combines emoji + Chinese name shown as group header in v6+.
_TOPIC_META: dict[str, dict[str, str]] = {
    # 粗粒度
    "sales":              {"label": "销量",     "emoji": "📊", "heading": "📊 销量速览"},
    "new_car":            {"label": "新车",     "emoji": "🚙", "heading": "🚙 新车动态"},
    "policy":             {"label": "政策",     "emoji": "📜", "heading": "📜 政策法规"},
    "overseas":           {"label": "海外",     "emoji": "🌍", "heading": "🌍 海外动态"},
    "people":             {"label": "人事",     "emoji": "👤", "heading": "👤 人事变动"},
    "finance":            {"label": "财务",     "emoji": "💰", "heading": "💰 财务资本"},
    "recall":             {"label": "召回",     "emoji": "⚠️", "heading": "⚠️ 召回质量"},
    "supply_chain":       {"label": "供应链",   "emoji": "🔗", "heading": "🔗 供应链"},
    # 技术细分
    "battery_tech":       {"label": "电池技术", "emoji": "🔋", "heading": "🔋 电池技术"},
    "autonomous_driving": {"label": "智能驾驶", "emoji": "🤖", "heading": "🤖 智能驾驶"},
    "smart_cockpit":      {"label": "智能座舱", "emoji": "🎙️", "heading": "🎙️ 智能座舱"},
    "ota_update":         {"label": "OTA",     "emoji": "📡", "heading": "📡 OTA 升级"},
    "chassis":            {"label": "底盘",     "emoji": "🛞", "heading": "🛞 底盘操控"},
    "exterior_design":    {"label": "外观",     "emoji": "🎨", "heading": "🎨 外观设计"},
    "tech":               {"label": "技术",     "emoji": "🔧", "heading": "🔧 通用技术"},
}

# Default for unknown topics
_DEFAULT_META = {"label": "其他", "emoji": "▫️", "heading": "▫️ 其他"}


def topic_label(t: str) -> str:
    return _TOPIC_META.get(t, _DEFAULT_META)["label"]


def topic_emoji(t: str) -> str:
    return _TOPIC_META.get(t, _DEFAULT_META)["emoji"]


def topic_heading(t: str) -> str:
    return _TOPIC_META.get(t, _DEFAULT_META)["heading"]


def _make_env(autoescape: bool) -> jinja2.Environment:
    env = jinja2.Environment(
        loader=jinja2.FileSystemLoader(str(_TEMPLATES_DIR)),
        autoescape=jinja2.select_autoescape(["html", "j2"]) if autoescape else False,
        trim_blocks=True,
        lstrip_blocks=True,
    )
    env.globals["topic_label"] = topic_label
    env.globals["topic_emoji"] = topic_emoji
    env.globals["topic_heading"] = topic_heading
    env.filters["label"] = topic_label
    env.filters["emoji"] = topic_emoji
    return env


def render_html(ctx: dict[str, Any]) -> str:
    return _make_env(autoescape=True).get_template("brief.html.j2").render(**ctx)


def render_text(ctx: dict[str, Any]) -> str:
    # Plain-text 不需要 autoescape；HTML entities 会污染
    return _make_env(autoescape=False).get_template("brief.txt.j2").render(**ctx)
