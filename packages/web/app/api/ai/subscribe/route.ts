import { NextResponse } from "next/server";
import { z } from "zod";
import { sendAiWelcomeEmail } from "@/lib/ai-welcome-email";
import { subscriptionsEnabled } from "@/lib/feature-flags";
import {
  checkSubscriptionRateLimit,
  hashSubscriptionRateLimitKey,
} from "@/lib/rate-limit";
import { createConfirmationToken } from "@/lib/subscription-token";
import { getSupabaseAdmin } from "@/lib/supabase";

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
    utm: Utm.optional(),
  })
  .strict();

interface ActivateSubscriptionRow {
  welcome_required: boolean;
  unsubscribe_token: string;
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

  let activationResult: {
    data: unknown;
    error: unknown;
  };
  try {
    activationResult = await getSupabaseAdmin().rpc("activate_ai_subscription", {
      input_email: body.email,
      input_ip_hash: ipHash,
      input_utm: body.utm ?? {},
    });
  } catch {
    console.error("[ai/subscribe] atomic activation failed");
    return NextResponse.json({ error: "db" }, { status: 500 });
  }

  const rows = activationResult.data as ActivateSubscriptionRow[] | null;
  const decision = Array.isArray(rows) ? rows[0] : undefined;
  if (
    activationResult.error ||
    rows?.length !== 1 ||
    !decision ||
    typeof decision.welcome_required !== "boolean" ||
    typeof decision.unsubscribe_token !== "string"
  ) {
    console.error("[ai/subscribe] atomic activation failed");
    return NextResponse.json({ error: "db" }, { status: 500 });
  }

  if (decision.welcome_required) {
    const { tokenHash } = createConfirmationToken();
    try {
      await sendAiWelcomeEmail(
        body.email,
        decision.unsubscribe_token,
        tokenHash,
      );
    } catch {
      console.error("[ai/subscribe] welcome email delivery failed");
    }
  }

  return NextResponse.json(
    { ok: true, message: "subscribed" },
    { status: 202 },
  );
}
