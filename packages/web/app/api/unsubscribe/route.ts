import { NextResponse } from "next/server";
import { getSupabaseAdmin } from "@/lib/supabase";

export const runtime = "nodejs";

const UUID_RE =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

async function unsubscribeByToken(token: string): Promise<{ ok: boolean; status: number; body: string }> {
  if (!UUID_RE.test(token)) {
    return { ok: false, status: 400, body: "invalid_token" };
  }
  const sb = getSupabaseAdmin();
  const { data, error } = await sb
    .from("subscribers")
    .update({ status: "unsubscribed" })
    .eq("unsubscribe_token", token)
    .select("id")
    .maybeSingle();
  if (error) {
    console.error("[unsubscribe] db error", error);
    return { ok: false, status: 500, body: "db" };
  }
  if (!data) {
    // Unknown token — still return 200 to avoid leaking validity to scanners
    return { ok: true, status: 200, body: "OK" };
  }
  return { ok: true, status: 200, body: "OK" };
}

/**
 * RFC 8058 List-Unsubscribe one-click — Gmail/Outlook send a POST here when a
 * recipient hits the unsubscribe button. Response MUST be 2xx without any user
 * interaction; otherwise the mailbox provider treats the sender as untrusted.
 */
export async function POST(req: Request) {
  const url = new URL(req.url);
  const tokenFromQuery = url.searchParams.get("token");
  let tokenFromBody: string | null = null;
  if (!tokenFromQuery) {
    // RFC 8058 spec sends `List-Unsubscribe=One-Click` in form body, but
    // some clients also pass the token in the URL fragment. Try both.
    try {
      const form = await req.formData();
      const t = form.get("token");
      if (typeof t === "string") tokenFromBody = t;
    } catch {
      // not form data — ignore
    }
  }
  const token = tokenFromQuery ?? tokenFromBody ?? "";
  const r = await unsubscribeByToken(token);
  return new NextResponse(r.body, {
    status: r.status,
    headers: { "Content-Type": "text/plain; charset=utf-8" },
  });
}
