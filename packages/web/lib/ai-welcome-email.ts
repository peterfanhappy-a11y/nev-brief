import { Resend } from "resend";

const FROM_EMAIL = process.env.RESEND_FROM_EMAIL || "onboarding@resend.dev";

export async function sendAiWelcomeEmail(
  to: string,
  unsubscribeToken: string,
): Promise<void> {
  const apiKey = process.env.RESEND_API_KEY;
  if (!apiKey) {
    console.warn("[resend/ai] RESEND_API_KEY missing — skip welcome email");
    return;
  }

  const baseUrl = process.env.WEB_BASE_URL || "http://localhost:3002";
  const unsubUrl = `${baseUrl}/unsubscribe?token=${unsubscribeToken}&product=ai`;

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
  await resend.emails.send({
    from: `AIVIZENS <${FROM_EMAIL}>`,
    to,
    subject: "欢迎加入 AIVIZENS · 每日 5 分钟学会 AI",
    html,
    text,
  });
}
