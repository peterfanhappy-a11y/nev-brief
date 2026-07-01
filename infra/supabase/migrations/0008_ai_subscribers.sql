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
