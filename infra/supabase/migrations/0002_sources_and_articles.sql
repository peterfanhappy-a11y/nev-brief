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
