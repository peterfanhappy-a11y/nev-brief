from enum import Enum


class SubscriberStatus(str, Enum):  # noqa: UP042 - preserve str(Enum) behavior
    ACTIVE = "active"
    PAUSED = "paused"
    UNSUBSCRIBED = "unsubscribed"


class Plan(str, Enum):  # noqa: UP042 - preserve str(Enum) behavior
    FREE = "free"
    PRO = "pro"
    ENTERPRISE = "enterprise"


class PushChannel(str, Enum):  # noqa: UP042 - preserve str(Enum) behavior
    EMAIL = "email"
    FEISHU = "feishu"


class Topic(str, Enum):  # noqa: UP042 - preserve str(Enum) behavior
    NEW_CAR = "new_car"
    SALES = "sales"
    POLICY = "policy"
    TECH = "tech"
    OVERSEAS = "overseas"
    PEOPLE = "people"
    FINANCE = "finance"
    RECALL = "recall"
    SUPPLY_CHAIN = "supply_chain"


class SourceType(str, Enum):  # noqa: UP042 - preserve str(Enum) behavior
    RSS = "rss"
    API = "api"
    HTML_SCRAPE = "html_scrape"
    RSSHUB = "rsshub"


class SourceCategory(str, Enum):  # noqa: UP042 - preserve str(Enum) behavior
    MEDIA = "media"
    OFFICIAL = "official"
    ASSOCIATION = "association"
    OEM = "oem"


class Locale(str, Enum):  # noqa: UP042 - preserve str(Enum) behavior
    ZH = "zh"
    EN = "en"


class ArticleStatus(str, Enum):  # noqa: UP042 - preserve str(Enum) behavior
    PENDING = "pending"
    PROCESSING = "processing"
    DONE = "done"
    FAILED = "failed"


class DeliveryStatus(str, Enum):  # noqa: UP042 - preserve str(Enum) behavior
    PENDING = "pending"
    SENDING = "sending"
    SENT = "sent"
    FAILED = "failed"
    BOUNCED = "bounced"


class SalesSource(str, Enum):  # noqa: UP042 - preserve str(Enum) behavior
    CPCA = "CPCA"
    CAAM = "CAAM"
    OFFICIAL = "official"
