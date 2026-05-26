from datetime import date, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from python.delivery import BriefCandidate, DailyBrief, Delivery, VehicleSalesDaily
from python.enums import DeliveryStatus, SalesSource, Topic


def test_brief_candidate_title_too_long_rejected():
    with pytest.raises(ValidationError):
        BriefCandidate(
            rank=1,
            cluster_id=uuid4(),
            title="超过二十五个字的标题啦啦啦啦啦啦啦啦啦啦啦啦啦啦啦啦",  # >25
            summary="ok",
            brands=[], topics=[], source_links=[],
            global_importance=80,
        )


def test_brief_candidate_summary_too_long_rejected():
    with pytest.raises(ValidationError):
        BriefCandidate(
            rank=1, cluster_id=uuid4(),
            title="正常标题",
            summary="过长" * 65,  # > 120 chars
            brands=[], topics=[], source_links=[],
            global_importance=80,
        )


def test_daily_brief_with_candidates():
    b = DailyBrief(
        brief_date=date(2026, 5, 24),
        candidates=[
            BriefCandidate(
                rank=1, cluster_id=uuid4(),
                title="测试标题",
                summary="测试摘要 120 字以内。",
                brands=["BYD"],
                topics=[Topic.SALES],
                source_links=[{"name": "36氪", "url": "https://36kr.com/x"}],
                global_importance=87,
            )
        ],
    )
    assert len(b.candidates) == 1


def test_delivery_default_pending():
    d = Delivery(
        subscriber_id=uuid4(),
        brief_date=date.today(),
        content_html="<html></html>",
        content_text="text",
    )
    assert d.status == DeliveryStatus.PENDING
    assert d.retry_count == 0


def test_sales_units_negative_rejected():
    with pytest.raises(ValidationError):
        VehicleSalesDaily(
            brand_code="BYD", brand_name="比亚迪",
            week_date=date.today(), units=-1, source=SalesSource.CPCA,
        )
