import { NextResponse } from "next/server";

export const runtime = "nodejs";

const UUID_RE =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

/**
 * GET /api/ai/rate?d=<delivery_uuid>&s=<1|2|3>
 * Compatibility redirect for links in already-sent email. The destination GET
 * renders a confirmation form; only its explicit server-action POST may write.
 */
export async function GET(req: Request) {
  const url = new URL(req.url);
  const deliveryId = url.searchParams.get("d") ?? "";
  const scoreRaw = url.searchParams.get("s") ?? "";
  const score = Number(scoreRaw);
  const destination = new URL("/rate", url);

  if (!UUID_RE.test(deliveryId) || ![1, 2, 3].includes(score)) {
    destination.searchParams.set("status", "invalid");
  } else {
    destination.searchParams.set("delivery", deliveryId);
    destination.searchParams.set("score", String(score));
  }
  return NextResponse.redirect(destination, 307);
}
