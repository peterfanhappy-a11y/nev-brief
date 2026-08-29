import { execFileSync } from "node:child_process";
import { randomUUID } from "node:crypto";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { createClient } from "@supabase/supabase-js";
import { afterAll, beforeAll, describe, expect, it } from "vitest";
import WebSocket from "ws";
import { POST as subscribe } from "@/app/api/ai/subscribe/route";
import { confirmSubscriptionAction } from "@/app/confirm/actions";
import { unsubscribeAction } from "@/app/unsubscribe/actions";

interface CapturedEmail {
  id: string;
  body: {
    to: string;
    subject: string;
    html: string;
    text: string;
  };
  idempotencyKey: string | null;
}

interface SubscriberRow {
  id: string;
  email: string;
  status: "pending_confirmation" | "active" | "unsubscribed";
  confirmation_token_hash: string | null;
  confirmation_expires_at: string | null;
  confirmed_at: string | null;
  unsubscribed_at: string | null;
  unsubscribe_token: string;
}

const SUCCESS = { ok: true, message: "check_email" };
const ZERO_UUID = "00000000-0000-0000-0000-000000000000";
const SHA256_HEX = /^[0-9a-f]{64}$/;
const CONFIRMATION_URL = /https?:\/\/[^\s<]+\/confirm\?token=([^\s<]+)/;
function requiredEnvironment(name: string): string {
  const value = process.env[name];
  if (!value) {
    throw new Error(`subscription integration stack is missing ${name}`);
  }
  return value;
}

const fakeResendUrl = requiredEnvironment("RESEND_BASE_URL");
const supabaseUrl = requiredEnvironment("SUPABASE_URL");
const serviceRoleKey = requiredEnvironment("SUPABASE_SERVICE_ROLE_KEY");
const databaseUrl = requiredEnvironment("DATABASE_URL");

let lastPostgrestFailure: {
  method: string;
  pathname: string;
  status: number;
  statusText: string;
} | null = null;

async function diagnosticFetch(input: RequestInfo | URL, init?: RequestInit) {
  const response = await fetch(input, init);
  if (!response.ok) {
    const url = new URL(input instanceof Request ? input.url : String(input));
    lastPostgrestFailure = {
      method: init?.method ?? (input instanceof Request ? input.method : "GET"),
      pathname: url.pathname,
      status: response.status,
      statusText: response.statusText,
    };
  }
  return response;
}

const supabase = createClient(supabaseUrl, serviceRoleKey, {
  auth: { persistSession: false, autoRefreshToken: false },
  realtime: { transport: WebSocket as unknown as typeof globalThis.WebSocket },
  global: { fetch: diagnosticFetch },
});

function assertNoSupabaseError(error: unknown, operation: string): void {
  if (!error) return;
  const row = error as Record<string, unknown>;
  const safeError = Object.fromEntries(
    ["name", "code", "message", "details", "hint", "status", "statusText"]
      .filter((key) => ["string", "number", "boolean"].includes(typeof row[key]))
      .map((key) => [key, row[key]]),
  );
  throw new Error(
    `${operation} failed: ${JSON.stringify({
      error: safeError,
      response: lastPostgrestFailure,
    })}`,
  );
}

function request(email: string, ip = "203.0.113.10"): Request {
  return new Request("http://integration.test/api/ai/subscribe", {
    method: "POST",
    headers: {
      "content-type": "application/json",
      "x-forwarded-for": ip,
    },
    body: JSON.stringify({
      email,
      utm: { source: "phase-1", medium: "integration", campaign: "task-6" },
    }),
  });
}

async function submit(email: string, ip?: string) {
  const response = await subscribe(request(email, ip));
  return { status: response.status, body: await response.json() };
}

async function formActionRedirect(
  action: (formData: FormData) => Promise<never>,
  fields: Record<string, string>,
): Promise<string> {
  const formData = new FormData();
  for (const [key, value] of Object.entries(fields)) formData.set(key, value);
  try {
    await action(formData);
  } catch (error) {
    const digest = (error as { digest?: unknown }).digest;
    if (typeof digest === "string" && digest.startsWith("NEXT_REDIRECT;")) {
      return digest;
    }
    throw error;
  }
  throw new Error("server action did not redirect");
}

