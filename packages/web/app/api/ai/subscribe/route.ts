import { NextResponse } from "next/server";
import { z } from "zod";
import { getSupabaseAdmin } from "@/lib/supabase";
import { verifyTurnstile } from "@/lib/turnstile";
import { sendAiWelcomeEmail } from "@/lib/ai-welcome-email";

export const runtime = "nodejs";

const Body = z.object({
  email: z.string().email().toLowerCase().trim().max(254),
  turnstile_token: z.string().min(1).max(2048),
});

function getClientIp(req: Request): string {
  return (
    req.headers.get("x-forwarded-for")?.split(",")[0]?.trim() ??
    req.headers.get("x-real-ip") ??
    "unknown"
  );
}

export async function POST(req: Request) {
  let body;
  try {
    body = Body.parse(await req.json());
  } catch {
    return NextResponse.json({ error: "invalid_body" }, { status: 400 });
  }

  const ip = getClientIp(req);
  const turnstileOk = await verifyTurnstile(body.turnstile_token, ip);
  if (!turnstileOk) {
    return NextResponse.json({ error: "turnstile_failed" }, { status: 403 });
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
