import { Resend } from "resend";

const FROM_EMAIL = process.env.RESEND_FROM_EMAIL || "onboarding@resend.dev";

export async function sendWelcomeEmail(
  to: string,
  unsubscribeToken: string,
): Promise<void> {
  const apiKey = process.env.RESEND_API_KEY;
  if (!apiKey) {
    console.warn("[resend] RESEND_API_KEY missing — skip welcome email");
    return;
  }

  const baseUrl = process.env.WEB_BASE_URL || "http://localhost:3002";
  const unsubUrl = `${baseUrl}/unsubscribe?token=${unsubscribeToken}`;
  const manageUrl = `${baseUrl}/manage?token=${unsubscribeToken}`;

  const html = `<!DOCTYPE html>
<html><head><meta charset="utf-8" /></head>
<body style="margin:0;padding:0;font-family:-apple-system,'PingFang SC',sans-serif;background:#f4f5f7;">
<table align="center" width="560" cellpadding="0" cellspacing="0" style="background:#ffffff;margin:24px auto;border-radius:8px;">
  <tr><td style="background:#0066FF;padding:24px;color:#ffffff;border-radius:8px 8px 0 0;">
    <h2 style="margin:0;font-size:20px;">🚗 欢迎订阅 NEV 早报</h2>
  </td></tr>
  <tr><td style="padding:24px;color:#333;font-size:15px;line-height:1.7;">
    <p>感谢订阅 NEV 早报。</p>
    <p>明天早上 8:00 你会收到第一封早报，包含 <strong>10 条新能源汽车行业精选</strong> + <strong>主要车企日销量数据</strong>。</p>
    <p style="margin-top:24px;">
      需要调整关注车企 / 主题 / 推送时间？
      <a href="${manageUrl}" style="color:#0066FF;">管理订阅 →</a>
    </p>
    <p style="color:#999;font-size:13px;margin-top:32px;">
      不想再收？<a href="${unsubUrl}" style="color:#999;">一键退订</a>
    </p>
  </td></tr>
  <tr><td style="background:#f4f5f7;padding:16px 24px;color:#999;font-size:12px;text-align:center;border-radius:0 0 8px 8px;">
    © 2026 NEV 早报
  </td></tr>
</table>
</body></html>`;

  const text = `🚗 欢迎订阅 NEV 早报

感谢订阅。明天早上 8:00 你会收到第一封早报，包含 10 条新能源汽车行业精选 + 主要车企日销量数据。

管理订阅：${manageUrl}
一键退订：${unsubUrl}

© 2026 NEV 早报`;

  const resend = new Resend(apiKey);
  await resend.emails.send({
    from: `NEV 早报 <${FROM_EMAIL}>`,
    to,
    subject: "欢迎订阅 NEV 早报 · 明早 8 点收到第一封",
    html,
    text,
  });
}
