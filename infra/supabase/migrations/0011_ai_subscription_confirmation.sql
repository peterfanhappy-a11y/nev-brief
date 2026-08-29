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
