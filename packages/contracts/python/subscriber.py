from datetime import datetime, time
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from python.enums import Plan, PushChannel, SubscriberStatus, Topic


class Subscriber(BaseModel):
    model_config = ConfigDict(use_enum_values=False, str_strip_whitespace=True)

    id: UUID = Field(default_factory=uuid4)
    email: EmailStr
    status: SubscriberStatus
    plan: Plan = Plan.FREE
    push_time: time = time(8, 0)
    push_channel: PushChannel = PushChannel.EMAIL
    unsubscribe_token: UUID = Field(default_factory=uuid4)
    last_opened_at: datetime | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    @field_validator("email", mode="before")
    @classmethod
    def lower_email(cls, v: str) -> str:
        return v.lower() if isinstance(v, str) else v


class SubscriberPreferences(BaseModel):
    model_config = ConfigDict(use_enum_values=False)

    subscriber_id: UUID
    brands: list[str] = Field(default_factory=list)
    topics: list[Topic] = Field(default_factory=list)
    regions: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
