import { NextResponse } from "next/server";
import { getSupabaseAdmin } from "@/lib/supabase";
import { parseProduct, subscribersTable } from "@/lib/subscribers";

export const runtime = "nodejs";

const UUID_RE =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

async function unsubscribeByToken(
  token: string,
  productRaw: string | null,
): Promise<{ ok: boolean; status: number; body: string }> {
  if (!UUID_RE.test(token)) {
    return { ok: false, status: 400, body: "invalid_token" };
  }
  const product = parseProduct(productRaw);
  const sb = getSupabaseAdmin();
  const { error } = await sb
    .from(subscribersTable(product))
    .update({ status: "unsubscribed" })
    .eq("unsubscribe_token", token);
  if (error) {
    console.error("[unsubscribe] db error", error);
    return { ok: false, status: 500, body: "db" };
  }
  // Unknown token — still return 200 to avoid leaking validity to scanners.
  return { ok: true, status: 200, body: "OK" };
}

/**
 * RFC 8058 List-Unsubscribe one-click — Gmail/Outlook send a POST here when a
 * recipient hits the unsubscribe button. Response MUST be 2xx without any user
 * interaction; otherwise the mailbox provider treats the sender as untrusted.
 * Accepts ?product=ai|nev (default nev) to pick the right table.
 */
export async function POST(req: Request) {
  const url = new URL(req.url);
  const tokenFromQuery = url.searchParams.get("token");
  const productFromQuery = url.searchParams.get("product");
  let tokenFromBody: string | null = null;
  let productFromBody: string | null = null;
  if (!tokenFromQuery) {
    try {
      const form = await req.formData();
      const t = form.get("token");
      const p = form.get("product");
      if (typeof t === "string") tokenFromBody = t;
      if (typeof p === "string") productFromBody = p;
    } catch {
      // not form data — ignore
    }
  }
  const token = tokenFromQuery ?? tokenFromBody ?? "";
  const product = productFromQuery ?? productFromBody;
  const r = await unsubscribeByToken(token, product);
  return new NextResponse(r.body, {
    status: r.status,
    headers: { "Content-Type": "text/plain; charset=utf-8" },
  });
}

