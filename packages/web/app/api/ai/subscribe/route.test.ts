import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const RAW_TOKEN = "raw-confirmation-token-must-stay-private";
const TOKEN_HASH = "c".repeat(64);
const IP_HASH = "a".repeat(64);
const EMAIL_HASH = "b".repeat(64);
const UNSUBSCRIBE_TOKEN = "11111111-1111-4111-8111-111111111111";

const mocks = vi.hoisted(() => ({
  hashLimiterKey: vi.fn(),
  checkRateLimit: vi.fn(),
  createToken: vi.fn(),
  sendWelcome: vi.fn(),
  getSupabaseAdmin: vi.fn(),
  rpc: vi.fn(),
}));

vi.mock("@/lib/rate-limit", () => ({
  hashSubscriptionRateLimitKey: mocks.hashLimiterKey,
  checkSubscriptionRateLimit: mocks.checkRateLimit,
}));
vi.mock("@/lib/subscription-token", () => ({
  createConfirmationToken: mocks.createToken,
}));
vi.mock("@/lib/ai-welcome-email", () => ({
  sendAiWelcomeEmail: mocks.sendWelcome,
}));
vi.mock("@/lib/supabase", () => ({
  getSupabaseAdmin: mocks.getSupabaseAdmin,
}));

import { POST } from "./route";

const SUCCESS = { ok: true, message: "subscribed" };

function request(
  body: unknown = {
    email: "Reader@Example.com",
    utm: { source: "launch", medium: "email", campaign: "phase-1" },
  },
): Request {
  return new Request("http://localhost/api/ai/subscribe", {
    method: "POST",
    headers: {
      "content-type": "application/json",
      "x-forwarded-for": "203.0.113.8, 10.0.0.1",
    },
    body: JSON.stringify(body),
  });
}

async function responseBody(response: Response): Promise<unknown> {
  return response.json();
}

