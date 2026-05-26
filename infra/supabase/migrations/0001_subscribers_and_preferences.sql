-- 0001_subscribers_and_preferences.sql
-- Spec §4.1

CREATE EXTENSION IF NOT EXISTS "pgcrypto";

CREATE TABLE subscribers (
    id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    email             text UNIQUE NOT NULL,
    status            text NOT NULL CHECK (status IN ('active','paused','unsubscribed')),
    plan              text NOT NULL DEFAULT 'free' CHECK (plan IN ('free','pro','enterprise')),
    push_time         time NOT NULL DEFAULT '08:00',
    push_channel      text NOT NULL DEFAULT 'email' CHECK (push_channel IN ('email','feishu')),
    unsubscribe_token uuid NOT NULL UNIQUE DEFAULT gen_random_uuid(),
    last_opened_at    timestamptz,
    created_at        timestamptz NOT NULL DEFAULT now(),
    updated_at        timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX idx_subscribers_status ON subscribers(status) WHERE status = 'active';
CREATE INDEX idx_subscribers_email_lower ON subscribers(lower(email));

CREATE TABLE subscriber_preferences (
    subscriber_id  uuid PRIMARY KEY REFERENCES subscribers(id) ON DELETE CASCADE,
    brands         text[] NOT NULL DEFAULT '{}',
    topics         text[] NOT NULL DEFAULT '{}',
    regions        text[] NOT NULL DEFAULT '{}',
    created_at     timestamptz NOT NULL DEFAULT now(),
    updated_at     timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX idx_pref_brands_gin ON subscriber_preferences USING GIN (brands);
CREATE INDEX idx_pref_topics_gin ON subscriber_preferences USING GIN (topics);

-- updated_at 自动更新触发器
CREATE OR REPLACE FUNCTION touch_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_subscribers_updated
    BEFORE UPDATE ON subscribers
    FOR EACH ROW EXECUTE FUNCTION touch_updated_at();

CREATE TRIGGER trg_pref_updated
    BEFORE UPDATE ON subscriber_preferences
    FOR EACH ROW EXECUTE FUNCTION touch_updated_at();
