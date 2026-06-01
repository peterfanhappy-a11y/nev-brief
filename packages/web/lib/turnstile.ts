const VERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify";

interface TurnstileResponse {
  success: boolean;
  "error-codes"?: string[];
  hostname?: string;
}

export async function verifyTurnstile(token: string, ip?: string): Promise<boolean> {
  const secret = process.env.TURNSTILE_SECRET_KEY;
  if (!secret) {
    console.warn("[turnstile] TURNSTILE_SECRET_KEY missing — skipping verification (dev only)");
    return true;
  }
  const params = new URLSearchParams({ secret, response: token });
  if (ip) params.append("remoteip", ip);
  try {
    const res = await fetch(VERIFY_URL, {
      method: "POST",
      body: params,
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
    });
    const data: TurnstileResponse = await res.json();
    if (!data.success) {
      console.warn("[turnstile] verification failed", data["error-codes"]);
    }
    return data.success;
  } catch (err) {
    console.error("[turnstile] network error", err);
    return false;
  }
}
