import { NextResponse } from "next/server";
import { z } from "zod";
import { getSupabaseAdmin } from "@/lib/supabase";
import { sendAiWelcomeEmail } from "@/lib/ai-welcome-email";

export const runtime = "nodejs";

// AI 趋势订阅：不用 Cloudflare Turnstile — 前端用 hold-to-verify modal
// (15s 长按 + 二次点击) 挡住自动化脚本；如未来遭遇滥用可再加 IP rate limit。
const Body = z.object({
  email: z.string().email().toLowerCase().trim().max(254),
});

export async function POST(req: Request) {
  let body;
  try {
    body = Body.parse(await req.json());
  } catch {
    return NextResponse.json({ error: "invalid_body" }, { status: 400 });
  }

  const sb = getSupabaseAdmin();

  const { data: existing, error: lookupErr } = await sb
    .from("ai_subscribers")
    .select("id, unsubscribe_token, status")
    .eq("email", body.email)
    .maybeSingle();

  if (lookupErr) {
    console.error("[ai/subscribe] lookup failed", lookupErr);
    return NextResponse.json({ error: "db" }, { status: 500 });
  }

  let unsubscribeToken: string;
  let resubscribed = false;

  if (existing) {
    if (existing.status !== "active") {
      const { error } = await sb
        .from("ai_subscribers")
        .update({ status: "active" })
        .eq("id", existing.id);
      if (error) {
        console.error("[ai/subscribe] reactivate failed", error);
        return NextResponse.json({ error: "db" }, { status: 500 });
      }
      resubscribed = true;
    }
    unsubscribeToken = existing.unsubscribe_token;
  } else {
    const { data, error } = await sb
      .from("ai_subscribers")
      .insert({
        email: body.email,
        status: "active",
        source: "ai_landing",
      })
      .select("id, unsubscribe_token")
      .single();
    if (error || !data) {
      console.error("[ai/subscribe] insert failed", error);
      return NextResponse.json({ error: "db" }, { status: 500 });
    }
    unsubscribeToken = data.unsubscribe_token;
  }

  sendAiWelcomeEmail(body.email, unsubscribeToken).catch((err) => {
    console.error("[ai/subscribe] welcome email failed", err);
  });

  return NextResponse.json({ ok: true, resubscribed });
}
