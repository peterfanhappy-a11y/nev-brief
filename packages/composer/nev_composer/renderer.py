"""Jinja2 environment + render API."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import jinja2

_TEMPLATES_DIR = Path(__file__).parent / "templates"

_TOPIC_LABELS = {
    "new_car": "新车", "sales": "销量", "policy": "政策",
    "tech": "技术", "overseas": "海外", "people": "人事",
    "finance": "财务", "recall": "召回", "supply_chain": "供应链",
}


def topic_label(t: str) -> str:
    return _TOPIC_LABELS.get(t, t)


def _make_env(autoescape: bool) -> jinja2.Environment:
    env = jinja2.Environment(
        loader=jinja2.FileSystemLoader(str(_TEMPLATES_DIR)),
        autoescape=jinja2.select_autoescape(["html", "j2"]) if autoescape else False,
        trim_blocks=True,
        lstrip_blocks=True,
    )
    env.globals["topic_label"] = topic_label
    env.filters["label"] = topic_label
    return env


def render_html(ctx: dict[str, Any]) -> str:
    return _make_env(autoescape=True).get_template("brief.html.j2").render(**ctx)


def render_text(ctx: dict[str, Any]) -> str:
    # Plain-text 不需要 autoescape；HTML entities 会污染
    return _make_env(autoescape=False).get_template("brief.txt.j2").render(**ctx)
