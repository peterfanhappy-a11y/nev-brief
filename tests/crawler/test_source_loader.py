from pathlib import Path

import pytest

from nev_crawler.source_loader import load_sources_yaml, SourceSpec


def test_load_sources_yaml_returns_25():
    yaml_path = Path(__file__).parent.parent.parent / "packages" / "crawler" / "nev_crawler" / "sources_seed.yaml"
    specs = load_sources_yaml(yaml_path)
    assert len(specs) == 25


def test_source_spec_fields():
    yaml_path = Path(__file__).parent.parent.parent / "packages" / "crawler" / "nev_crawler" / "sources_seed.yaml"
    specs = load_sources_yaml(yaml_path)
    s = next(x for x in specs if x.name == "36氪汽车")
    assert s.type == "rss"
    assert s.authority == 9
    assert s.locale == "zh"
    assert s.category == "media"
    assert s.enabled is True


def test_source_spec_rejects_bad_type():
    with pytest.raises(Exception):
        SourceSpec(name="x", type="bogus_type", url="http://x", authority=5, locale="zh", category="media")


def test_source_spec_authority_range():
    with pytest.raises(Exception):
        SourceSpec(name="x", type="rss", url="http://x", authority=11, locale="zh", category="media")
