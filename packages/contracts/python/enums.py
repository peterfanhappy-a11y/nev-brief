from enum import Enum


class SubscriberStatus(str, Enum):
    ACTIVE = "active"
    PAUSED = "paused"
    UNSUBSCRIBED = "unsubscribed"


class Plan(str, Enum):
    FREE = "free"
    PRO = "pro"
    ENTERPRISE = "enterprise"


class PushChannel(str, Enum):
    EMAIL = "email"
    FEISHU = "feishu"


class Topic(str, Enum):
    NEW_CAR = "new_car"
    SALES = "sales"
    POLICY = "policy"
    TECH = "tech"
    OVERSEAS = "overseas"
    PEOPLE = "people"
    FINANCE = "finance"
    RECALL = "recall"
    SUPPLY_CHAIN = "supply_chain"


class SourceType(str, Enum):
    RSS = "rss"
    API = "api"
    HTML_SCRAPE = "html_scrape"
    RSSHUB = "rsshub"


class SourceCategory(str, Enum):
    MEDIA = "media"
    OFFICIAL = "official"
    ASSOCIATION = "association"
    OEM = "oem"


class Locale(str, Enum):
    ZH = "zh"
    EN = "en"


class ArticleStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    DONE = "done"
    FAILED = "failed"


class DeliveryStatus(str, Enum):
    PENDING = "pending"
    SENDING = "sending"
    SENT = "sent"
    FAILED = "failed"
    BOUNCED = "bounced"


class SalesSource(str, Enum):
    CPCA = "CPCA"
    CAAM = "CAAM"
    OFFICIAL = "official"
