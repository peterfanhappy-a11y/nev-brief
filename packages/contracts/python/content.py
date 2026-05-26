from datetime import datetime
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field

from python.enums import (
    ArticleStatus, Locale, SourceCategory, SourceType, Topic,
)


class Source(BaseModel):
    model_config = ConfigDict(use_enum_values=False)

    id: UUID = Field(default_factory=uuid4)
    name: str
    type: SourceType
    url: str  # 不用 HttpUrl 以兼容 RSSHub 内网地址
    authority: int = Field(ge=1, le=10)
    locale: Locale
    category: SourceCategory
    enabled: bool = True
    crawl_cron: str | None = None
    last_crawled_at: datetime | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class ArticleRaw(BaseModel):
    model_config = ConfigDict(use_enum_values=False)

    id: UUID = Field(default_factory=uuid4)
    source_id: UUID
    url: str
    title: str | None = None
    content: str | None = None
    content_hash: str | None = None
    published_at: datetime | None = None
    crawled_at: datetime = Field(default_factory=datetime.utcnow)
    status: ArticleStatus = ArticleStatus.PENDING
    error: str | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class ArticleProcessed(BaseModel):
    model_config = ConfigDict(use_enum_values=False)

    id: UUID = Field(default_factory=uuid4)
    raw_id: UUID
    title: str
    clean_text: str
    language: Locale | None = None
    brands: list[str] = Field(default_factory=list)
    models: list[str] = Field(default_factory=list)
    topics: list[Topic] = Field(default_factory=list)
    people: list[str] = Field(default_factory=list)
    importance_score: float | None = None
    cluster_id: UUID | None = None
    status: ArticleStatus = ArticleStatus.PENDING
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
