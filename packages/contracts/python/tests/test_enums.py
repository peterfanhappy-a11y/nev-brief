from python.enums import (
    SubscriberStatus, Plan, PushChannel, Topic, SourceType, SourceCategory,
    ArticleStatus, DeliveryStatus, SalesSource, Locale,
)


def test_subscriber_status_values():
    assert SubscriberStatus.ACTIVE.value == "active"
    assert SubscriberStatus.PAUSED.value == "paused"
    assert SubscriberStatus.UNSUBSCRIBED.value == "unsubscribed"


def test_all_topics_defined():
    expected = {"new_car","sales","policy","tech","overseas","people","finance","recall","supply_chain"}
    assert {t.value for t in Topic} == expected


def test_article_status_lifecycle():
    assert {s.value for s in ArticleStatus} == {"pending","processing","done","failed"}
