-- Activate AI subscriptions immediately while preserving confirmation-based unsubscribe.

CREATE OR REPLACE FUNCTION activate_ai_subscription(
    input_email text,
    input_ip_hash text,
    input_utm jsonb
)
RETURNS TABLE (
    welcome_required boolean,
    unsubscribe_token uuid
)
LANGUAGE plpgsql
SECURITY DEFINER
STRICT
SET search_path = ''
AS $$
DECLARE
    activated_unsubscribe_token uuid;
BEGIN
    IF input_email <> lower(btrim(input_email))
       OR char_length(input_email) < 3
       OR char_length(input_email) > 254
       OR position('@' IN input_email) <= 1 THEN
        RAISE EXCEPTION 'invalid normalized subscriber email'
            USING ERRCODE = '22023';
    END IF;
    IF input_ip_hash !~ '^[0-9a-f]{64}$' THEN
        RAISE EXCEPTION 'invalid signup IP hash'
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
        'active',
        NULL,
        NULL,
        now(),
        NULL,
        input_ip_hash,
        NULLIF(input_utm ->> 'source', ''),
        NULLIF(input_utm ->> 'medium', ''),
        NULLIF(input_utm ->> 'campaign', '')
    )
    ON CONFLICT ON CONSTRAINT ai_subscribers_email_key DO UPDATE
    SET status = 'active',
        confirmation_token_hash = NULL,
        confirmation_expires_at = NULL,
        confirmed_at = now(),
        unsubscribed_at = NULL,
        signup_ip_hash = EXCLUDED.signup_ip_hash,
        utm_source = EXCLUDED.utm_source,
        utm_medium = EXCLUDED.utm_medium,
        utm_campaign = EXCLUDED.utm_campaign
    WHERE subscriber.status <> 'active'
    RETURNING subscriber.unsubscribe_token INTO activated_unsubscribe_token;

    IF activated_unsubscribe_token IS NOT NULL THEN
        welcome_required := true;
        unsubscribe_token := activated_unsubscribe_token;
        RETURN NEXT;
        RETURN;
    END IF;

    SELECT subscriber.unsubscribe_token
    INTO activated_unsubscribe_token
    FROM public.ai_subscribers AS subscriber
    WHERE subscriber.email = input_email;

    IF activated_unsubscribe_token IS NULL THEN
        RAISE EXCEPTION 'subscriber activation did not return a row';
    END IF;

    welcome_required := false;
    unsubscribe_token := activated_unsubscribe_token;
    RETURN NEXT;
END;
$$;

REVOKE ALL ON FUNCTION activate_ai_subscription(text, text, jsonb) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION activate_ai_subscription(text, text, jsonb) TO service_role;