async function fakeResendRequest(pathname: string, init?: RequestInit) {
  return fetch(`${fakeResendUrl}${pathname}`, init);
}

async function messages(): Promise<CapturedEmail[]> {
  const response = await fakeResendRequest("/_test/messages");
  expect(response.status).toBe(200);
  return response.json();
}

async function deliveryAttempts(): Promise<CapturedEmail[]> {
  const response = await fakeResendRequest("/_test/attempts");
  expect(response.status).toBe(200);
  return response.json();
}

async function clearMessages() {
  const response = await fakeResendRequest("/_test/messages", { method: "DELETE" });
  expect(response.status).toBe(204);
}

async function failNextMessages(count: number) {
  const response = await fakeResendRequest("/_test/fail-next", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ count }),
  });
  expect(response.status).toBe(204);
}

async function subscriber(email: string): Promise<SubscriberRow> {
  const { data, error } = await supabase
    .from("ai_subscribers")
    .select("*")
    .eq("email", email)
    .single();
  assertNoSupabaseError(error, "select subscriber");
  return data as SubscriberRow;
}

function rawConfirmationToken(email: CapturedEmail): string {
  const match = CONFIRMATION_URL.exec(email.body.text);
  expect(match).not.toBeNull();
  return decodeURIComponent(match![1]);
}

function activeSubscribersFromProduction(): Array<{
  id: string;
  email: string;
  unsubscribe_token: string;
}> {
  const here = path.dirname(fileURLToPath(import.meta.url));
  const helper = path.join(here, "fetch-active-subscribers.py");
  const stdout = execFileSync(process.env.PYTHON_BIN ?? "python3", [helper, databaseUrl], {
    cwd: path.resolve(here, "../../../.."),
    encoding: "utf8",
    env: process.env,
  });
  return JSON.parse(stdout);
}

function claimPendingFromProduction(): Array<{ delivery_id: string; email: string }> {
  const here = path.dirname(fileURLToPath(import.meta.url));
  const helper = path.join(here, "claim-pending-deliveries.py");
  const stdout = execFileSync(
    process.env.PYTHON_BIN ?? "python3",
    [helper, databaseUrl],
    {
      cwd: path.resolve(here, "../../../.."),
      encoding: "utf8",
      env: process.env,
    },
  );
  return JSON.parse(stdout);
}

function verifyDeliveryUnsubscribeLock(subscriberId: string): void {
  const here = path.dirname(fileURLToPath(import.meta.url));
  const helper = path.join(here, "verify-delivery-unsubscribe-lock.py");
  execFileSync(
    process.env.PYTHON_BIN ?? "python3",
    [helper, databaseUrl, subscriberId],
    {
      cwd: path.resolve(here, "../../../.."),
      encoding: "utf8",
      env: process.env,
    },
  );
}

