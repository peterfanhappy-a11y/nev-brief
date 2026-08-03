import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const resendMocks = vi.hoisted(() => ({ send: vi.fn() }));

vi.mock("resend", () => ({
  Resend: vi.fn(() => ({ emails: { send: resendMocks.send } })),
}));

beforeEach(() => {
  vi.resetModules();
  resendMocks.send.mockReset().mockResolvedValue({ id: "email_123" });
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
});
