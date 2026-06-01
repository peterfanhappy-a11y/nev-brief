import { NextResponse } from "next/server";
import { z } from "zod";
import { getSupabaseAdmin } from "@/lib/supabase";
import { verifyTurnstile } from "@/lib/turnstile";
import { sendWelcomeEmail } from "@/lib/resend";

export const runtime = "nodejs";

const TOPICS = [
  "new_car", "sales", "policy", "tech", "overseas",
  "people", "finance", "recall", "supply_chain",
] as const;

const Body = z.object({
  email: z.string().email().toLowerCase().trim().max(254),
  brands: z.array(z.string().max(40)).max(50).default([]),
  topics: z.array(z.enum(TOPICS)).default([]),
  push_time: z.enum(["07:30", "08:00", "09:00"]).default("08:00"),
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
  } catch (e) {
    return NextResponse.json({ error: "invalid_body" }, { status: 400 });
  }

  const ip = getClientIp(req);
  const turnstileOk = await verifyTurnstile(body.turnstile_token, ip);
  if (!turnstileOk) {
    return NextResponse.json({ error: "turnstile_failed" }, { status: 403 });
  }

  const sb = getSupabaseAdmin();

  // Check if subscriber exists (resubscribe case)
  const { data: existing, error: lookupErr } = await sb
    .from("subscribers")
    .select("id, unsubscribe_token, status")
    .eq("email", body.email)
    .maybeSingle();

  if (lookupErr) {
    console.error("[subscribe] lookup failed", lookupErr);
    return NextResponse.json({ error: "db" }, { status: 500 });
  }

  let subscriberId: string;
  let unsubscribeToken: string;

  if (existing) {
    // Resubscribe: reactivate + update push_time
    const { error } = await sb
      .from("subscribers")
      .update({ status: "active", push_time: body.push_time })
      .eq("id", existing.id);
    if (error) {
      console.error("[subscribe] update failed", error);
      return NextResponse.json({ error: "db" }, { status: 500 });
    }
    subscriberId = existing.id;
    unsubscribeToken = existing.unsubscribe_token;
  } else {
    // New subscriber
    const { data, error } = await sb
      .from("subscribers")
      .insert({
        email: body.email,
        status: "active",
        plan: "free",
        push_time: body.push_time,
        push_channel: "email",
      })
      .select("id, unsubscribe_token")
      .single();
    if (error || !data) {
      console.error("[subscribe] insert failed", error);
      return NextResponse.json({ error: "db" }, { status: 500 });
    }
    subscriberId = data.id;
    unsubscribeToken = data.unsubscribe_token;
  }

  // Upsert preferences
  const { error: prefErr } = await sb
    .from("subscriber_preferences")
    .upsert(
      {
        subscriber_id: subscriberId,
        brands: body.brands,
        topics: body.topics,
        regions: [],
      },
      { onConflict: "subscriber_id" },
    );
  if (prefErr) {
    console.error("[subscribe] preferences upsert failed", prefErr);
    // 不阻塞返回 — subscriber 已建好，prefs 可用 /manage 后补
  }

  // Fire-and-forget welcome email
  sendWelcomeEmail(body.email, unsubscribeToken).catch((err) => {
    console.error("[subscribe] welcome email failed", err);
  });

  return NextResponse.json({ ok: true, resubscribed: !!existing });
}