describe("POST /api/ai/subscribe", () => {
  let consoleError: ReturnType<typeof vi.spyOn>;

  beforeEach(() => {
    vi.stubEnv("SUBSCRIPTIONS_ENABLED", "true");
    mocks.hashLimiterKey.mockImplementation((value: string) =>
      value === "203.0.113.8" ? IP_HASH : EMAIL_HASH,
    );
    mocks.checkRateLimit.mockResolvedValue({
      allowed: true,
      retryAfterSeconds: 0,
    });
    mocks.createToken.mockReturnValue({ rawToken: RAW_TOKEN, tokenHash: TOKEN_HASH });
    mocks.rpc.mockResolvedValue({
      data: [{ welcome_required: true, unsubscribe_token: UNSUBSCRIBE_TOKEN }],
      error: null,
    });
    mocks.getSupabaseAdmin.mockReturnValue({ rpc: mocks.rpc });
    mocks.sendWelcome.mockResolvedValue(undefined);
    consoleError = vi.spyOn(console, "error").mockImplementation(() => undefined);
  });

  afterEach(() => {
    consoleError.mockRestore();
    vi.unstubAllEnvs();
    vi.clearAllMocks();
  });

  it("short-circuits a disabled signup before body parsing or external calls", async () => {
    vi.stubEnv("SUBSCRIPTIONS_ENABLED", "false");
    const json = vi.fn().mockRejectedValue(new Error("must not parse"));

    const response = await POST({ json, headers: new Headers() } as unknown as Request);

    expect(response.status).toBe(503);
    await expect(responseBody(response)).resolves.toEqual({
      error: "subscriptions_disabled",
    });
    expect(json).not.toHaveBeenCalled();
    expect(mocks.checkRateLimit).not.toHaveBeenCalled();
    expect(mocks.getSupabaseAdmin).not.toHaveBeenCalled();
    expect(mocks.sendWelcome).not.toHaveBeenCalled();
  });

  it.each([
    [{}],
    [{ email: "not-an-email" }],
    [{ email: "reader@example.com", utm: "bad" }],
  ])("rejects an invalid body before rate limiting (%j)", async (body) => {
    const response = await POST(request(body));

    expect(response.status).toBe(400);
    await expect(responseBody(response)).resolves.toEqual({ error: "invalid_body" });
    expect(mocks.checkRateLimit).not.toHaveBeenCalled();
  });

  it("uses the durable limiter without a browser captcha", async () => {
    const response = await POST(request());

    expect(response.status).toBe(202);
    expect(mocks.checkRateLimit).toHaveBeenCalledOnce();
  });

  it.each([
    ["IP", 899],
    ["email", 3599],
  ])("returns Retry-After when the %s limiter blocks the request", async (_scope, retry) => {
    mocks.checkRateLimit.mockResolvedValue({
      allowed: false,
      retryAfterSeconds: retry,
    });

    const response = await POST(request());

    expect(response.status).toBe(429);
    expect(response.headers.get("Retry-After")).toBe(String(retry));
    await expect(responseBody(response)).resolves.toEqual({ error: "rate_limited" });
    expect(mocks.createToken).not.toHaveBeenCalled();
    expect(mocks.getSupabaseAdmin).not.toHaveBeenCalled();
  });

  it("normalizes input, atomically activates the subscription, and sends welcome mail", async () => {
    const response = await POST(request());
    const text = await response.text();

    expect(response.status).toBe(202);
    expect(JSON.parse(text)).toEqual(SUCCESS);
    expect(mocks.hashLimiterKey).toHaveBeenNthCalledWith(1, "203.0.113.8");
    expect(mocks.hashLimiterKey).toHaveBeenNthCalledWith(2, "reader@example.com");
    expect(mocks.checkRateLimit).toHaveBeenCalledWith({
      ipHash: IP_HASH,
      emailHash: EMAIL_HASH,
      now: expect.any(Date),
    });
    expect(mocks.rpc).toHaveBeenCalledWith("activate_ai_subscription", {
      input_email: "reader@example.com",
      input_ip_hash: IP_HASH,
      input_utm: { source: "launch", medium: "email", campaign: "phase-1" },
    });
    expect(mocks.sendWelcome).toHaveBeenCalledWith(
      "reader@example.com",
      UNSUBSCRIBE_TOKEN,
      TOKEN_HASH,
    );

    const dbPayload = JSON.stringify(mocks.rpc.mock.calls);
    expect(dbPayload).not.toContain(RAW_TOKEN);
    expect(text).not.toContain(RAW_TOKEN);
    expect(JSON.stringify(consoleError.mock.calls)).not.toContain(RAW_TOKEN);

    expect(mocks.checkRateLimit.mock.invocationCallOrder[0]).toBeLessThan(
      mocks.rpc.mock.invocationCallOrder[0],
    );
    expect(mocks.rpc.mock.invocationCallOrder[0]).toBeLessThan(
      mocks.createToken.mock.invocationCallOrder[0],
    );
    expect(mocks.createToken.mock.invocationCallOrder[0]).toBeLessThan(
      mocks.sendWelcome.mock.invocationCallOrder[0],
    );
  });

  it.each(["new", "pending", "unsubscribed"])(
    "returns the same public success for a %s email and sends one welcome message",
    async () => {
      const response = await POST(request());
      expect(response.status).toBe(202);
      await expect(responseBody(response)).resolves.toEqual(SUCCESS);
      expect(mocks.sendWelcome).toHaveBeenCalledOnce();
    },
  );

  it("returns the same public success for an active email without sending another welcome", async () => {
    mocks.rpc.mockResolvedValue({
      data: [{ welcome_required: false, unsubscribe_token: UNSUBSCRIBE_TOKEN }],
      error: null,
    });

    const response = await POST(request());

    expect(response.status).toBe(202);
    await expect(responseBody(response)).resolves.toEqual(SUCCESS);
    expect(mocks.createToken).not.toHaveBeenCalled();
    expect(mocks.sendWelcome).not.toHaveBeenCalled();
  });

  it("fails closed when the durable limiter storage fails", async () => {
    mocks.checkRateLimit.mockRejectedValue(new Error("storage unavailable"));

    const response = await POST(request());

    expect(response.status).toBe(500);
    await expect(responseBody(response)).resolves.toEqual({ error: "db" });
    expect(mocks.createToken).not.toHaveBeenCalled();
    expect(mocks.getSupabaseAdmin).not.toHaveBeenCalled();
  });

  it("returns a database error without sending email when atomic activation fails", async () => {
    mocks.rpc.mockResolvedValue({ data: null, error: { message: "db unavailable" } });

    const response = await POST(request());

    expect(response.status).toBe(500);
    await expect(responseBody(response)).resolves.toEqual({ error: "db" });
    expect(mocks.sendWelcome).not.toHaveBeenCalled();
  });

  it.each([
    ["new", true],
    ["pending", true],
    ["unsubscribed", true],
    ["active", false],
  ])(
    "keeps the subscription successful for %s when welcome delivery is unavailable",
    async (_state, welcomeRequired) => {
      mocks.rpc.mockResolvedValue({
        data: [{
          welcome_required: welcomeRequired,
          unsubscribe_token: UNSUBSCRIBE_TOKEN,
        }],
        error: null,
      });
      mocks.sendWelcome.mockRejectedValue(
        new Error(`provider rejected reader@example.com ${RAW_TOKEN}`),
      );

      const response = await POST(request());
      const text = await response.text();

      expect(response.status).toBe(202);
      expect(JSON.parse(text)).toEqual(SUCCESS);
      expect(mocks.rpc).toHaveBeenCalledOnce();
      expect(mocks.sendWelcome).toHaveBeenCalledTimes(welcomeRequired ? 1 : 0);
      expect(text).not.toContain(RAW_TOKEN);
      expect(JSON.stringify(mocks.rpc.mock.calls)).not.toContain(RAW_TOKEN);
      expect(JSON.stringify(consoleError.mock.calls)).not.toContain(RAW_TOKEN);
    },
  );
});
