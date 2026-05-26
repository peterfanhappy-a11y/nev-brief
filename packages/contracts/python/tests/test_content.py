from datetime import datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from python.content import Source, ArticleRaw, ArticleProcessed
from python.enums import SourceType, SourceCategory, Locale, ArticleStatus, Topic


def test_source_construction():
    s = Source(
        name="36氪汽车",
        type=SourceType.RSS,
        url="https://36kr.com/feed-newsflash",
        authority=9,
        locale=Locale.ZH,
        category=SourceCategory.MEDIA,
    )
    assert s.authority == 9
    assert s.enabled is True


def test_source_authority_out_of_range_rejected():
    with pytest.raises(ValidationError):
        Source(
            name="x", type=SourceType.RSS, url="https://x.com",
            authority=11, locale=Locale.ZH, category=SourceCategory.MEDIA,
        )


def test_article_raw_status_default_pending():
    a = ArticleRaw(source_id=uuid4(), url="https://example.com/a")
    assert a.status == ArticleStatus.PENDING


def test_article_raw_url_required():
    with pytest.raises(ValidationError):
        ArticleRaw(source_id=uuid4())


def test_article_processed_arrays_default_empty():
    a = ArticleProcessed(
        raw_id=uuid4(),
        title="Test",
        clean_text="body",
    )
    assert a.brands == []
    assert a.topics == []
    assert a.status == ArticleStatus.PENDING
