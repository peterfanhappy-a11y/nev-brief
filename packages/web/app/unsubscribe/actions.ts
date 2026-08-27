"use server";

import { redirect } from "next/navigation";
import { getSupabaseAdmin } from "@/lib/supabase";

const UUID_RE =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export async function unsubscribeAction(formData: FormData): Promise<never> {
  const token = formData.get("token");
  if (typeof token !== "string" || !UUID_RE.test(token)) {
    redirect("/unsubscribe?status=invalid");
  }

  let result: { error: unknown };
  try {
    result = await getSupabaseAdmin()
      .from("ai_subscribers")
      .update({
        status: "unsubscribed",
        unsubscribed_at: new Date().toISOString(),
      })
      .eq("unsubscribe_token", token);
  } catch {
    console.error("[unsubscribe] update failed");
    redirect("/unsubscribe?status=error");
  }

  if (result.error) {
    console.error("[unsubscribe] update failed");
    redirect("/unsubscribe?status=error");
  }

  // Unknown tokens intentionally receive the same completion state.
  redirect("/unsubscribe?status=unsubscribed");
}
