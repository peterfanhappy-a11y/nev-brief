"""Sources YAML loader + DB upsert.

CLI: uv run python -m nev_crawler.source_loader sync
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field

from nev_shared.db import get_supabase_client
from nev_shared.logger import get_logger

log = get_logger("source_loader")


class SourceSpec(BaseModel):
    name: str
    type: str = Field(pattern="^(rss|api|html_scrape|html|rsshub|nextjs_json)$")
    url: str
    authority: int = Field(ge=1, le=10)
    locale: str = Field(pattern="^(zh|en)$")
    category: str = Field(pattern="^(media|official|association|oem)$")
    enabled: bool = True
    crawl_cron: str | None = None
    extra: dict[str, Any] = Field(default_factory=dict)


def load_sources_yaml(path: Path) -> list[SourceSpec]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return [SourceSpec(**s) for s in data["sources"]]


def upsert_sources(specs: list[SourceSpec]) -> int:
    """Upsert by (name) — name unique enough for MVP. Returns count."""
    client = get_supabase_client()
    count = 0
    for spec in specs:
        # html_scrape is the spec enum; we map 'html' from YAML to it
        db_type = "html_scrape" if spec.type == "html" else spec.type
        payload = {
            "name": spec.name,
            "type": db_type,
            "url": spec.url,
            "authority": spec.authority,
            "locale": spec.locale,
            "category": spec.category,
            "enabled": spec.enabled,
            "crawl_cron": spec.crawl_cron,
        }
        client.table("sources").upsert(payload, on_conflict="name").execute()
        count += 1
        log.info("upserted_source", name=spec.name, type=db_type)
    return count


def main() -> None:
    if len(sys.argv) < 2 or sys.argv[1] != "sync":
        print("Usage: python -m nev_crawler.source_loader sync")
        sys.exit(2)
    yaml_path = Path(__file__).parent / "sources_seed.yaml"
    specs = load_sources_yaml(yaml_path)
    n = upsert_sources(specs)
    print(f"Upserted {n} sources.")


if __name__ == "__main__":
    main()
