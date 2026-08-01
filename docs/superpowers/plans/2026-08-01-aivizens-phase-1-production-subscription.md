# AIVIZENS Phase 1 Production Subscription Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace immediate activation with a production-safe double-opt-in subscription flow protected by server-side Turnstile and durable IP/email rate limits.

**Architecture:** The Web route normalizes the email, verifies Turnstile, evaluates database-backed rate limits, and upserts a `pending_confirmation` subscriber with a one-time hashed token. A POST confirmation endpoint atomically consumes the token, activates the subscriber, and sends the welcome email. Browser GET requests only render confirmation, unsubscribe, or rating pages and never mutate subscription data.

**Tech Stack:** Next.js 14 Route Handlers and Server Actions, TypeScript, Zod, Vitest, Supabase/Postgres, Resend, Cloudflare Turnstile, Web Crypto/Node crypto.

## Global Constraints

- Unknown, existing, pending, and unsubscribed emails receive the same public subscribe response.
- Store only SHA-256 token hashes; never persist or log raw confirmation tokens.
- Confirmation tokens expire after 24 hours and are single-use.
- Resubscription from `unsubscribed` returns to `pending_confirmation`; it never becomes active without confirmation.
- Turnstile is fail-closed in production. Missing production secrets are configuration errors.
- Rate-limit keys contain HMAC/SHA-256 hashes, not raw IP addresses or emails.
- GET confirmation, unsubscribe, and rating requests are read-only.
- `SUBSCRIPTIONS_ENABLED=false` disables both the public form and the subscribe API without deleting data.
- Do not clear production subscribers in this phase; Phase 5 owns that approved production operation.

---

### Task 1: Add the subscription state and rate-limit schema

**Files:**
- Create: `infra/supabase/migrations/0011_ai_subscription_confirmation.sql`
- Modify: `infra/supabase/all_migrations.sql`
- Create: `packages/web/lib/subscription-types.ts`
- Create: `packages/web/lib/subscription-types.test.ts`

**Interfaces:**
- `AiSubscriberStatus = "pending_confirmation" | "active" | "unsubscribed"`.
- `ai_subscription_attempts(scope, key_hash, window_started_at, attempt_count, blocked_until)` is the durable limiter store.
- `confirm_ai_subscription(token_hash text, now_at timestamptz)` atomically returns the confirmed email/token or no row.

- [ ] **Step 1: Write the failing TypeScript state test**

Create `packages/web/lib/subscription-types.test.ts`:

```ts
import { describe, expect, it } from "vitest";
import { canReceiveAiBrief, nextSubscriberStatus } from "./subscription-types";

describe("AI subscriber states", () => {
  it("allows delivery only to active subscribers", () => {
    expect(canReceiveAiBrief("pending_confirmation")).toBe(false);
    expect(canReceiveAiBrief("active")).toBe(true);
    expect(canReceiveAiBrief("unsubscribed")).toBe(false);
  });

  it("requires confirmation after resubscription", () => {
    expect(nextSubscriberStatus("unsubscribed", "subscribe")).toBe(
      "pending_confirmation",
    );
  });
});
```

- [ ] **Step 2: Run the test and observe the missing module**

```bash
npm --workspace @nev/web test -- subscription-types.test.ts
```

Expected before implementation: import failure for `subscription-types`.

- [ ] **Step 3: Implement the state helpers**

Create `packages/web/lib/subscription-types.ts` with exhaustive transitions for `subscribe`, `confirm`, and `unsubscribe`. Throw on illegal transitions; `canReceiveAiBrief` returns true only for `active`.

- [ ] **Step 4: Add the additive migration**

The migration must:

```sql
ALTER TABLE ai_subscribers DROP CONSTRAINT IF EXISTS ai_subscribers_status_check;
ALTER TABLE ai_subscribers
  ADD CONSTRAINT ai_subscribers_status_check
  CHECK (status IN ('pending_confirmation','active','unsubscribed'));

ALTER TABLE ai_subscribers
  ALTER COLUMN status SET DEFAULT 'pending_confirmation',
  ADD COLUMN confirmation_token_hash text,
  ADD COLUMN confirmation_expires_at timestamptz,
  ADD COLUMN confirmed_at timestamptz,
  ADD COLUMN unsubscribed_at timestamptz,
  ADD COLUMN signup_ip_hash text,
  ADD COLUMN utm_source text,
  ADD COLUMN utm_medium text,
  ADD COLUMN utm_campaign text;

CREATE UNIQUE INDEX idx_ai_subscribers_confirmation_token_hash
  ON ai_subscribers(confirmation_token_hash)
  WHERE confirmation_token_hash IS NOT NULL;
```

