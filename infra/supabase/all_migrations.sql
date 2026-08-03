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
-- 0006_sources_type_add_nextjs_json.sql
-- 扩展 sources.type 枚举，新增 'nextjs_json'（用于懂车帝等 Next.js __NEXT_DATA__ 源）

ALTER TABLE sources DROP CONSTRAINT IF EXISTS sources_type_check;
ALTER TABLE sources ADD CONSTRAINT sources_type_check
    CHECK (type IN ('rss','api','html_scrape','rsshub','nextjs_json'));
-- 0007: 给 articles_processed 加 simhash 列 + raw_id UNIQUE 约束
-- pipeline-service 需要 simhash 查询做聚类，raw_id UNIQUE 让 upsert 幂等
ALTER TABLE articles_processed ADD COLUMN IF NOT EXISTS simhash bigint;
CREATE INDEX IF NOT EXISTS idx_processed_simhash ON articles_processed(simhash);
ALTER TABLE articles_processed
    ADD CONSTRAINT articles_processed_raw_id_unique UNIQUE (raw_id);
-- 0008_ai_subscribers.sql
-- AIVIZENS / AI 趋势 tab 独立订阅表。与 subscribers (NEV 早报) 物理隔离，
-- 未来若 AI 趋势产品字段发散（推送频率、语言偏好、内容分类）不影响 NEV。
-- MVP 无 brands/topics/push_time，全员一份日报。

