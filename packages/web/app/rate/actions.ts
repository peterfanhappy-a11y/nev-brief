"use server";

import { redirect } from "next/navigation";
import { getSupabaseAdmin } from "@/lib/supabase";

const UUID_RE =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export async function recordRatingAction(formData: FormData): Promise<never> {
  const delivery = formData.get("delivery");
  const score = Number(formData.get("score"));
  if (
    typeof delivery !== "string" ||
    !UUID_RE.test(delivery) ||
    !Number.isInteger(score) ||
    ![1, 2, 3].includes(score)
  ) {
    redirect("/rate?status=invalid");
  }

  try {
    const { error } = await getSupabaseAdmin()
      .from("ai_ratings")
      .upsert(
        { delivery_id: delivery, score, rated_at: new Date().toISOString() },
        { onConflict: "delivery_id" },
      );
    if (error) console.error("[rate] upsert failed");
  } catch {
    console.error("[rate] upsert failed");
  }

  // FK failures and unknown delivery IDs share the same public state.
  redirect("/rate?status=thanks");
}
