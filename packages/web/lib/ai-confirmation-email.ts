import { Resend } from "resend";
import { hashConfirmationToken } from "./subscription-token";

const MAX_SEND_ATTEMPTS = 2;
const DELIVERY_ERROR = "AI confirmation email delivery failed";

export class ConfirmationEmailDeliveryError extends Error {
  constructor(
    readonly kind: "configuration" | "provider",
    message: string,
  ) {
    super(message);
  }
}

function requiredEmailEnvironment(
  name: "RESEND_API_KEY" | "RESEND_FROM_EMAIL" | "WEB_BASE_URL",
  testFallback: string,
): string {
  const value = process.env[name];
  if (value) {
    return value;
  }

  if (process.env.NODE_ENV === "test") {
    return testFallback;
  }

  throw new ConfirmationEmailDeliveryError(
    "configuration",
    `${name} is required to send AI confirmation email`,
  );
}

export async function sendAiConfirmationEmail(
  email: string,
  rawToken: string,
): Promise<void> {
  const apiKey = requiredEmailEnvironment("RESEND_API_KEY", "test-resend-key");
  const baseUrl = requiredEmailEnvironment("WEB_BASE_URL", "http://localhost:3002");
  const fromEmail = requiredEmailEnvironment(
    "RESEND_FROM_EMAIL",
    "test-sender@aivizens.invalid",
  );
  const confirmationUrl = `${baseUrl}/confirm?token=${encodeURIComponent(rawToken)}`;
  const idempotencyKey = `ai-confirmation:${hashConfirmationToken(rawToken)}`;

  const html = `<!DOCTYPE html>
<html><head><meta charset="utf-8" /></head>
<body style="margin:0;padding:0;font-family:-apple-system,'PingFang SC',sans-serif;background:#f4f5f7;">
<table align="center" width="560" cellpadding="0" cellspacing="0" style="background:#ffffff;margin:24px auto;border-radius:8px;">
  <tr><td style="background:#4F46E5;padding:24px;color:#ffffff;border-radius:8px 8px 0 0;">
    <h2 style="margin:0;font-size:20px;">确认订阅 AIVIZENS 趋势</h2>
  </td></tr>
  <tr><td style="padding:24px;color:#333;font-size:15px;line-height:1.7;">
    <p>感谢你的订阅请求。请点击下方链接确认你的邮箱地址：</p>
    <p><a href="${confirmationUrl}" style="color:#4F46E5;">确认订阅 AIVIZENS 趋势</a></p>
    <p>此链接将在 24 小时后失效。</p>
    <p>如果不是你发起的订阅请求，无需进行任何操作。</p>
  </td></tr>
  <tr><td style="background:#f4f5f7;padding:16px 24px;color:#999;font-size:12px;text-align:center;border-radius:0 0 8px 8px;">
    © 2026 AIVIZENS 趋势
  </td></tr>
</table>
</body></html>`;

  const text = `确认订阅 AIVIZENS 趋势

感谢你的订阅请求。请打开以下链接确认你的邮箱地址：
${confirmationUrl}

此链接将在 24 小时后失效。如果不是你发起的订阅请求，无需进行任何操作。

© 2026 AIVIZENS 趋势`;

  const resend = new Resend(apiKey);
  const message = {
    from: `AIVIZENS 趋势 <${fromEmail}>`,
    to: email,
    subject: "确认订阅 AIVIZENS 趋势",
    html,
    text,
  };

  for (let attempt = 0; attempt < MAX_SEND_ATTEMPTS; attempt += 1) {
    try {
      const result = await resend.emails.send(message, { idempotencyKey });
      if (result.error === null && result.data) {
        return;
      }
    } catch {
      // Retry once with the same idempotency key. Never surface SDK details,
      // because provider errors may contain recipient or message content.
    }
  }

  throw new ConfirmationEmailDeliveryError("provider", DELIVERY_ERROR);
}
