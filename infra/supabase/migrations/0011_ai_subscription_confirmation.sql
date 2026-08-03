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
