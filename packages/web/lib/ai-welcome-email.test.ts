import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const resendMocks = vi.hoisted(() => ({ send: vi.fn() }));

vi.mock("resend", () => ({
  Resend: vi.fn(() => ({ emails: { send: resendMocks.send } })),
}));

beforeEach(() => {
  vi.resetModules();
  resendMocks.send.mockReset().mockResolvedValue({
    data: { id: "email_123" },
    error: null,
  });
  vi.stubEnv("RESEND_FROM_EMAIL", "news@aivizens.test");
  vi.stubEnv("WEB_BASE_URL", "https://aivizens.test");
  vi.stubEnv("RESEND_API_KEY", undefined);
  vi.stubEnv("NODE_ENV", "production");
});

afterEach(() => {
  vi.unstubAllEnvs();
});

describe("AI welcome email", () => {
  it("uses the confirmation token hash as a stable idempotency key", async () => {
    vi.stubEnv("RESEND_API_KEY", "production-resend-key");
    const { sendAiWelcomeEmail } = await import("./ai-welcome-email");

    await sendAiWelcomeEmail(
      "reader@example.com",
      "11111111-1111-4111-8111-111111111111",
      "a".repeat(64),
    );

    expect(resendMocks.send).toHaveBeenCalledTimes(1);
    expect(resendMocks.send.mock.calls[0][1]).toEqual({
      idempotencyKey: `ai-welcome:${"a".repeat(64)}`,
    });
    expect(JSON.stringify(resendMocks.send.mock.calls)).not.toContain(
      "confirmation-token",
    );
  });

  it("retries one resolved SDK error with the same idempotency key", async () => {
    vi.stubEnv("RESEND_API_KEY", "production-resend-key");
    resendMocks.send
      .mockResolvedValueOnce({
        data: null,
        error: { message: "provider leaked reader@example.com" },
      })
      .mockResolvedValueOnce({ data: { id: "email_456" }, error: null });
    const { sendAiWelcomeEmail } = await import("./ai-welcome-email");

    await expect(
      sendAiWelcomeEmail("reader@example.com", "unsubscribe-token", "b".repeat(64)),
    ).resolves.toBeUndefined();

    expect(resendMocks.send).toHaveBeenCalledTimes(2);
    expect(resendMocks.send.mock.calls[1][1]).toEqual(
      resendMocks.send.mock.calls[0][1],
    );
  });

  it.each(["resolved", "rejected"])(
    "throws one static error after two %s SDK failures",
    async (failureMode) => {
      vi.stubEnv("RESEND_API_KEY", "production-resend-key");
      if (failureMode === "resolved") {
        resendMocks.send.mockResolvedValue({
          data: null,
          error: { message: "provider leaked reader@example.com private-token" },
        });
      } else {
        resendMocks.send.mockRejectedValue(
          new Error("provider rejected reader@example.com private-token"),
        );
      }
      const { sendAiWelcomeEmail } = await import("./ai-welcome-email");

      const failure = await sendAiWelcomeEmail(
        "reader@example.com",
        "private-token",
        "c".repeat(64),
      ).catch((error: unknown) => error);

      expect(resendMocks.send).toHaveBeenCalledTimes(2);
      expect(failure).toBeInstanceOf(Error);
      expect((failure as Error).message).toBe("AI welcome email delivery failed");
      expect((failure as Error).message).not.toMatch(
        /reader@example\.com|private-token|provider/,
      );
    },
  );

  it("rejects a missing Resend API key outside tests", async () => {
    const { sendAiWelcomeEmail } = await import("./ai-welcome-email");

    await expect(
      sendAiWelcomeEmail("reader@example.com", "unsubscribe-token", "d".repeat(64)),
    ).rejects.toThrow("RESEND_API_KEY is required");
    expect(resendMocks.send).not.toHaveBeenCalled();
  });

  it("rejects a missing base URL outside tests", async () => {
    vi.stubEnv("RESEND_API_KEY", "production-resend-key");
    vi.stubEnv("WEB_BASE_URL", undefined);
    const { sendAiWelcomeEmail } = await import("./ai-welcome-email");

    await expect(
      sendAiWelcomeEmail("reader@example.com", "unsubscribe-token", "d".repeat(64)),
    ).rejects.toThrow("WEB_BASE_URL is required");
    expect(resendMocks.send).not.toHaveBeenCalled();
  });

  it("rejects a missing sender address outside tests", async () => {
    vi.stubEnv("RESEND_API_KEY", "production-resend-key");
    vi.stubEnv("RESEND_FROM_EMAIL", undefined);
    const { sendAiWelcomeEmail } = await import("./ai-welcome-email");

    await expect(
      sendAiWelcomeEmail("reader@example.com", "unsubscribe-token", "d".repeat(64)),
    ).rejects.toThrow("RESEND_FROM_EMAIL is required");
    expect(resendMocks.send).not.toHaveBeenCalled();
  });
});
