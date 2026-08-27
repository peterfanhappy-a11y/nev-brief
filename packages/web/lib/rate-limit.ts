import { createHmac } from "node:crypto";
import { getSupabaseAdmin } from "./supabase";

const SHA256_HEX = /^[0-9a-f]{64}$/;

interface RateLimitRpcRow {
  allowed: boolean;
  retry_after_seconds: number;
}

export interface SubscriptionRateLimitInput {
  ipHash: string;
  emailHash: string;
  now: Date;
}

export interface SubscriptionRateLimitResult {
  allowed: boolean;
  retryAfterSeconds: number;
}

export function hashSubscriptionRateLimitKey(identifier: string): string {
  const secret = process.env.SUBSCRIPTION_HASH_SECRET;
  if (!secret) {
    throw new Error("SUBSCRIPTION_HASH_SECRET is required");
  }

  return createHmac("sha256", secret).update(identifier).digest("hex");
}

export async function checkSubscriptionRateLimit(
  input: SubscriptionRateLimitInput,
): Promise<SubscriptionRateLimitResult> {
  if (!SHA256_HEX.test(input.ipHash) || !SHA256_HEX.test(input.emailHash)) {
    throw new Error("Subscription rate limiting requires hashed identifiers");
  }
  if (Number.isNaN(input.now.getTime())) {
    throw new Error("Subscription rate limiting requires a valid timestamp");
  }

  const { data, error } = await getSupabaseAdmin().rpc(
    "check_ai_subscription_rate_limit",
    {
      ip_hash: input.ipHash,
      email_hash: input.emailHash,
      now_at: input.now.toISOString(),
    },
  );

  const row = Array.isArray(data) ? (data[0] as RateLimitRpcRow | undefined) : undefined;
  if (
    error ||
    !row ||
    typeof row.allowed !== "boolean" ||
    !Number.isInteger(row.retry_after_seconds) ||
    row.retry_after_seconds < 0
  ) {
    throw new Error("Subscription rate-limit storage failed");
  }

  return {
    allowed: row.allowed,
    retryAfterSeconds: row.retry_after_seconds,
  };
}