CREATE TABLE ai_subscribers (
    id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    email             text UNIQUE NOT NULL,
    status            text NOT NULL DEFAULT 'active'
                        CHECK (status IN ('active','paused','unsubscribed')),
    unsubscribe_token uuid NOT NULL UNIQUE DEFAULT gen_random_uuid(),
    source            text DEFAULT 'ai_landing',  -- future utm/referrer tracking
    created_at        timestamptz NOT NULL DEFAULT now(),
    updated_at        timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX idx_ai_subscribers_status ON ai_subscribers(status) WHERE status = 'active';
CREATE INDEX idx_ai_subscribers_email_lower ON ai_subscribers(lower(email));

-- 复用 0001 中定义的 touch_updated_at() 触发器函数
CREATE TRIGGER trg_ai_subscribers_updated
    BEFORE UPDATE ON ai_subscribers
    FOR EACH ROW EXECUTE FUNCTION touch_updated_at();
-- 0009_ai_pipeline.sql
-- AIVIZENS AI 趋势：完全独立的内容管线，与 NEV 表零交叉。
--   ai_articles      抓取的 AI 新闻（标题+URL+正文+og:image）
--   ai_daily_briefs  每日结构化简报文档（DeepSeek 两阶段输出）
--   ai_deliveries    每订阅者一封的投递记录
--   ai_ratings       邮件末尾评分模块回收
-- ai_subscribers 已在 0008 建好。

-- 抓取的 AI 文章。与 NEV 的 articles_raw 隔离：AI crawler 抓正文（NEV 只抓列表页）。
CREATE TABLE ai_articles (
    id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    source_name  text NOT NULL,
    locale       text NOT NULL DEFAULT 'en' CHECK (locale IN ('zh','en')),
    authority    smallint NOT NULL DEFAULT 5,
    url          text NOT NULL UNIQUE,
    title        text NOT NULL,
    content      text,                    -- 文章正文（截断存储），可能为空（抓取失败降级）
    og_image     text,                    -- og:image / twitter:image 绝对 https URL
    published_at timestamptz,
    crawled_at   timestamptz NOT NULL DEFAULT now(),
    created_at   timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX idx_ai_articles_crawled ON ai_articles(crawled_at DESC);

-- 每日简报文档。content jsonb = schema.py 的 AiBriefContent（version 字段内嵌）。
CREATE TABLE ai_daily_briefs (
    id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    brief_date   date NOT NULL UNIQUE,
    content      jsonb NOT NULL,
    model        text,
    generated_at timestamptz NOT NULL DEFAULT now(),
    created_at   timestamptz NOT NULL DEFAULT now(),
    updated_at   timestamptz NOT NULL DEFAULT now()
);

-- 每订阅者一封投递。subject 每日动态（compose 时定稿），故独立成列。
CREATE TABLE ai_deliveries (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    subscriber_id   uuid NOT NULL REFERENCES ai_subscribers(id) ON DELETE CASCADE,
    brief_date      date NOT NULL,
    subject         text NOT NULL,
    content_html    text NOT NULL,
    content_text    text NOT NULL,
    status          text NOT NULL DEFAULT 'pending'
                      CHECK (status IN ('pending','sending','sent','failed','bounced')),
    resend_id       text,
    sent_at         timestamptz,
    error           text,
    retry_count     smallint NOT NULL DEFAULT 0,
    created_at      timestamptz NOT NULL DEFAULT now(),
    updated_at      timestamptz NOT NULL DEFAULT now(),
    UNIQUE (subscriber_id, brief_date)
);

CREATE INDEX idx_ai_deliveries_status_date ON ai_deliveries(status, brief_date);

-- 评分回收。delivery_id 是每封邮件唯一的随机 uuid（与 unsubscribe_token 同信任模型），
-- 无需额外鉴权。后点覆盖先点（UNIQUE + upsert）。
CREATE TABLE ai_ratings (
    id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    delivery_id  uuid NOT NULL UNIQUE REFERENCES ai_deliveries(id) ON DELETE CASCADE,
    score        smallint NOT NULL CHECK (score BETWEEN 1 AND 3),  -- 3=很棒 2=还行 1=一般
    rated_at     timestamptz NOT NULL DEFAULT now(),
    created_at   timestamptz NOT NULL DEFAULT now(),
    updated_at   timestamptz NOT NULL DEFAULT now()
);

-- RLS：全部 service_role only（应用层走 service-role key，anon 一律拒绝）。
-- 补 0008 遗漏的 ai_subscribers RLS。
ALTER TABLE ai_subscribers   ENABLE ROW LEVEL SECURITY;
ALTER TABLE ai_articles      ENABLE ROW LEVEL SECURITY;
ALTER TABLE ai_daily_briefs  ENABLE ROW LEVEL SECURITY;
ALTER TABLE ai_deliveries    ENABLE ROW LEVEL SECURITY;
ALTER TABLE ai_ratings       ENABLE ROW LEVEL SECURITY;

-- updated_at 自动触发器（touch_updated_at() 在 0001 定义）
CREATE TRIGGER trg_ai_briefs_updated BEFORE UPDATE ON ai_daily_briefs
    FOR EACH ROW EXECUTE FUNCTION touch_updated_at();
CREATE TRIGGER trg_ai_deliveries_updated BEFORE UPDATE ON ai_deliveries
    FOR EACH ROW EXECUTE FUNCTION touch_updated_at();
CREATE TRIGGER trg_ai_ratings_updated BEFORE UPDATE ON ai_ratings
    FOR EACH ROW EXECUTE FUNCTION touch_updated_at();
-- 0010_ai_brief_images_bucket.sql
-- AIVIZENS 简报头图公开桶：每天把 digest 选中的头图上传到此桶，邮件热链。
-- 独立于 NEV。幂等：可重复执行。

-- 公开可读桶（存 digest 头图，路径 ai/<date>/<module>-<hash>.png）
insert into storage.buckets (id, name, public)
values ('ai-brief-images', 'ai-brief-images', true)
on conflict (id) do update set public = true;

-- 公开读策略（匿名可 GET 该桶对象；写入走 service-role 绕过 RLS）
do $$
begin
  if not exists (
    select 1 from pg_policies
    where schemaname = 'storage' and tablename = 'objects'
      and policyname = 'ai_brief_images_public_read'
  ) then
    create policy ai_brief_images_public_read
      on storage.objects for select
      to public
      using (bucket_id = 'ai-brief-images');
  end if;
end $$;
-- AIVIZENS production subscription state, confirmation tokens, and durable abuse limits.

ALTER TABLE ai_subscribers
    ADD COLUMN confirmation_token_hash text,
    ADD COLUMN confirmation_expires_at timestamptz,
    ADD COLUMN confirmed_at timestamptz,
    ADD COLUMN unsubscribed_at timestamptz,
    ADD COLUMN signup_ip_hash text,
    ADD COLUMN utm_source text,
    ADD COLUMN utm_medium text,
    ADD COLUMN utm_campaign text;

ALTER TABLE ai_subscribers
    DROP CONSTRAINT IF EXISTS ai_subscribers_status_check;

-- The legacy schema allowed paused. Keep those rows non-deliverable while moving
-- to the explicit production subscription state model.
UPDATE ai_subscribers
SET status = 'unsubscribed',
    unsubscribed_at = COALESCE(unsubscribed_at, updated_at)
WHERE status = 'paused';

ALTER TABLE ai_subscribers
    ALTER COLUMN status SET DEFAULT 'pending_confirmation',
    ADD CONSTRAINT ai_subscribers_status_check
        CHECK (status IN ('pending_confirmation', 'active', 'unsubscribed'));

CREATE UNIQUE INDEX idx_ai_subscribers_confirmation_token_hash
    ON ai_subscribers(confirmation_token_hash)
    WHERE confirmation_token_hash IS NOT NULL;

CREATE TABLE ai_subscription_attempts (
    scope             text NOT NULL
                          CHECK (scope IN ('ip', 'email')),
    key_hash          text NOT NULL
                          CHECK (key_hash ~ '^[0-9a-f]{64}$'),
    window_started_at timestamptz NOT NULL,
    attempt_count     integer NOT NULL DEFAULT 0
                          CHECK (attempt_count >= 0),
    blocked_until     timestamptz,
    created_at        timestamptz NOT NULL DEFAULT now(),
    updated_at        timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (scope, key_hash)
);

ALTER TABLE ai_subscription_attempts ENABLE ROW LEVEL SECURITY;

CREATE TRIGGER trg_ai_subscription_attempts_updated
    BEFORE UPDATE ON ai_subscription_attempts
    FOR EACH ROW EXECUTE FUNCTION touch_updated_at();

CREATE OR REPLACE FUNCTION confirm_ai_subscription(
    token_hash text,
    now_at timestamptz
)
RETURNS TABLE (
    id uuid,
    email text,
    unsubscribe_token uuid
)
LANGUAGE sql
SECURITY DEFINER
STRICT
SET search_path = ''
AS $$
    WITH candidate AS MATERIALIZED (
        SELECT subscriber.id
        FROM public.ai_subscribers AS subscriber
        WHERE subscriber.confirmation_token_hash = token_hash
          AND subscriber.status = 'pending_confirmation'
          AND subscriber.confirmation_expires_at > now_at
        ORDER BY subscriber.id
        FOR UPDATE
        LIMIT 1
    ), confirmed AS (
        UPDATE public.ai_subscribers AS subscriber
        SET status = 'active',
            confirmation_token_hash = NULL,
            confirmation_expires_at = NULL,
            confirmed_at = now_at,
            unsubscribed_at = NULL
        FROM candidate
        WHERE subscriber.id = candidate.id
        RETURNING subscriber.id, subscriber.email, subscriber.unsubscribe_token
    )
    SELECT confirmed.id, confirmed.email, confirmed.unsubscribe_token
    FROM confirmed;
$$;

REVOKE ALL ON FUNCTION confirm_ai_subscription(text, timestamptz) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION confirm_ai_subscription(text, timestamptz) TO service_role;

CREATE OR REPLACE FUNCTION prepare_ai_subscription(
    input_email text,
    input_token_hash text,
    input_expires_at timestamptz,
    input_ip_hash text,
    input_utm jsonb
)
RETURNS TABLE (
    confirmation_required boolean
)
LANGUAGE plpgsql
SECURITY DEFINER
STRICT
SET search_path = ''
AS $$
DECLARE
    prepared boolean;
BEGIN
    IF input_email <> lower(btrim(input_email))
       OR char_length(input_email) < 3
       OR char_length(input_email) > 254
       OR position('@' IN input_email) <= 1 THEN
        RAISE EXCEPTION 'invalid normalized subscriber email'
            USING ERRCODE = '22023';
    END IF;
    IF input_token_hash !~ '^[0-9a-f]{64}$' THEN
        RAISE EXCEPTION 'invalid confirmation token hash'
            USING ERRCODE = '22023';
    END IF;
    IF input_ip_hash !~ '^[0-9a-f]{64}$' THEN
        RAISE EXCEPTION 'invalid signup IP hash'
            USING ERRCODE = '22023';
    END IF;
    IF input_expires_at <= now() THEN
        RAISE EXCEPTION 'confirmation expiry must be in the future'
            USING ERRCODE = '22023';
    END IF;
    IF jsonb_typeof(input_utm) <> 'object'
       OR EXISTS (
           SELECT 1
           FROM jsonb_each(input_utm) AS item(key, value)
           WHERE item.key NOT IN ('source', 'medium', 'campaign')
              OR jsonb_typeof(item.value) NOT IN ('string', 'null')
              OR char_length(COALESCE(item.value #>> '{}', '')) > 200
       ) THEN
        RAISE EXCEPTION 'invalid UTM metadata'
            USING ERRCODE = '22023';
    END IF;

    INSERT INTO public.ai_subscribers AS subscriber (
        email,
        status,
        confirmation_token_hash,
        confirmation_expires_at,
        confirmed_at,
        unsubscribed_at,
        signup_ip_hash,
        utm_source,
        utm_medium,
        utm_campaign
    ) VALUES (
        input_email,
        'pending_confirmation',
        input_token_hash,
        input_expires_at,
        NULL,
        NULL,
        input_ip_hash,
        NULLIF(input_utm ->> 'source', ''),
        NULLIF(input_utm ->> 'medium', ''),
        NULLIF(input_utm ->> 'campaign', '')
    )
    ON CONFLICT ON CONSTRAINT ai_subscribers_email_key DO UPDATE
    SET status = 'pending_confirmation',
        confirmation_token_hash = EXCLUDED.confirmation_token_hash,
        confirmation_expires_at = EXCLUDED.confirmation_expires_at,
        confirmed_at = NULL,
        unsubscribed_at = NULL,
        signup_ip_hash = EXCLUDED.signup_ip_hash,
        utm_source = EXCLUDED.utm_source,
        utm_medium = EXCLUDED.utm_medium,
        utm_campaign = EXCLUDED.utm_campaign
    WHERE subscriber.status <> 'active'
    RETURNING true INTO prepared;

    confirmation_required := COALESCE(prepared, false);
    RETURN NEXT;
END;
$$;

REVOKE ALL ON FUNCTION prepare_ai_subscription(text, text, timestamptz, text, jsonb)
    FROM PUBLIC;
GRANT EXECUTE ON FUNCTION prepare_ai_subscription(text, text, timestamptz, text, jsonb)
    TO service_role;

CREATE OR REPLACE FUNCTION check_ai_subscription_rate_limit(
    ip_hash text,
    email_hash text,
    now_at timestamptz
)
RETURNS TABLE (
    allowed boolean,
    retry_after_seconds integer
)
LANGUAGE plpgsql
SECURITY DEFINER
STRICT
SET search_path = ''
AS $$
DECLARE
    ip_attempt public.ai_subscription_attempts%ROWTYPE;
    email_attempt public.ai_subscription_attempts%ROWTYPE;
    blocked_until_at timestamptz;
BEGIN
    -- Every call takes the IP row before the email row. The consistent lock
    -- order and ON CONFLICT row locks make increments atomic under concurrency.
    INSERT INTO public.ai_subscription_attempts AS attempt (
        scope,
        key_hash,
        window_started_at,
        attempt_count,
        blocked_until
    ) VALUES (
        'ip',
        ip_hash,
        now_at,
        1,
        NULL
    )
    ON CONFLICT (scope, key_hash) DO UPDATE
    SET window_started_at = CASE
            WHEN EXCLUDED.window_started_at >=
                 attempt.window_started_at + interval '15 minutes'
                THEN EXCLUDED.window_started_at
            ELSE attempt.window_started_at
        END,
        attempt_count = CASE
            WHEN EXCLUDED.window_started_at >=
                 attempt.window_started_at + interval '15 minutes'
                THEN 1
            ELSE attempt.attempt_count + 1
        END,
        blocked_until = CASE
            WHEN EXCLUDED.window_started_at >=
                 attempt.window_started_at + interval '15 minutes'
                THEN NULL
            WHEN attempt.blocked_until > EXCLUDED.window_started_at
                THEN attempt.blocked_until
            WHEN attempt.attempt_count + 1 > 5
                THEN attempt.window_started_at + interval '15 minutes'
            ELSE NULL
        END
    RETURNING attempt.* INTO ip_attempt;

    INSERT INTO public.ai_subscription_attempts AS attempt (
        scope,
        key_hash,
        window_started_at,
        attempt_count,
        blocked_until
    ) VALUES (
        'email',
        email_hash,
        now_at,
        1,
        NULL
    )
    ON CONFLICT (scope, key_hash) DO UPDATE
    SET window_started_at = CASE
            WHEN EXCLUDED.window_started_at >=
                 attempt.window_started_at + interval '1 hour'
                THEN EXCLUDED.window_started_at
            ELSE attempt.window_started_at
        END,
        attempt_count = CASE
            WHEN EXCLUDED.window_started_at >=
                 attempt.window_started_at + interval '1 hour'
                THEN 1
            ELSE attempt.attempt_count + 1
        END,
        blocked_until = CASE
            WHEN EXCLUDED.window_started_at >=
                 attempt.window_started_at + interval '1 hour'
                THEN NULL
            WHEN attempt.blocked_until > EXCLUDED.window_started_at
                THEN attempt.blocked_until
            WHEN attempt.attempt_count + 1 > 3
                THEN attempt.window_started_at + interval '1 hour'
            ELSE NULL
        END
    RETURNING attempt.* INTO email_attempt;

    allowed := NOT (
        COALESCE(ip_attempt.blocked_until > now_at, false) OR
        COALESCE(email_attempt.blocked_until > now_at, false)
    );

    IF allowed THEN
        retry_after_seconds := 0;
    ELSE
        blocked_until_at := GREATEST(
            COALESCE(ip_attempt.blocked_until, now_at),
            COALESCE(email_attempt.blocked_until, now_at)
        );
        retry_after_seconds := GREATEST(
            0,
            CEIL(EXTRACT(EPOCH FROM (blocked_until_at - now_at)))::integer
        );
    END IF;

    RETURN NEXT;
END;
$$;

REVOKE ALL ON FUNCTION check_ai_subscription_rate_limit(text, text, timestamptz)
    FROM PUBLIC;
GRANT EXECUTE ON FUNCTION check_ai_subscription_rate_limit(text, text, timestamptz)
    TO service_role;
-- 0012_ai_brief_workflow.sql
-- Explicit publication lifecycle for public AIVIZENS daily archives.

ALTER TABLE ai_daily_briefs
  ADD COLUMN status text NOT NULL DEFAULT 'generating'
    CHECK (status IN ('generating','blocked','awaiting_approval','approved','published')),
  ADD COLUMN quality_report jsonb,
  ADD COLUMN digest_sources jsonb,
  ADD COLUMN approved_at timestamptz,
  ADD COLUMN published_at timestamptz,
  ADD COLUMN failure_reason text;

-- Historical documents predate the workflow and require fresh review. Preserve
-- their content, but fail closed: none becomes public through this migration.
UPDATE ai_daily_briefs
SET status = 'awaiting_approval',
    quality_report = jsonb_build_object(
      'passed', false,
      'blockers', '[]'::jsonb,
      'warnings', jsonb_build_array(
        jsonb_build_object(
          'code', 'pre_workflow_import',
          'message', 'Imported before publication workflow; regenerate and review before approval.',
          'path', NULL
        )
      ),
      'metrics', jsonb_build_object('pre_workflow_import', true)
    );

CREATE INDEX idx_ai_daily_briefs_public
  ON ai_daily_briefs(published_at DESC)
  WHERE status = 'published';
