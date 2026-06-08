import { NextResponse } from "next/server";
import { z } from "zod";
import { getSupabaseAdmin } from "@/lib/supabase";

export const runtime = "nodejs";

const TOPICS = [
  "new_car", "sales", "policy", "tech", "overseas",
  "people", "finance", "recall", "supply_chain",
  "battery_tech", "autonomous_driving", "smart_cockpit",
  "ota_update", "chassis", "exterior_design",
] as const;

const PUSH_TIMES = ["07:30", "08:00", "09:00"] as const;
const UUID_RE =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

const Body = z.object({
  token: z.string().regex(UUID_RE),
  brands: z.array(z.string().trim().min(1).max(40)).max(50),
  topics: z.array(z.enum(TOPICS)).max(15),
  push_time: z.enum(PUSH_TIMES),
});

export async function PATCH(req: Request) {
  let body;
  try {
    body = Body.parse(await req.json());
  } catch {
    return NextResponse.json({ error: "invalid_body" }, { status: 400 });
  }

  const sb = getSupabaseAdmin();
  const { data: sub, error: lookupErr } = await sb
    .from("subscribers")
    .select("id")
    .eq("unsubscribe_token", body.token)
    .maybeSingle();

  if (lookupErr) {
    console.error("[preferences] lookup", lookupErr);
    return NextResponse.json({ error: "db" }, { status: 500 });
  }
  if (!sub) {
    return NextResponse.json({ error: "not_found" }, { status: 404 });
  }

  const { error: subErr } = await sb
    .from("subscribers")
    .update({ push_time: body.push_time })
    .eq("id", sub.id);
  if (subErr) {
    console.error("[preferences] update push_time", subErr);
    return NextResponse.json({ error: "db" }, { status: 500 });
  }

  const { error: prefErr } = await sb
    .from("subscriber_preferences")
    .upsert(
      {
        subscriber_id: sub.id,
        brands: body.brands,
        topics: body.topics,
        regions: [],
      },
      { onConflict: "subscriber_id" },
    );
  if (prefErr) {
    console.error("[preferences] upsert prefs", prefErr);
    return NextResponse.json({ error: "db" }, { status: 500 });
  }

  return NextResponse.json({ ok: true });
}
