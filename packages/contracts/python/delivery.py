from datetime import date, datetime
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator

from python.enums import DeliveryStatus, SalesSource, Topic


def _count_chinese_chars(s: str) -> int:
    """中英混合时，1 个中文算 1 字，连续 ASCII 词整体算 1 字 — 此处先用字符总数简化。"""
    return len(s)


class SourceLink(BaseModel):
    name: str
    url: str


class BriefCandidate(BaseModel):
    rank: int = Field(ge=1)
    cluster_id: UUID
    title: str
    summary: str
    brands: list[str]
    topics: list[Topic]
    source_links: list[SourceLink]
    global_importance: float = Field(ge=0, le=100)

    @field_validator("title")
    @classmethod
    def title_max_25_chars(cls, v: str) -> str:
        if _count_chinese_chars(v) > 25:
            raise ValueError(f"title must be ≤25 chars, got {_count_chinese_chars(v)}")
        return v

    @field_validator("summary")
    @classmethod
    def summary_max_120_chars(cls, v: str) -> str:
        if _count_chinese_chars(v) > 120:
            raise ValueError(f"summary must be ≤120 chars, got {_count_chinese_chars(v)}")
        return v


class DailyBrief(BaseModel):
    model_config = ConfigDict(use_enum_values=False)

    id: UUID = Field(default_factory=uuid4)
    brief_date: date
    candidates: list[BriefCandidate]
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class Delivery(BaseModel):
    model_config = ConfigDict(use_enum_values=False)

    id: UUID = Field(default_factory=uuid4)
    subscriber_id: UUID
    brief_date: date
    content_html: str
    content_text: str
    selected_items: list[dict] | None = None
    status: DeliveryStatus = DeliveryStatus.PENDING
    resend_id: str | None = None
    sent_at: datetime | None = None
    opened_at: datetime | None = None
    error: str | None = None
    retry_count: int = Field(default=0, ge=0)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class VehicleSalesDaily(BaseModel):
    model_config = ConfigDict(use_enum_values=False)

    brand_code: str
    brand_name: str
    week_date: date
    units: int = Field(ge=0)
    yoy: float | None = None
    wow: float | None = None
    source: SalesSource
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