Create `ai_subscription_attempts` with a unique `(scope, key_hash)` key, `scope IN ('ip','email')`, RLS enabled, and `touch_updated_at()` trigger. Add a `SECURITY DEFINER` `confirm_ai_subscription` function that locks one non-expired pending row, sets it active, clears the confirmation hash/expiry, records `confirmed_at`, and returns only `id`, `email`, and `unsubscribe_token`. Revoke public execute and grant it only to `service_role`.

Append the migration to `infra/supabase/all_migrations.sql` without modifying earlier migrations.

- [ ] **Step 5: Validate SQL structure and commit**

```bash
rg -n "pending_confirmation|confirm_ai_subscription|ai_subscription_attempts" infra/supabase
npm --workspace @nev/web test -- subscription-types.test.ts
git add infra/supabase packages/web/lib/subscription-types.ts packages/web/lib/subscription-types.test.ts
git commit -m "feat(subscription): add confirmation state model"
```

### Task 2: Implement one-time token generation and confirmation email

**Files:**
- Create: `packages/web/lib/subscription-token.ts`
- Create: `packages/web/lib/subscription-token.test.ts`
- Create: `packages/web/lib/ai-confirmation-email.ts`
- Create: `packages/web/lib/ai-confirmation-email.test.ts`
- Modify: `packages/web/lib/ai-welcome-email.ts`
- Modify: `packages/web/.env.local.example`

**Interfaces:**
- `createConfirmationToken(): { rawToken: string; tokenHash: string }`.
- `hashConfirmationToken(rawToken: string): string`.
- `sendAiConfirmationEmail(email: string, rawToken: string): Promise<void>`.
- Confirmation URL: `${WEB_BASE_URL}/confirm?token=${encodeURIComponent(rawToken)}`.

- [ ] **Step 1: Write failing token and email tests**

Tests must assert:

- generated tokens have at least 256 bits of entropy;
- hashes are deterministic 64-character lowercase hex;
- raw tokens never appear in the mocked database payload;
- confirmation email contains `/confirm?token=` and does not say the reader is already subscribed;
- welcome email is a separate function called only after confirmation.

- [ ] **Step 2: Verify failure**

```bash
npm --workspace @nev/web test -- subscription-token.test.ts ai-confirmation-email.test.ts
```

Expected before implementation: missing modules/functions.

- [ ] **Step 3: Implement token helpers**

Use `randomBytes(32).toString("base64url")` for the raw token and SHA-256 hex for storage. Do not add reversible encryption or token logging.

- [ ] **Step 4: Implement the confirmation message**

Render both HTML and plain text. Set a 24-hour-expiry message, brand the sender as `AIVIZENS 趋势`, and use `WEB_BASE_URL`. Throw if `WEB_BASE_URL` or `RESEND_API_KEY` is missing outside tests.

- [ ] **Step 5: Run and commit**

```bash
npm --workspace @nev/web test -- subscription-token.test.ts ai-confirmation-email.test.ts
git add packages/web/lib packages/web/.env.local.example
git commit -m "feat(subscription): add one-time confirmation email"
```

### Task 3: Enforce Turnstile and durable rate limits

**Files:**
- Modify: `packages/web/lib/turnstile.ts`
- Create: `packages/web/lib/turnstile.test.ts`
- Create: `packages/web/lib/rate-limit.ts`
- Create: `packages/web/lib/rate-limit.test.ts`
- Modify: `packages/web/.env.local.example`

**Interfaces:**
- `verifyTurnstile(token: string, remoteIp: string | null): Promise<boolean>`.
- `checkSubscriptionRateLimit(input: { ipHash: string; emailHash: string; now: Date }): Promise<{ allowed: boolean; retryAfterSeconds: number }>`.
- Production limits: five attempts per IP per 15 minutes and three attempts per email per hour; block the exceeded key until its window ends.

- [ ] **Step 1: Add failing abuse tests**

Cover valid/invalid Turnstile responses, upstream timeout, missing production secret, IP threshold, email threshold, window rollover, and storage failure. Storage failure must reject the request, not fail open.

- [ ] **Step 2: Run and observe failure**

