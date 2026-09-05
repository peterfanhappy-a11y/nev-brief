import { createHmac } from "node:crypto";
import { getSupabaseAdmin } from "./supabase";

const SHA256_HEX = /^[0-9a-f]{64}$/;

function redactTestDiagnostic(value: unknown): string | null {
  if (typeof value !== "string") return null;
  return value
    .replace(/[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}/gi, "[redacted]")
    .replace(/\b[a-f0-9]{64}\b/gi, "[redacted]")
    .replace(/\b[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\b/g, "[redacted]");
}

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

  let result: Awaited<ReturnType<ReturnType<typeof getSupabaseAdmin>["rpc"]>>;
  try {
    result = await getSupabaseAdmin().rpc("check_ai_subscription_rate_limit", {
      ip_hash: input.ipHash,
      email_hash: input.emailHash,
      now_at: input.now.toISOString(),
    });
  } catch (error) {
    if (process.env.AIVIZENS_DISPOSABLE_STACK === "true") {
      const cause = error instanceof Error ? error.cause : null;
      console.error("[test rate-limit RPC exception]", {
        name: error instanceof Error ? error.name : typeof error,
        message: redactTestDiagnostic(error instanceof Error ? error.message : null),
        causeCode:
          typeof cause === "object" && cause && "code" in cause
            ? redactTestDiagnostic(cause.code)
            : null,
        causeMessage:
          typeof cause === "object" && cause && "message" in cause
            ? redactTestDiagnostic(cause.message)
            : null,
      });
    }
    throw new Error("Subscription rate-limit storage failed");
  }
  const { data, error } = result;

  const row = Array.isArray(data) ? (data[0] as RateLimitRpcRow | undefined) : undefined;
  if (
    error ||
    !row ||
    typeof row.allowed !== "boolean" ||
    !Number.isInteger(row.retry_after_seconds) ||
    row.retry_after_seconds < 0
  ) {
    if (process.env.AIVIZENS_DISPOSABLE_STACK === "true") {
      console.error("[test rate-limit RPC failure]", {
        hasError: Boolean(error),
        errorCode: typeof error === "object" && error && "code" in error ? error.code : null,
        errorMessage: typeof error === "object" && error && "message" in error ? error.message : null,
        dataKind: data === null ? "null" : Array.isArray(data) ? "array" : typeof data,
        rowCount: Array.isArray(data) ? data.length : null,
      });
    }
    throw new Error("Subscription rate-limit storage failed");
  }

  return {
    allowed: row.allowed,
    retryAfterSeconds: row.retry_after_seconds,
  };
}
