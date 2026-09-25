# AIVIZENS subscription operations

## Production boundary

Production remains Vercel (Next.js) → Supabase (PostgreSQL, REST, and RPC) →
Resend, durable server-side rate limiting, and a two-second hold-to-verify
interaction. The local PostgREST and fake Resend services are acceptance-test infrastructure only.
They are not deployed and they do not introduce an alternate production data
path.

Never place credentials, raw confirmation tokens, subscriber email addresses,
or full rate-limit hashes in tickets, chat, screenshots, or logs. Confirmation
tokens are stored only as SHA-256 hashes. The unsubscribe token is personal
data and must be handled accordingly.

## Welcome-email delivery

The public form activates a valid subscription immediately after the hold
verification. It does not send a confirmation-subscription email.

1. Check Resend's service status and the Vercel log event
   `[ai/subscribe] welcome email delivery failed`. That log is
   intentionally generic; do not add the address, token, or provider response
   to it.
2. A new, legacy `pending_confirmation`, or `unsubscribed` address becomes
   `active` atomically and receives one welcome email. An existing `active`
   address remains unchanged and does not receive another welcome email.
3. Welcome-email failure does not roll back activation. Do not change the
   subscriber status manually or resend through an ad hoc provider call.
4. Legacy confirmation links already issued before immediate activation remain
   valid until expiry. No new confirmation links are issued by the public form.

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
  closed and the subscription is not activated.
- `blocked_until` in the future determines the `Retry-After` response.

Do not attempt to reverse a hash. To correlate a reported request, use the
approved application-side HMAC tooling with the production secret still in its
secret manager; never copy that secret into SQL or a shell history.

## Hold-to-verify and configuration

The public form does not load Cloudflare Turnstile. A reader selects “免费订阅”,
then continuously holds the verification dialog's progress bar for two seconds.
The browser automatically sends the subscription request when the hold completes.
This is a friction control, not a security boundary: the durable server-side
limiter remains mandatory.

1. Confirm `SUBSCRIPTION_HASH_SECRET` exists in the intended Vercel environment
   without printing its value. Its absence produces `server_configuration` and
   intentionally prevents subscription preparation.
2. If the form needs immediate containment, disable it as described below.
3. Do not replace the limiter with browser-only checks or a direct database
   insert path.

## Disable or restore the public form

To stop new subscription attempts without deleting any subscriber data:

1. Set `SUBSCRIPTIONS_ENABLED=false` in the production Vercel environment and
   deploy that configuration.
2. Verify the home page displays `订阅暂未开放` with no form.
3. Verify `POST /api/ai/subscribe` returns HTTP 503 with
   `subscriptions_disabled` before rate limiting, database, or
   Resend access.
4. Leave `ai_subscribers`, `ai_subscription_attempts`, confirmations,
   deliveries, and ratings intact. The switch controls entry only.

To reopen, restore `SUBSCRIPTIONS_ENABLED=true`, deploy, then run a controlled
smoke test with an approved test address. Confirm the address becomes active
immediately, receives one welcome email, and receives no confirmation-subscription
email. Existing delivery selection must continue to query only `status = 'active'`;
unsubscribe must still require the emailed confirmation link.