```bash
npm --workspace @nev/web test -- turnstile.test.ts rate-limit.test.ts
```

- [ ] **Step 3: Make Turnstile production-fail-closed**

POST to Cloudflare `siteverify` with `secret`, `response`, and `remoteip`. Use an abort timeout. Return false on invalid response or timeout. Permit an explicit `TURNSTILE_TEST_BYPASS=true` only when `NODE_ENV === "test"`.

- [ ] **Step 4: Implement limiter storage**

Use a database RPC or transaction-safe upsert so concurrent requests cannot reset counters. Derive `ipHash` and `emailHash` with HMAC-SHA-256 and `SUBSCRIPTION_HASH_SECRET`; never store raw identifiers. Return `Retry-After` seconds when blocked.

- [ ] **Step 5: Verify and commit**

```bash
npm --workspace @nev/web test -- turnstile.test.ts rate-limit.test.ts
git add packages/web/lib/turnstile.ts packages/web/lib/turnstile.test.ts packages/web/lib/rate-limit.ts packages/web/lib/rate-limit.test.ts packages/web/.env.local.example
git commit -m "feat(subscription): enforce abuse controls"
```

### Task 4: Replace immediate activation with pending confirmation

**Files:**
- Modify: `packages/web/app/api/ai/subscribe/route.ts`
- Create: `packages/web/app/api/ai/subscribe/route.test.ts`
- Create: `packages/web/lib/feature-flags.ts`
- Create: `packages/web/lib/feature-flags.test.ts`
- Modify: `packages/web/components/ai-subscribe-form.tsx`
- Create: `packages/web/components/ai-subscribe-form.test.tsx`
- Modify: `packages/web/app/page.tsx`
- Modify: `packages/web/.env.local.example`

**Interfaces:**
- Request JSON: `{ email: string; turnstileToken: string; utm?: { source?: string; medium?: string; campaign?: string } }`.
- Success response for all non-error account states: HTTP 202 `{ ok: true, message: "check_email" }`.
- Abuse response: HTTP 429 with `Retry-After`.
- Invalid Turnstile: HTTP 400 `{ error: "verification_failed" }`.
- Disabled response: HTTP 503 `{ error: "subscriptions_disabled" }` without database, Turnstile, or email calls.

- [ ] **Step 1: Write failing route tests**

Cover disabled signup, new email, already pending email, active email, unsubscribed email, invalid body, invalid Turnstile, rate-limited IP/email, database error, and email-send failure. Assert that no path writes `status='active'` and that the public response does not reveal whether the email exists.

- [ ] **Step 2: Run the focused tests**

```bash
npm --workspace @nev/web test -- app/api/ai/subscribe/route.test.ts
```

- [ ] **Step 3: Implement the route**

Use one server-only `subscriptionsEnabled()` helper that is true only for the exact string `"true"`. Check it before parsing or external calls. When enabled, order operations as: parse → identify client IP → verify Turnstile → hash limiter keys → consume rate-limit attempt → create token → upsert pending state and UTM → send confirmation email → return uniform 202. For an active email, do not downgrade it and do not send another welcome email; return the same 202 response.

If sending confirmation fails, retain pending state for a bounded retry and return 503 without exposing account state. Never return the unsubscribe token.

- [ ] **Step 4: Update the form**

Have the homepage call the same server-only feature flag and pass the boolean into the client component. Render a disabled notice instead of the form when `subscriptionsEnabled=false`. When enabled, render the official Turnstile widget with `NEXT_PUBLIC_TURNSTILE_SITE_KEY`, include the token in the request, reset the widget after failure, and show “请查收确认邮件” only after HTTP 202. Remove the hold-to-verify security claim. Add `SUBSCRIPTIONS_ENABLED=false` to the environment example.

- [ ] **Step 5: Verify and commit**

```bash
npm --workspace @nev/web test -- app/api/ai/subscribe/route.test.ts components/ai-subscribe-form.test.tsx lib/feature-flags.test.ts
npm --workspace @nev/web run typecheck
git add packages/web/app/api/ai/subscribe packages/web/lib/feature-flags.ts packages/web/lib/feature-flags.test.ts packages/web/components/ai-subscribe-form.tsx packages/web/components/ai-subscribe-form.test.tsx packages/web/app/page.tsx packages/web/.env.local.example
git commit -m "feat(subscription): require email confirmation"
```

### Task 5: Add explicit confirmation and safe unsubscribe/rating flows

