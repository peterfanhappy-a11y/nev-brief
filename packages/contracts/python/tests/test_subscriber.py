from datetime import datetime, time
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from python.subscriber import Subscriber, SubscriberPreferences
from python.enums import SubscriberStatus, Plan, PushChannel, Topic


def test_subscriber_minimal_construction():
    s = Subscriber(
        email="peter@example.com",
        status=SubscriberStatus.ACTIVE,
        plan=Plan.FREE,
    )
    assert s.email == "peter@example.com"
    assert s.push_time == time(8, 0)
    assert s.push_channel == PushChannel.EMAIL
    assert isinstance(s.unsubscribe_token, UUID)


def test_subscriber_email_lowercased():
    s = Subscriber(email="Peter@Example.COM", status=SubscriberStatus.ACTIVE, plan=Plan.FREE)
    assert s.email == "peter@example.com"


def test_subscriber_invalid_email_rejected():
    with pytest.raises(ValidationError):
        Subscriber(email="not-an-email", status=SubscriberStatus.ACTIVE, plan=Plan.FREE)


def test_preferences_default_empty_arrays():
    p = SubscriberPreferences(subscriber_id=uuid4())
    assert p.brands == []
    assert p.topics == []
    assert p.regions == []


def test_preferences_topic_enum_coerced():
    p = SubscriberPreferences(
        subscriber_id=uuid4(),
        topics=[Topic.NEW_CAR, Topic.SALES],
    )
    assert [t.value for t in p.topics] == ["new_car", "sales"]
