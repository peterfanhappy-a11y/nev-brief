import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { verifyTurnstile } from "./turnstile";

const fetchMock = vi.fn<typeof fetch>();

describe("verifyTurnstile", () => {
  beforeEach(() => {
    fetchMock.mockReset();
    vi.stubGlobal("fetch", fetchMock);
    vi.stubEnv("NODE_ENV", "production");
    vi.stubEnv("TURNSTILE_SECRET_KEY", "production-turnstile-secret");
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllEnvs();
    vi.unstubAllGlobals();
    vi.clearAllMocks();
  });

  it("accepts a valid Cloudflare response and sends the remote IP", async () => {
    fetchMock.mockResolvedValue(
      new Response(JSON.stringify({ success: true }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );

    await expect(verifyTurnstile("valid-token", "203.0.113.8")).resolves.toBe(true);

    expect(fetchMock).toHaveBeenCalledOnce();
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("https://challenges.cloudflare.com/turnstile/v0/siteverify");
    expect(init?.method).toBe("POST");
    expect(init?.headers).toEqual({
      "Content-Type": "application/x-www-form-urlencoded",
    });
    expect(init?.body?.toString()).toBe(
      "secret=production-turnstile-secret&response=valid-token&remoteip=203.0.113.8",
    );
    expect(init?.signal).toBeInstanceOf(AbortSignal);
  });

  it("rejects an invalid Cloudflare response", async () => {
    fetchMock.mockResolvedValue(
      new Response(JSON.stringify({ success: false, "error-codes": ["invalid-input-response"] }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );

    await expect(verifyTurnstile("invalid-token", null)).resolves.toBe(false);
  });

  it("fails closed when Cloudflare does not respond before the abort timeout", async () => {
    vi.useFakeTimers();
    fetchMock.mockImplementation((_url, init) =>
      new Promise((_resolve, reject) => {
        init?.signal?.addEventListener("abort", () => {
          reject(new DOMException("The operation was aborted", "AbortError"));
        });
      }),
    );

    const result = verifyTurnstile("slow-token", "203.0.113.9");
    await vi.runAllTimersAsync();

    await expect(result).resolves.toBe(false);
  });

  it("throws a configuration error when the production secret is missing", async () => {
    vi.stubEnv("TURNSTILE_SECRET_KEY", "");

    await expect(verifyTurnstile("token", "203.0.113.10")).rejects.toThrow(
      "TURNSTILE_SECRET_KEY is required in production",
    );
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("allows the explicit bypass only in the test environment", async () => {
    vi.stubEnv("TURNSTILE_TEST_BYPASS", "true");
    fetchMock.mockResolvedValue(
      new Response(JSON.stringify({ success: false }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );

    await expect(verifyTurnstile("token", null)).resolves.toBe(false);
    expect(fetchMock).toHaveBeenCalledOnce();
    fetchMock.mockClear();

    vi.stubEnv("NODE_ENV", "test");
    vi.stubEnv("TURNSTILE_SECRET_KEY", "");
    vi.stubEnv("TURNSTILE_TEST_BYPASS", "");
    await expect(verifyTurnstile("token", null)).resolves.toBe(false);

    vi.stubEnv("TURNSTILE_TEST_BYPASS", "true");
    await expect(verifyTurnstile("token", null)).resolves.toBe(true);
    expect(fetchMock).not.toHaveBeenCalled();
  });
});