**Files:**
- Create: `packages/web/app/confirm/page.tsx`
- Create: `packages/web/app/confirm/actions.ts`
- Create: `packages/web/app/confirm/confirm.test.tsx`
- Modify: `packages/web/app/unsubscribe/page.tsx`
- Create: `packages/web/app/unsubscribe/actions.ts`
- Modify: `packages/web/app/api/unsubscribe/route.ts`
- Modify: `packages/web/app/api/ai/rate/route.ts`
- Create: `packages/web/app/rate/page.tsx`
- Create: `packages/web/app/rate/actions.ts`
- Create: `packages/web/app/safety-actions.test.ts`

**Interfaces:**
- GET `/confirm?token=...`, `/unsubscribe?token=...`, and `/rate?delivery=...&score=...` render only.
- Server actions perform user-confirmed POST mutations.
- RFC 8058 `POST /api/unsubscribe?token=...` remains an intentional one-click mutation for mailbox providers.

- [ ] **Step 1: Write failing scanner-safety tests**

Assert that rendering each GET page performs select-only calls. Assert confirmation POST activates exactly once, unsubscribe POST records `status='unsubscribed'` and `unsubscribed_at`, and rating POST upserts only scores 1–3.

- [ ] **Step 2: Run and observe the current GET mutation failure**

```bash
npm --workspace @nev/web test -- app/safety-actions.test.ts app/confirm/confirm.test.tsx
```

- [ ] **Step 3: Implement atomic confirmation**

Hash the raw token and call `confirm_ai_subscription`. On success, send the welcome email. Replayed, expired, or unknown tokens show the same invalid/expired state and never reveal an email address.

- [ ] **Step 4: Convert unsubscribe and rating to confirmation POSTs**

Keep the RFC 8058 API POST. Remove all database writes from page rendering. Remove NEV product branching from the new AIVIZENS page behavior; Phase 4 will remove the remaining compatibility code.

- [ ] **Step 5: Verify and commit**

```bash
npm --workspace @nev/web test -- app/safety-actions.test.ts app/confirm/confirm.test.tsx
npm --workspace @nev/web run typecheck
git add packages/web/app/confirm packages/web/app/unsubscribe packages/web/app/rate packages/web/app/api/unsubscribe packages/web/app/api/ai/rate
git commit -m "fix(web): require explicit subscription actions"
```

### Task 6: Add database and browser acceptance coverage

**Files:**
- Create: `packages/web/test/integration/ai-subscription.integration.test.ts`
- Create: `packages/web/e2e/ai-subscription.spec.ts`
- Modify: `packages/web/playwright.config.ts`
- Modify: `.github/workflows/test.yml`
- Create: `docs/runbooks/subscription-operations.md`

**Interfaces:**
- Integration tests use an isolated Supabase/Postgres target and a fake Resend transport.
- Browser tests use Turnstile's documented test key only in the test environment.

- [ ] **Step 1: Write the integration lifecycle test**

Exercise `new → pending_confirmation → active → unsubscribed → pending_confirmation → active`, token expiry, token replay, active-only delivery selection, and concurrent rate-limit increments.

- [ ] **Step 2: Write the browser lifecycle test**

Submit a fresh email, observe the check-email screen, extract the fake transport confirmation URL, confirm, observe welcome state, then unsubscribe through an explicit form submission.

- [ ] **Step 3: Document operational recovery**

Document resend-confirmation behavior, rate-limit inspection, Turnstile outage behavior, and how to disable the public form without deleting subscriber data. Do not include secrets.

- [ ] **Step 4: Run the phase gate**

```bash
make verify
npm --workspace @nev/web run test:integration
npm --workspace @nev/web run test:e2e -- ai-subscription.spec.ts
```

- [ ] **Step 5: Commit**

```bash
git add packages/web/test packages/web/e2e packages/web/playwright.config.ts .github/workflows/test.yml docs/runbooks/subscription-operations.md
git commit -m "test(subscription): cover double opt-in lifecycle"
```

## Phase 1 Gate

Verify in an isolated environment:

```bash
make verify
npm --workspace @nev/web run test:integration
npm --workspace @nev/web run test:e2e -- ai-subscription.spec.ts
```

Expected: a new or resubscribing address remains `pending_confirmation` until one valid POST confirmation; GET requests do not mutate; only `active` subscribers can be selected for delivery; abuse controls fail closed. Do not start Phase 2 until this gate passes.
