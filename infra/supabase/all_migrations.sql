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
-- 0002_sources_and_articles.sql
-- Spec §4.2

CREATE TABLE sources (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    name            text NOT NULL,
    type            text NOT NULL CHECK (type IN ('rss','api','html_scrape','rsshub')),
    url             text NOT NULL,
    authority       smallint NOT NULL CHECK (authority BETWEEN 1 AND 10),
    locale          text NOT NULL CHECK (locale IN ('zh','en')),
    category        text NOT NULL CHECK (category IN ('media','official','association','oem')),
    enabled         boolean NOT NULL DEFAULT true,
    crawl_cron      text,
    last_crawled_at timestamptz,
    created_at      timestamptz NOT NULL DEFAULT now(),
    updated_at      timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX idx_sources_enabled ON sources(enabled) WHERE enabled = true;

CREATE TABLE articles_raw (
    id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    source_id     uuid NOT NULL REFERENCES sources(id),
    url           text NOT NULL UNIQUE,
    title         text,
    content       text,
    content_hash  text,
    published_at  timestamptz,
    crawled_at    timestamptz NOT NULL DEFAULT now(),
    status        text NOT NULL DEFAULT 'pending'
                    CHECK (status IN ('pending','processing','done','failed')),
    error         text,
    created_at    timestamptz NOT NULL DEFAULT now(),
    updated_at    timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX idx_raw_status_crawled ON articles_raw(status, crawled_at);
CREATE INDEX idx_raw_hash ON articles_raw(content_hash);
CREATE INDEX idx_raw_source_published ON articles_raw(source_id, published_at);

CREATE TABLE articles_processed (
    id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    raw_id            uuid NOT NULL REFERENCES articles_raw(id) ON DELETE CASCADE,
    title             text NOT NULL,
    clean_text        text NOT NULL,
    language          text CHECK (language IN ('zh','en')),
    brands            text[] NOT NULL DEFAULT '{}',
    models            text[] NOT NULL DEFAULT '{}',
    topics            text[] NOT NULL DEFAULT '{}',
    people            text[] NOT NULL DEFAULT '{}',
    importance_score  real,
    cluster_id        uuid,
    status            text NOT NULL DEFAULT 'pending'
                        CHECK (status IN ('pending','processing','done','failed')),
    created_at        timestamptz NOT NULL DEFAULT now(),
    updated_at        timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX idx_processed_cluster ON articles_processed(cluster_id);
CREATE INDEX idx_processed_importance ON articles_processed(importance_score DESC);
CREATE INDEX idx_processed_brands ON articles_processed USING GIN (brands);
CREATE INDEX idx_processed_topics ON articles_processed USING GIN (topics);

CREATE TRIGGER trg_sources_updated BEFORE UPDATE ON sources
    FOR EACH ROW EXECUTE FUNCTION touch_updated_at();
CREATE TRIGGER trg_raw_updated BEFORE UPDATE ON articles_raw
    FOR EACH ROW EXECUTE FUNCTION touch_updated_at();
CREATE TRIGGER trg_processed_updated BEFORE UPDATE ON articles_processed
    FOR EACH ROW EXECUTE FUNCTION touch_updated_at();
-- 0003_briefs_deliveries_sales.sql
-- Spec §4.2 §4.3

CREATE TABLE daily_briefs (
    id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    brief_date   date NOT NULL UNIQUE,
    candidates   jsonb NOT NULL,
    generated_at timestamptz NOT NULL DEFAULT now(),
    created_at   timestamptz NOT NULL DEFAULT now(),
    updated_at   timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE vehicle_sales_daily (
    brand_code  text NOT NULL,
    brand_name  text NOT NULL,
    week_date   date NOT NULL,
    units       integer NOT NULL,
    yoy         real,
    wow         real,
    source      text NOT NULL CHECK (source IN ('CPCA','CAAM','official')),
    created_at  timestamptz NOT NULL DEFAULT now(),
    updated_at  timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (brand_code, week_date, source)
);

CREATE INDEX idx_sales_week ON vehicle_sales_daily(week_date DESC);

CREATE TABLE deliveries (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    subscriber_id   uuid NOT NULL REFERENCES subscribers(id) ON DELETE CASCADE,
    brief_date      date NOT NULL,
    content_html    text NOT NULL,
    content_text    text NOT NULL,
    selected_items  jsonb,
    status          text NOT NULL DEFAULT 'pending'
                      CHECK (status IN ('pending','sending','sent','failed','bounced')),
    resend_id       text,
    sent_at         timestamptz,
    opened_at       timestamptz,
    error           text,
    retry_count     smallint NOT NULL DEFAULT 0,
    created_at      timestamptz NOT NULL DEFAULT now(),
    updated_at      timestamptz NOT NULL DEFAULT now(),
    UNIQUE (subscriber_id, brief_date)
);

CREATE INDEX idx_deliveries_status_date ON deliveries(status, brief_date);

CREATE TRIGGER trg_briefs_updated BEFORE UPDATE ON daily_briefs
    FOR EACH ROW EXECUTE FUNCTION touch_updated_at();
CREATE TRIGGER trg_sales_updated BEFORE UPDATE ON vehicle_sales_daily
    FOR EACH ROW EXECUTE FUNCTION touch_updated_at();
CREATE TRIGGER trg_deliveries_updated BEFORE UPDATE ON deliveries
    FOR EACH ROW EXECUTE FUNCTION touch_updated_at();
-- 0004_rls_policies.sql
-- Spec §4.4 §7.6

-- Create Supabase roles for local dev (safe if they exist)
DO $$ BEGIN
  CREATE ROLE anon NOINHERIT;
EXCEPTION WHEN duplicate_object THEN END;
$$;

DO $$ BEGIN
  CREATE ROLE authenticated NOINHERIT;
EXCEPTION WHEN duplicate_object THEN END;
$$;

DO $$ BEGIN
  CREATE ROLE service_role NOINHERIT;
EXCEPTION WHEN duplicate_object THEN END;
$$;

-- 启用所有表的 RLS
ALTER TABLE subscribers              ENABLE ROW LEVEL SECURITY;
ALTER TABLE subscriber_preferences   ENABLE ROW LEVEL SECURITY;
ALTER TABLE sources                  ENABLE ROW LEVEL SECURITY;
ALTER TABLE articles_raw             ENABLE ROW LEVEL SECURITY;
ALTER TABLE articles_processed       ENABLE ROW LEVEL SECURITY;
ALTER TABLE daily_briefs             ENABLE ROW LEVEL SECURITY;
ALTER TABLE vehicle_sales_daily      ENABLE ROW LEVEL SECURITY;
ALTER TABLE deliveries               ENABLE ROW LEVEL SECURITY;

-- 所有表禁止 anon role 任何操作
-- service_role 自动绕过 RLS（Postgres 默认行为）
-- 即所有应用层访问必须用 service_role key（在 .env 中）

-- 唯一例外：sources 表允许 anon SELECT（公开信源清单）
CREATE POLICY anon_read_sources_enabled
    ON sources FOR SELECT
    TO anon
    USING (enabled = true);

-- 不为其他表创建任何 anon policy → 默认拒绝所有
-- 0005_sources_name_unique.sql
-- 为 source_loader.upsert 提供 ON CONFLICT 目标
ALTER TABLE sources ADD CONSTRAINT sources_name_unique UNIQUE (name);
