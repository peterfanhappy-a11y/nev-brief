import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const resendMocks = vi.hoisted(() => ({ send: vi.fn() }));

vi.mock("resend", () => ({
  Resend: vi.fn(() => ({ emails: { send: resendMocks.send } })),
}));

beforeEach(() => {
  vi.resetModules();
  resendMocks.send.mockReset().mockResolvedValue({ id: "email_123" });
  vi.stubEnv("RESEND_FROM_EMAIL", "news@aivizens.test");
  vi.stubEnv("WEB_BASE_URL", "https://aivizens.test");
  vi.stubEnv("RESEND_API_KEY", undefined);
  vi.stubEnv("NODE_ENV", "production");
});

afterEach(() => {
  vi.unstubAllEnvs();
});

describe("AI welcome email", () => {
  it("rejects a missing Resend API key outside tests", async () => {
    const { sendAiWelcomeEmail } = await import("./ai-welcome-email");

    await expect(
      sendAiWelcomeEmail("reader@example.com", "unsubscribe-token"),
    ).rejects.toThrow("RESEND_API_KEY is required");
    expect(resendMocks.send).not.toHaveBeenCalled();
  });

  it("rejects a missing base URL outside tests", async () => {
    vi.stubEnv("RESEND_API_KEY", "production-resend-key");
    vi.stubEnv("WEB_BASE_URL", undefined);
    const { sendAiWelcomeEmail } = await import("./ai-welcome-email");

    await expect(
      sendAiWelcomeEmail("reader@example.com", "unsubscribe-token"),
    ).rejects.toThrow("WEB_BASE_URL is required");
    expect(resendMocks.send).not.toHaveBeenCalled();
  });
});
