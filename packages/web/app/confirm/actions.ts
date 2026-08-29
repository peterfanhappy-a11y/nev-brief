"use server";

import { redirect } from "next/navigation";
import { sendAiWelcomeEmail } from "@/lib/ai-welcome-email";
import { hashConfirmationToken } from "@/lib/subscription-token";
import { getSupabaseAdmin } from "@/lib/supabase";

interface ConfirmedSubscriber {
  id: string;
  email: string;
  unsubscribe_token: string;
}

function isConfirmedSubscriber(value: unknown): value is ConfirmedSubscriber {
  if (!value || typeof value !== "object") return false;
  const row = value as Record<string, unknown>;
  return (
    typeof row.id === "string" &&
    typeof row.email === "string" &&
    typeof row.unsubscribe_token === "string"
  );
}

export async function confirmSubscriptionAction(formData: FormData): Promise<never> {
  const rawToken = formData.get("token");
  if (typeof rawToken !== "string" || rawToken.length === 0 || rawToken.length > 512) {
    redirect("/confirm?status=invalid");
  }

  const tokenHash = hashConfirmationToken(rawToken);
  let result: { data: unknown; error: unknown };
  try {
    result = await getSupabaseAdmin().rpc("confirm_ai_subscription", {
      token_hash: tokenHash,
      now_at: new Date().toISOString(),
    });
  } catch {
    console.error("[confirm] atomic confirmation failed");
    redirect("/confirm?status=error");
  }

  if (result.error) {
    console.error("[confirm] atomic confirmation failed");
    redirect("/confirm?status=error");
  }

  const rows = Array.isArray(result.data) ? result.data : [];
  if (rows.length === 0) {
    redirect("/confirm?status=invalid");
  }
  if (rows.length !== 1 || !isConfirmedSubscriber(rows[0])) {
    console.error("[confirm] atomic confirmation failed");
    redirect("/confirm?status=error");
  }

  try {
    await sendAiWelcomeEmail(
      rows[0].email,
      rows[0].unsubscribe_token,
      tokenHash,
    );
  } catch {
    console.error("[confirm] welcome email delivery failed");
  }

  redirect("/confirm?status=confirmed");
}
