import { Resend } from "resend";

const MAX_SEND_ATTEMPTS = 2;
const DELIVERY_ERROR = "AI welcome email delivery failed";

function requiredEmailEnvironment(
  name: "RESEND_API_KEY" | "RESEND_FROM_EMAIL" | "WEB_BASE_URL",
  testFallback: string,
): string {
  const value = process.env[name];
  if (value) return value;
  if (process.env.NODE_ENV === "test") return testFallback;
  throw new Error(`${name} is required to send AI welcome email`);
}

/** Send only after a subscriber has successfully confirmed their email. */
export async function sendAiWelcomeEmail(
  to: string,
  unsubscribeToken: string,
  confirmationTokenHash: string,
): Promise<void> {
  const apiKey = requiredEmailEnvironment("RESEND_API_KEY", "test-resend-key");
  const baseUrl = requiredEmailEnvironment("WEB_BASE_URL", "http://localhost:3002");
  const fromEmail = requiredEmailEnvironment(
    "RESEND_FROM_EMAIL",
    "test-sender@aivizens.invalid",
  );
  const unsubUrl = `${baseUrl}/unsubscribe?token=${unsubscribeToken}&product=ai`;
  const idempotencyKey = `ai-welcome:${confirmationTokenHash}`;

  const html = `<!DOCTYPE html>
<html><head><meta charset="utf-8" /></head>
<body style="margin:0;padding:0;font-family:-apple-system,'PingFang SC',sans-serif;background:#f4f5f7;">
<table align="center" width="560" cellpadding="0" cellspacing="0" style="background:#ffffff;margin:24px auto;border-radius:8px;">
  <tr><td style="background:#4F46E5;padding:24px;color:#ffffff;border-radius:8px 8px 0 0;">
    <h2 style="margin:0;font-size:20px;">⚡ 欢迎加入 AIVIZENS</h2>
  </td></tr>
  <tr><td style="padding:24px;color:#333;font-size:15px;line-height:1.7;">
    <p>感谢订阅 <strong>AIVIZENS · AI 趋势</strong>。</p>
    <p>每天 5 分钟，让你了解最新 AI 资讯、行业趋势与实用工具，弄清为什么重要，学习如何应用到工作中。</p>
    <p>第一封日报会在明早送达，敬请查收。</p>
    <p style="color:#999;font-size:13px;margin-top:32px;">
      不想再收？<a href="${unsubUrl}" style="color:#999;">一键退订</a>
    </p>
  </td></tr>
  <tr><td style="background:#f4f5f7;padding:16px 24px;color:#999;font-size:12px;text-align:center;border-radius:0 0 8px 8px;">
    © 2026 AIVIZENS
  </td></tr>
</table>
</body></html>`;

  const text = `⚡ 欢迎加入 AIVIZENS

感谢订阅 AIVIZENS · AI 趋势。

每天 5 分钟，让你了解最新 AI 资讯、行业趋势与实用工具，弄清为什么重要，学习如何应用到工作中。第一封日报会在明早送达。

一键退订：${unsubUrl}

© 2026 AIVIZENS`;

  const resend = new Resend(apiKey);
  const message = {
    from: `AIVIZENS 趋势 <${fromEmail}>`,
    to,
    subject: "欢迎加入 AIVIZENS · 每日 5 分钟学会 AI",
    html,
    text,
  };

  for (let attempt = 0; attempt < MAX_SEND_ATTEMPTS; attempt += 1) {
    try {
      const result = await resend.emails.send(message, { idempotencyKey });
      if (result.error === null && result.data) return;
    } catch {
      // Retry once with the same hash-only idempotency key. Provider details
      // may contain recipient data, so never surface the rejected error.
    }
  }

  throw new Error(DELIVERY_ERROR);
}
