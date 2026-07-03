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
