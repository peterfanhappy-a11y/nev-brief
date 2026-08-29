-- 0013_ai_digest_runs.sql
-- Durable, privacy-safe pipeline run records and aggregate operational views.

CREATE TABLE ai_digest_runs (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    brief_date      date NOT NULL,
    source_adapter  text NOT NULL,
    status          text NOT NULL DEFAULT 'running'
                        CHECK (status IN (
                            'running', 'blocked', 'awaiting_approval', 'failed', 'completed'
                        )),
    started_at      timestamptz NOT NULL DEFAULT statement_timestamp(),
    finished_at     timestamptz,
    duration_ms     bigint CHECK (duration_ms >= 0),
    digest_sources  jsonb NOT NULL DEFAULT '{}'::jsonb,
    parse_counts    jsonb NOT NULL DEFAULT '{}'::jsonb,
    quality_report  jsonb,
    failed_stage    text,
    error_summary   text,
    created_at      timestamptz NOT NULL DEFAULT now(),
    updated_at      timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT ai_digest_runs_completion_check CHECK (
        (status = 'running' AND finished_at IS NULL AND duration_ms IS NULL)
        OR
        (status <> 'running' AND finished_at IS NOT NULL AND duration_ms IS NOT NULL)
    ),
    CONSTRAINT ai_digest_runs_failed_stage_check CHECK (
        status <> 'failed'
        OR (failed_stage IS NOT NULL AND failed_stage !~ '^[[:space:]]*$')
    )
);

CREATE INDEX idx_ai_digest_runs_brief_date
    ON ai_digest_runs(brief_date DESC, started_at DESC);
CREATE INDEX idx_ai_digest_runs_running
    ON ai_digest_runs(started_at)
    WHERE status = 'running';

ALTER TABLE ai_digest_runs ENABLE ROW LEVEL SECURITY;

CREATE POLICY service_role_manage_ai_digest_runs
    ON ai_digest_runs
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

CREATE FUNCTION touch_ai_digest_run_updated_at()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    NEW.updated_at = statement_timestamp();
    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_ai_digest_runs_updated
    BEFORE UPDATE ON ai_digest_runs
    FOR EACH ROW EXECUTE FUNCTION touch_ai_digest_run_updated_at();

ALTER TABLE ai_daily_briefs
    ADD COLUMN approved_by text,
    ADD COLUMN source_run_id uuid REFERENCES ai_digest_runs(id);

CREATE INDEX idx_ai_daily_briefs_source_run
    ON ai_daily_briefs(source_run_id)
    WHERE source_run_id IS NOT NULL;

CREATE VIEW ai_subscription_stats
WITH (security_invoker = true)
AS
WITH counts AS (
    SELECT
        count(*) FILTER (WHERE source IS DISTINCT FROM 'test') AS total_non_test,
        count(*) FILTER (
            WHERE source IS DISTINCT FROM 'test' AND status = 'pending_confirmation'
        ) AS pending_count,
        count(*) FILTER (
            WHERE source IS DISTINCT FROM 'test' AND confirmed_at IS NOT NULL
        ) AS confirmed_count,
        count(*) FILTER (
            WHERE source IS DISTINCT FROM 'test' AND status = 'active'
        ) AS active_count,
        count(*) FILTER (
            WHERE source IS DISTINCT FROM 'test' AND status = 'unsubscribed'
        ) AS unsubscribed_count
    FROM ai_subscribers
)
SELECT
    total_non_test,
    pending_count,
    confirmed_count,
    active_count,
    unsubscribed_count,
    COALESCE(
        round(confirmed_count::numeric / NULLIF(total_non_test, 0), 4),
        0::numeric
    ) AS confirmation_rate
FROM counts;

CREATE VIEW ai_daily_operations
WITH (security_invoker = true)
AS
SELECT
    run.brief_date,
    count(*) AS run_count,
    count(*) FILTER (WHERE run.status = 'running') AS running_count,
    count(*) FILTER (WHERE run.status = 'blocked') AS blocked_count,
    count(*) FILTER (WHERE run.status = 'awaiting_approval') AS awaiting_approval_count,
    count(*) FILTER (WHERE run.status = 'failed') AS failed_count,
    count(*) FILTER (WHERE run.status = 'completed') AS completed_count,
    count(*) FILTER (WHERE run.failed_stage IS NOT NULL) AS staged_failure_count,
    COALESCE(sum(parse_totals.parsed_item_count), 0) AS parsed_item_count,
    COALESCE(sum(source_counts.missing_count), 0) AS missing_digest_count,
    COALESCE(sum(source_counts.fallback_count), 0) AS fallback_digest_count
FROM ai_digest_runs AS run
CROSS JOIN LATERAL (
    SELECT COALESCE(
        sum(
            CASE
                WHEN jsonb_typeof(parse_count.value) = 'number'
                    THEN (parse_count.value #>> '{}')::bigint
                ELSE 0
            END
        ),
        0
    ) AS parsed_item_count
    FROM jsonb_each(run.parse_counts) AS parse_count
) AS parse_totals
CROSS JOIN LATERAL (
    SELECT
        count(*) FILTER (WHERE source.value = 'null'::jsonb) AS missing_count,
        count(*) FILTER (WHERE source.value ->> 'used_fallback' = 'true') AS fallback_count
    FROM jsonb_each(run.digest_sources) AS source
) AS source_counts
GROUP BY run.brief_date;

CREATE VIEW ai_delivery_stats
WITH (security_invoker = true)
AS
SELECT
    brief_date,
    count(*) AS delivery_count,
    count(*) FILTER (WHERE status = 'pending') AS pending_count,
    count(*) FILTER (WHERE status = 'sending') AS sending_count,
    count(*) FILTER (WHERE status = 'sent') AS sent_count,
    count(*) FILTER (WHERE status = 'failed') AS failed_count,
    count(*) FILTER (WHERE status = 'bounced') AS bounced_count,
    COALESCE(sum(retry_count), 0) AS retry_count
FROM ai_deliveries
GROUP BY brief_date;

CREATE VIEW ai_rating_stats
WITH (security_invoker = true)
AS
SELECT
    delivery.brief_date,
    count(rating.id) AS rating_count,
    count(rating.id) FILTER (WHERE rating.score = 1) AS score_1_count,
    count(rating.id) FILTER (WHERE rating.score = 2) AS score_2_count,
    count(rating.id) FILTER (WHERE rating.score = 3) AS score_3_count,
    COALESCE(
        round(
            count(rating.id)::numeric
            / NULLIF(count(*) FILTER (WHERE delivery.status = 'sent'), 0),
            4
        ),
        0::numeric
    ) AS rating_rate
FROM ai_deliveries AS delivery
LEFT JOIN ai_ratings AS rating ON rating.delivery_id = delivery.id
GROUP BY delivery.brief_date;

REVOKE ALL ON ai_digest_runs FROM PUBLIC, anon, authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON ai_digest_runs TO service_role;

REVOKE ALL ON ai_subscription_stats FROM PUBLIC, anon, authenticated;
REVOKE ALL ON ai_daily_operations FROM PUBLIC, anon, authenticated;
REVOKE ALL ON ai_delivery_stats FROM PUBLIC, anon, authenticated;
REVOKE ALL ON ai_rating_stats FROM PUBLIC, anon, authenticated;
GRANT SELECT ON ai_subscription_stats TO service_role;
GRANT SELECT ON ai_daily_operations TO service_role;
GRANT SELECT ON ai_delivery_stats TO service_role;
GRANT SELECT ON ai_rating_stats TO service_role;
