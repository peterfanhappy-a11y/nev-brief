import { NextResponse } from "next/server";
import { z } from "zod";
import { sendAiConfirmationEmail } from "@/lib/ai-confirmation-email";
import { subscriptionsEnabled } from "@/lib/feature-flags";
import {
  checkSubscriptionRateLimit,
  hashSubscriptionRateLimitKey,
} from "@/lib/rate-limit";
import { createConfirmationToken } from "@/lib/subscription-token";
import { getSupabaseAdmin } from "@/lib/supabase";
import { verifyTurnstile } from "@/lib/turnstile";

export const runtime = "nodejs";

const Utm = z
  .object({
    source: z.string().max(200).optional(),
    medium: z.string().max(200).optional(),
    campaign: z.string().max(200).optional(),
  })
  .strict();

const Body = z
  .object({
    email: z.string().email().toLowerCase().trim().max(254),
    turnstileToken: z.string().min(1).max(2048),
    utm: Utm.optional(),
  })
  .strict();

interface PrepareSubscriptionRow {
  confirmation_required: boolean;
}

function getClientIp(req: Request): string {
  return (
    req.headers.get("x-forwarded-for")?.split(",")[0]?.trim() ||
    req.headers.get("x-real-ip")?.trim() ||
    "unknown"
  );
}

export async function POST(req: Request) {
  if (!subscriptionsEnabled()) {
    return NextResponse.json(
      { error: "subscriptions_disabled" },
      { status: 503 },
    );
  }

  let body: z.infer<typeof Body>;
  try {
    body = Body.parse(await req.json());
  } catch {
    return NextResponse.json({ error: "invalid_body" }, { status: 400 });
  }

  const ip = getClientIp(req);
  let turnstileOk: boolean;
  try {
    turnstileOk = await verifyTurnstile(body.turnstileToken, ip);
  } catch {
    console.error("[ai/subscribe] Turnstile verification unavailable");
    return NextResponse.json(
      { error: "verification_unavailable" },
      { status: 503 },
    );
  }
  if (!turnstileOk) {
    return NextResponse.json(
      { error: "verification_failed" },
      { status: 400 },
    );
  }

  let ipHash: string;
  let emailHash: string;
  try {
    ipHash = hashSubscriptionRateLimitKey(ip);
    emailHash = hashSubscriptionRateLimitKey(body.email);
  } catch {
    console.error("[ai/subscribe] limiter hashing unavailable");
    return NextResponse.json({ error: "server_configuration" }, { status: 500 });
  }

  let rateLimit: Awaited<ReturnType<typeof checkSubscriptionRateLimit>>;
  try {
    rateLimit = await checkSubscriptionRateLimit({
      ipHash,
      emailHash,
      now: new Date(),
    });
  } catch {
    console.error("[ai/subscribe] durable rate-limit storage failed");
    return NextResponse.json({ error: "db" }, { status: 500 });
  }
  if (!rateLimit.allowed) {
    return NextResponse.json(
      { error: "rate_limited" },
      {
        status: 429,
        headers: { "Retry-After": String(rateLimit.retryAfterSeconds) },
      },
    );
  }

  const { rawToken, tokenHash } = createConfirmationToken();
  const expiresAt = new Date(Date.now() + 24 * 60 * 60 * 1_000);

  let prepareResult: {
    data: unknown;
    error: unknown;
  };
  try {
    prepareResult = await getSupabaseAdmin().rpc("prepare_ai_subscription", {
      input_email: body.email,
      input_token_hash: tokenHash,
      input_expires_at: expiresAt.toISOString(),
      input_ip_hash: ipHash,
      input_utm: body.utm ?? {},
    });
  } catch {
    console.error("[ai/subscribe] atomic preparation failed");
    return NextResponse.json({ error: "db" }, { status: 500 });
  }

  const rows = prepareResult.data as PrepareSubscriptionRow[] | null;
  const decision = Array.isArray(rows) ? rows[0] : undefined;
  if (
    prepareResult.error ||
    rows?.length !== 1 ||
    !decision ||
    typeof decision.confirmation_required !== "boolean"
  ) {
    console.error("[ai/subscribe] atomic preparation failed");
    return NextResponse.json({ error: "db" }, { status: 500 });
  }

  if (decision.confirmation_required) {
    try {
      await sendAiConfirmationEmail(body.email, rawToken);
    } catch {
      // Preserve account-state privacy: retain the pending token for a later
      // rate-limited request, record no provider/input detail, and return the
      // same public response as every other subscriber state.
      console.error("[ai/subscribe] confirmation email delivery failed");
    }
  }

  return NextResponse.json(
    { ok: true, message: "check_email" },
    { status: 202 },
  );
}
