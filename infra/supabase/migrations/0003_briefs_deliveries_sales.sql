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