describe.sequential("AIVIZENS subscription against PostgreSQL, PostgREST, and fake Resend", () => {
  const runId = `${Date.now()}-${process.pid}`;
  const lifecycleEmail = `lifecycle-${runId}@example.com`;
  const pendingEmail = `pending-${runId}@example.com`;
  const expiredEmail = `expired-${runId}@example.com`;

  beforeAll(async () => {
    const attempts = await supabase
      .from("ai_subscription_attempts")
      .delete()
      .neq("key_hash", "");
    assertNoSupabaseError(attempts.error, "clear limiter rows");
    const subscribers = await supabase
      .from("ai_subscribers")
      .delete()
      .neq("id", ZERO_UUID);
    assertNoSupabaseError(subscribers.error, "clear subscriber rows");
    await clearMessages();
  });

  afterAll(async () => {
    await clearMessages();
  });

  it("rejects anonymous REST access while the signed service role succeeds", async () => {
    const anonymous = await fetch(
      `${supabaseUrl}/rest/v1/ai_subscribers?select=id&limit=1`,
    );
    expect([401, 403]).toContain(anonymous.status);

    const signed = await supabase.from("ai_subscribers").select("id").limit(1);
    assertNoSupabaseError(signed.error, "select subscribers with signed service role");
  });

  it("moves new -> pending -> active -> unsubscribed -> pending -> active without storing raw tokens", async () => {
    expect(await submit(lifecycleEmail)).toEqual({ status: 202, body: SUCCESS });

    const firstMail = (await messages()).find(
      (mail) => mail.body.to === lifecycleEmail && mail.body.subject.includes("确认订阅"),
    );
    expect(firstMail).toBeDefined();
    const firstRawToken = rawConfirmationToken(firstMail!);
    const firstPending = await subscriber(lifecycleEmail);
    expect(firstPending.status).toBe("pending_confirmation");
    expect(firstPending.confirmation_token_hash).toMatch(SHA256_HEX);
    expect(JSON.stringify(firstPending)).not.toContain(firstRawToken);
    expect(activeSubscribersFromProduction()).toEqual([]);

    expect(
      await formActionRedirect(confirmSubscriptionAction, { token: firstRawToken }),
    ).toContain("/confirm?status=confirmed");
    expect((await subscriber(lifecycleEmail)).status).toBe("active");
    expect(activeSubscribersFromProduction().map((row) => row.email)).toEqual([
      lifecycleEmail,
    ]);

    const active = await subscriber(lifecycleEmail);
    expect(
      await formActionRedirect(unsubscribeAction, {
        token: active.unsubscribe_token,
      }),
    ).toContain("/unsubscribe?status=unsubscribed");
    expect((await subscriber(lifecycleEmail)).status).toBe("unsubscribed");
    expect(activeSubscribersFromProduction()).toEqual([]);

    await clearMessages();
    expect(await submit(lifecycleEmail, "203.0.113.11")).toEqual({
      status: 202,
      body: SUCCESS,
    });
    const secondMail = (await messages()).find(
      (mail) => mail.body.to === lifecycleEmail && mail.body.subject.includes("确认订阅"),
    );
    expect(secondMail).toBeDefined();
    const secondRawToken = rawConfirmationToken(secondMail!);
    expect(secondRawToken).not.toBe(firstRawToken);
    expect((await subscriber(lifecycleEmail)).status).toBe("pending_confirmation");
    expect(JSON.stringify(await subscriber(lifecycleEmail))).not.toContain(secondRawToken);

    expect(
      await formActionRedirect(confirmSubscriptionAction, { token: secondRawToken }),
    ).toContain("/confirm?status=confirmed");
    expect((await subscriber(lifecycleEmail)).status).toBe("active");
  });

  it("keeps the public response identical when confirmation transport fails", async () => {
    await failNextMessages(2);
    const transportFailure = await submit(pendingEmail, "203.0.113.12");
    const existingActive = await submit(lifecycleEmail, "203.0.113.13");

    expect(transportFailure).toEqual({ status: 202, body: SUCCESS });
    expect(existingActive).toEqual(transportFailure);
    expect((await subscriber(pendingEmail)).status).toBe("pending_confirmation");
    expect((await messages()).some((mail) => mail.body.to === pendingEmail)).toBe(false);
    const attempts = (await deliveryAttempts()).filter(
      (attempt) => attempt.body.to === pendingEmail,
    );
    expect(attempts).toHaveLength(2);
    expect(attempts[0].idempotencyKey).not.toBeNull();
    expect(attempts[1].idempotencyKey).toBe(attempts[0].idempotencyKey);
  });

  it("rejects expired and replayed confirmation tokens without changing state", async () => {
    await clearMessages();
    expect(await submit(expiredEmail, "203.0.113.14")).toEqual({
      status: 202,
      body: SUCCESS,
    });
    const expiredMail = (await messages()).find((mail) => mail.body.to === expiredEmail);
    expect(expiredMail).toBeDefined();
    const expiredToken = rawConfirmationToken(expiredMail!);
    const expiryUpdate = await supabase
      .from("ai_subscribers")
      .update({ confirmation_expires_at: "2000-01-01T00:00:00.000Z" })
      .eq("email", expiredEmail);
    assertNoSupabaseError(expiryUpdate.error, "expire confirmation token");

    expect(
      await formActionRedirect(confirmSubscriptionAction, { token: expiredToken }),
    ).toContain("/confirm?status=invalid");
    expect((await subscriber(expiredEmail)).status).toBe("pending_confirmation");

    await clearMessages();
    expect(await submit(pendingEmail, "203.0.113.15")).toEqual({
      status: 202,
      body: SUCCESS,
    });
    const replayMail = (await messages()).find((mail) => mail.body.to === pendingEmail);
    expect(replayMail).toBeDefined();
    const replayToken = rawConfirmationToken(replayMail!);
    expect(
      await formActionRedirect(confirmSubscriptionAction, { token: replayToken }),
    ).toContain("/confirm?status=confirmed");
    expect(
      await formActionRedirect(confirmSubscriptionAction, { token: replayToken }),
    ).toContain("/confirm?status=invalid");
    expect((await subscriber(pendingEmail)).status).toBe("active");
  });

  it("suppresses an already queued delivery when the reader unsubscribes", async () => {
    const active = await subscriber(lifecycleEmail);
    expect(active.status).toBe("active");
    const deliveryId = randomUUID();
    const queued = await supabase.from("ai_deliveries").insert({
      id: deliveryId,
      subscriber_id: active.id,
      brief_date: "2026-08-03",
      subject: "queued before unsubscribe",
      content_html: "<p>queued</p>",
      content_text: "queued",
      status: "pending",
    });
    assertNoSupabaseError(queued.error, "queue delivery before unsubscribe");

    expect(
      await formActionRedirect(unsubscribeAction, {
        token: active.unsubscribe_token,
      }),
    ).toContain("/unsubscribe?status=unsubscribed");
    expect(claimPendingFromProduction()).toEqual([]);

    const suppressed = await supabase
      .from("ai_deliveries")
      .select("status,error,retry_count")
      .eq("id", deliveryId)
      .single();
    assertNoSupabaseError(suppressed.error, "read suppressed delivery");
    expect(suppressed.data).toEqual({
      status: "failed",
      error: "subscriber inactive before claim",
      retry_count: 0,
    });
  });

  it("serializes an in-flight delivery preflight with unsubscribe", async () => {
    const active = await subscriber(pendingEmail);
    expect(active.status).toBe("active");
    verifyDeliveryUnsubscribeLock(active.id);
    expect((await subscriber(pendingEmail)).status).toBe("unsubscribed");
  });

  it("atomically increments concurrent IP and email limiter rows", async () => {
    const suffix = `${runId}`.replace(/\D/g, "").padEnd(64, "0").slice(0, 64);
    const ipHash = `a${suffix.slice(1)}`;
    const emailHash = `b${suffix.slice(1)}`;
    const now = new Date("2026-08-03T00:00:00.000Z").toISOString();

    const calls = await Promise.all(
      Array.from({ length: 10 }, () =>
        supabase.rpc("check_ai_subscription_rate_limit", {
          ip_hash: ipHash,
          email_hash: emailHash,
          now_at: now,
        }),
      ),
    );
    for (const call of calls) {
      assertNoSupabaseError(call.error, "increment concurrent limiter");
    }
    const decisions = calls.flatMap((call) => call.data as Array<{ allowed: boolean }>);
    expect(decisions.filter((decision) => decision.allowed)).toHaveLength(3);
    expect(decisions.filter((decision) => !decision.allowed)).toHaveLength(7);

    const { data, error } = await supabase
      .from("ai_subscription_attempts")
      .select("scope,key_hash,attempt_count")
      .in("key_hash", [ipHash, emailHash])
      .order("scope");
    assertNoSupabaseError(error, "select limiter rows");
    expect(data).toEqual([
      { scope: "email", key_hash: emailHash, attempt_count: 10 },
      { scope: "ip", key_hash: ipHash, attempt_count: 10 },
    ]);
  });
});
