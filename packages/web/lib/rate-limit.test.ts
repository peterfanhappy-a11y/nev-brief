import { createHmac } from "node:crypto";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const { getSupabaseAdminMock, rpcMock } = vi.hoisted(() => ({
  getSupabaseAdminMock: vi.fn(),
  rpcMock: vi.fn(),
}));

vi.mock("./supabase", () => ({
  getSupabaseAdmin: getSupabaseAdminMock,
}));

import {
  checkSubscriptionRateLimit,
  hashSubscriptionRateLimitKey,
} from "./rate-limit";

const IP_HASH = "a".repeat(64);
const EMAIL_HASH = "b".repeat(64);
const NOW = new Date("2026-08-03T01:00:00.000Z");

describe("subscription rate limiting", () => {
  beforeEach(() => {
    getSupabaseAdminMock.mockReturnValue({ rpc: rpcMock });
    vi.stubEnv("SUBSCRIPTION_HASH_SECRET", "unit-test-rate-limit-secret");
  });

  afterEach(() => {
    vi.unstubAllEnvs();
    vi.clearAllMocks();
  });

  it("allows an attempt below both durable thresholds", async () => {
    rpcMock.mockResolvedValue({
      data: [{ allowed: true, retry_after_seconds: 0 }],
      error: null,
    });

    await expect(
      checkSubscriptionRateLimit({ ipHash: IP_HASH, emailHash: EMAIL_HASH, now: NOW }),
    ).resolves.toEqual({ allowed: true, retryAfterSeconds: 0 });

    expect(rpcMock).toHaveBeenCalledWith("check_ai_subscription_rate_limit", {
      ip_hash: IP_HASH,
      email_hash: EMAIL_HASH,
      now_at: "2026-08-03T01:00:00.000Z",
    });
  });

  it.each([
    ["sixth IP attempt in fifteen minutes", 899],
    ["fourth email attempt in one hour", 3599],
  ])("blocks the %s and returns its remaining window", async (_caseName, retryAfterSeconds) => {
    rpcMock.mockResolvedValue({
      data: [{ allowed: false, retry_after_seconds: retryAfterSeconds }],
      error: null,
    });

    await expect(
      checkSubscriptionRateLimit({ ipHash: IP_HASH, emailHash: EMAIL_HASH, now: NOW }),
    ).resolves.toEqual({ allowed: false, retryAfterSeconds });
  });

  it("allows the first attempt after the database rolls both windows over", async () => {
    rpcMock.mockResolvedValue({
      data: [{ allowed: true, retry_after_seconds: 0 }],
      error: null,
    });

    await expect(
      checkSubscriptionRateLimit({
        ipHash: IP_HASH,
        emailHash: EMAIL_HASH,
        now: new Date("2026-08-03T02:00:00.000Z"),
      }),
    ).resolves.toEqual({ allowed: true, retryAfterSeconds: 0 });
  });

  it("fails closed when durable storage rejects the attempt", async () => {
    vi.stubEnv("AIVIZENS_DISPOSABLE_STACK", "true");
    const errorSpy = vi.spyOn(console, "error").mockImplementation(() => undefined);
    rpcMock.mockResolvedValue({
      data: null,
      error: { message: "database unavailable" },
    });

    await expect(
      checkSubscriptionRateLimit({ ipHash: IP_HASH, emailHash: EMAIL_HASH, now: NOW }),
    ).rejects.toThrow("Subscription rate-limit storage failed");
    expect(errorSpy).toHaveBeenCalledWith(
      "[test rate-limit RPC failure]",
      expect.objectContaining({
        hasError: true,
        dataKind: "null",
        rowCount: null,
      }),
    );
  });

  it("rejects non-hash identifiers before they can enter the database payload", async () => {
    await expect(
      checkSubscriptionRateLimit({
        ipHash: "203.0.113.8",
        emailHash: "reader@example.com",
        now: NOW,
      }),
    ).rejects.toThrow("hashed identifiers");
    expect(rpcMock).not.toHaveBeenCalled();
  });

  it("derives deterministic HMAC-SHA-256 keys without exposing the identifier", () => {
    const rawIdentifier = " Reader@Example.com ";
    const expected = createHmac("sha256", "unit-test-rate-limit-secret")
      .update(rawIdentifier)
      .digest("hex");

    expect(hashSubscriptionRateLimitKey(rawIdentifier)).toBe(expected);
    expect(hashSubscriptionRateLimitKey(rawIdentifier)).toMatch(/^[0-9a-f]{64}$/);
    expect(hashSubscriptionRateLimitKey(rawIdentifier)).not.toContain(rawIdentifier);
  });

  it("refuses to hash identifiers without the server-side HMAC secret", () => {
    vi.stubEnv("SUBSCRIPTION_HASH_SECRET", "");

    expect(() => hashSubscriptionRateLimitKey("reader@example.com")).toThrow(
      "SUBSCRIPTION_HASH_SECRET",
    );
  });
});
