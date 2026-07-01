// Shared helpers for looking up subscribers by unsubscribe token across the
// two product tables (subscribers = NEV, ai_subscribers = AIVIZENS AI trends).
// Unsubscribe/manage routes accept ?product=ai|nev to pick the right table.

import type { SupabaseClient } from "@supabase/supabase-js";

export type Product = "nev" | "ai";

export function parseProduct(raw: string | null | undefined): Product {
  return raw === "ai" ? "ai" : "nev";
}

export function subscribersTable(product: Product): "subscribers" | "ai_subscribers" {
  return product === "ai" ? "ai_subscribers" : "subscribers";
}

export function productLabel(product: Product): string {
  return product === "ai" ? "AIVIZENS · AI 趋势" : "NEV 早报";
}

export type SubscriberLookup = { id: string; email: string; status: string } | null;

export async function findSubscriberByToken(
  sb: SupabaseClient,
  product: Product,
  token: string,
): Promise<SubscriberLookup> {
  const { data } = await sb
    .from(subscribersTable(product))
    .select("id, email, status")
    .eq("unsubscribe_token", token)
    .maybeSingle();
  return data ?? null;
}

export async function setSubscriberStatus(
  sb: SupabaseClient,
  product: Product,
  token: string,
  status: "active" | "unsubscribed",
): Promise<{ ok: boolean }> {
  const { error } = await sb
    .from(subscribersTable(product))
    .update({ status })
    .eq("unsubscribe_token", token);
  return { ok: !error };
}
