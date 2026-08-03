# AIVIZENS subscription operations

## Production boundary

Production remains Vercel (Next.js) → Supabase (PostgreSQL, REST, and RPC) →
Resend, with Cloudflare Turnstile verified by the Next.js server. The local
PostgREST and fake Resend services are acceptance-test infrastructure only.
They are not deployed and they do not introduce an alternate production data
path.

Never place credentials, raw confirmation tokens, subscriber email addresses,
or full rate-limit hashes in tickets, chat, screenshots, or logs. Confirmation
tokens are stored only as SHA-256 hashes. The unsubscribe token is personal
data and must be handled accordingly.

## Resend a confirmation

There is no operator endpoint that activates a subscriber or sends around the
double opt-in flow.

1. Check Resend's service status and the Vercel log event
   `[ai/subscribe] confirmation email delivery failed`. That log is
   intentionally generic; do not add the address, token, or provider response
   to it.
2. Ask the reader to submit the public form again after transport recovery.
   The normal IP and email rate limits still apply.
3. A `pending_confirmation` or `unsubscribed` address receives a new pending
   token and a new confirmation email. Its prior confirmation link becomes
   invalid. An `active` address receives the same public check-email response
   without exposing its state or sending another confirmation.
4. The address becomes `active` only after one valid confirmation POST. Do not
   update the status manually. Welcome-email failure does not roll back a
   completed confirmation.

If the form returns `rate_limited`, wait for the reported retry window instead
of clearing durable limiter state. If a verified false positive requires an
exception, record the incident and use a reviewed, hash-scoped database change;
never delete the whole limiter table.

## Inspect durable rate limits

Run read-only queries in the Supabase SQL editor or through the approved
operator database session:

```sql
SELECT
    scope,
    left(key_hash, 12) AS key_hash_prefix,
    window_started_at,
    attempt_count,
    blocked_until,
    updated_at
FROM ai_subscription_attempts
WHERE blocked_until > now()
   OR updated_at > now() - interval '2 hours'
ORDER BY updated_at DESC
LIMIT 100;
```

Interpretation:

- IP rows use a 15-minute window and block after more than five attempts.
- Email rows use a one-hour window and block after more than three attempts.
- Each request increments both rows atomically. A storage/RPC error fails
  closed and the subscription is not prepared.
- `blocked_until` in the future determines the `Retry-After` response.

Do not attempt to reverse a hash. To correlate a reported request, use the
approved application-side HMAC tooling with the production secret still in its
secret manager; never copy that secret into SQL or a shell history.

## Turnstile outage

Turnstile is fail-closed. When Siteverify times out, returns a non-success
response, or production verification configuration is absent, no database
preparation or email send should occur.

1. Confirm the impact in Cloudflare status/analytics and Vercel logs. Expected
   application events are generic verification failures; they must not contain
   widget tokens or subscriber details.
2. Confirm `TURNSTILE_SECRET_KEY` and `NEXT_PUBLIC_TURNSTILE_SITE_KEY` are
   present in the intended Vercel environment without printing their values.
3. Do not enable `TURNSTILE_TEST_BYPASS` in production and do not deploy
   Cloudflare's documented dummy keys. The bypass is accepted only when
   `NODE_ENV=test`; browser acceptance renders Cloudflare's official dummy
   widget key in its isolated process and uses that guarded server-side bypass
   so CI does not depend on the public Siteverify network.
4. For a prolonged outage, disable the public form as described below. Reopen
   it only after a server-side verification check succeeds.

## Disable or restore the public form

To stop new subscription attempts without deleting any subscriber data:

1. Set `SUBSCRIPTIONS_ENABLED=false` in the production Vercel environment and
   deploy that configuration.
2. Verify the home page displays `订阅暂未开放` with no form or Turnstile
   widget.
3. Verify `POST /api/ai/subscribe` returns HTTP 503 with
   `subscriptions_disabled` before verification, rate limiting, database, or
   Resend access.
4. Leave `ai_subscribers`, `ai_subscription_attempts`, confirmations,
   deliveries, and ratings intact. The switch controls entry only.

To reopen, restore `SUBSCRIPTIONS_ENABLED=true`, deploy, then run a controlled
double-opt-in smoke test with an approved test address. Confirm the address is
pending before the confirmation POST and active afterward. Existing delivery
selection must continue to query only `status = 'active'`.
