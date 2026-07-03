import { NextResponse } from "next/server";
import { getSupabaseAdmin } from "@/lib/supabase";

export const runtime = "nodejs";

const UUID_RE =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

function page(msg: string): NextResponse {
  const html = `<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>AIVIZENS</title></head>
<body style="margin:0;font-family:-apple-system,'PingFang SC',sans-serif;background:#f4f5f7;">
<div style="max-width:480px;margin:80px auto;background:#fff;border-radius:12px;padding:40px;text-align:center;">
  <div style="font-size:40px;margin-bottom:16px;">🙌</div>
  <div style="font-size:18px;font-weight:600;color:#111;">${msg}</div>
  <div style="margin-top:20px;"><a href="https://aivizens.com" style="color:#4F46E5;text-decoration:none;font-size:14px;">返回 AIVIZENS →</a></div>
</div></body></html>`;
  return new NextResponse(html, {
    status: 200,
    headers: { "Content-Type": "text/html; charset=utf-8" },
  });
}

/**
 * GET /api/ai/rate?d=<delivery_uuid>&s=<1|2|3>
 * 邮件末尾评分模块。delivery_id 是每封邮件唯一随机 uuid（同 unsubscribe_token
 * 信任模型），无需额外鉴权。后点覆盖先点（upsert on delivery_id）。
 * 未知 delivery_id 也回 200「感谢」文案，避免向扫描器泄露有效性。
 */
export async function GET(req: Request) {
  const url = new URL(req.url);
  const deliveryId = url.searchParams.get("d") ?? "";
  const scoreRaw = url.searchParams.get("s") ?? "";
  const score = Number(scoreRaw);

  if (!UUID_RE.test(deliveryId) || ![1, 2, 3].includes(score)) {
    return page("感谢你的反馈！");
  }

  const sb = getSupabaseAdmin();
  const { error } = await sb
    .from("ai_ratings")
    .upsert(
      { delivery_id: deliveryId, score, rated_at: new Date().toISOString() },
      { onConflict: "delivery_id" },
    );
  if (error) {
    // FK 违约（未知 delivery_id）或其他 DB 错误 — 仍回 200 感谢文案
    console.warn("[ai/rate] upsert issue", error.message);
  }

  return page("感谢反馈！你的评分已记录。");
}
