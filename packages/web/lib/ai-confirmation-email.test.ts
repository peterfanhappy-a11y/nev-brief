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
  vi.stubEnv("RESEND_API_KEY", "test-resend-key");
  vi.stubEnv("RESEND_FROM_EMAIL", "news@aivizens.test");
  vi.stubEnv("WEB_BASE_URL", "https://aivizens.test");
  vi.stubEnv("NODE_ENV", "test");
});

afterEach(() => {
  vi.unstubAllEnvs();
});

describe("AI confirmation email", () => {
  it("sends one 24-hour confirmation message with an encoded token link", async () => {
    const { sendAiConfirmationEmail } = await import("./ai-confirmation-email");

    await sendAiConfirmationEmail("reader@example.com", "token /?&=");

    expect(resendMocks.send).toHaveBeenCalledTimes(1);
    const [message] = resendMocks.send.mock.calls[0];
    expect(message).toMatchObject({
      from: "AIVIZENS 趋势 <news@aivizens.test>",
      to: "reader@example.com",
    });
    expect(message.subject).toContain("确认");
    expect(message.html).toContain(
      "https://aivizens.test/confirm?token=token%20%2F%3F%26%3D",
    );
    expect(message.text).toContain(
      "https://aivizens.test/confirm?token=token%20%2F%3F%26%3D",
    );
    expect(message.html).toContain("24 小时");
    expect(message.text).toContain("24 小时");
    expect(message.html).not.toContain("已经订阅");
    expect(message.text).not.toContain("已经订阅");
    expect(resendMocks.send.mock.calls[0][1]).toEqual({
      idempotencyKey:
        "ai-confirmation:df82b2735b0097dd84597d56ee7e9ae66a5abac6f83ece8ecc2229f79025c3c1",
    });
  });

  it("retries one resolved SDK error with the same idempotency key", async () => {
    resendMocks.send
      .mockResolvedValueOnce({
        data: null,
        error: { name: "rate_limit_exceeded", message: "retry later" },
      })
      .mockResolvedValueOnce({ data: { id: "email_456" }, error: null });
    const { sendAiConfirmationEmail } = await import("./ai-confirmation-email");

    await expect(
      sendAiConfirmationEmail("reader@example.com", "retry-token"),
    ).resolves.toBeUndefined();

    expect(resendMocks.send).toHaveBeenCalledTimes(2);
    expect(resendMocks.send.mock.calls[0][1]).toEqual({
      idempotencyKey:
        "ai-confirmation:2e4a72e6212a382961b0fc90ab9f037b10d95edd53305d012819d5216051687b",
    });
    expect(resendMocks.send.mock.calls[1][1]).toEqual(
      resendMocks.send.mock.calls[0][1],
    );
  });

  it("throws a static error after two resolved SDK failures", async () => {
    resendMocks.send.mockResolvedValue({
      data: null,
      error: {
        name: "application_error",
        message: "provider leaked reader@example.com and private-token",
      },
    });
    const { sendAiConfirmationEmail } = await import("./ai-confirmation-email");

    const failure = await sendAiConfirmationEmail(
      "reader@example.com",
      "private-token",
    ).catch((error: unknown) => error);

    expect(resendMocks.send).toHaveBeenCalledTimes(2);
    expect(failure).toBeInstanceOf(Error);
    expect((failure as Error).message).toBe("AI confirmation email delivery failed");
    expect((failure as Error).message).not.toMatch(
      /reader@example\.com|private-token|provider leaked/,
    );
  });

  it("throws the same static error after two rejected SDK attempts", async () => {
    resendMocks.send.mockRejectedValue(
      new Error("provider rejected reader@example.com private-token"),
    );
    const { sendAiConfirmationEmail } = await import("./ai-confirmation-email");

    const failure = await sendAiConfirmationEmail(
      "reader@example.com",
      "private-token",
    ).catch((error: unknown) => error);

    expect(resendMocks.send).toHaveBeenCalledTimes(2);
    expect(failure).toBeInstanceOf(Error);
    expect((failure as Error).message).toBe("AI confirmation email delivery failed");
    expect((failure as Error).message).not.toMatch(
      /reader@example\.com|private-token|provider rejected/,
    );
  });

  it("requires a base URL outside tests", async () => {
    vi.stubEnv("WEB_BASE_URL", undefined);
    vi.stubEnv("NODE_ENV", "production");
    const { sendAiConfirmationEmail } = await import("./ai-confirmation-email");

    await expect(
      sendAiConfirmationEmail("reader@example.com", "token"),
    ).rejects.toThrow("WEB_BASE_URL is required");
    expect(resendMocks.send).not.toHaveBeenCalled();
  });

  it("requires a Resend API key outside tests", async () => {
    vi.stubEnv("RESEND_API_KEY", undefined);
    vi.stubEnv("NODE_ENV", "production");
    const { sendAiConfirmationEmail } = await import("./ai-confirmation-email");

    await expect(
      sendAiConfirmationEmail("reader@example.com", "token"),
    ).rejects.toThrow("RESEND_API_KEY is required");
    expect(resendMocks.send).not.toHaveBeenCalled();
  });

  it("requires a sender address outside tests", async () => {
    vi.stubEnv("RESEND_FROM_EMAIL", undefined);
    vi.stubEnv("NODE_ENV", "production");
    const { sendAiConfirmationEmail } = await import("./ai-confirmation-email");

    await expect(
      sendAiConfirmationEmail("reader@example.com", "token"),
    ).rejects.toThrow("RESEND_FROM_EMAIL is required");
    expect(resendMocks.send).not.toHaveBeenCalled();
  });
});
