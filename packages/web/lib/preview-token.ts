import { createHmac, timingSafeEqual } from "node:crypto";

const MAX_PREVIEW_LIFETIME_SECONDS = 900;
const MIN_NON_TEST_SECRET_BYTES = 32;
const UNIX_SECONDS_RE = /^[1-9]\d{0,9}$/;
const LOWERCASE_SHA256_RE = /^[0-9a-f]{64}$/;

function isCanonicalDate(value: string): boolean {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value)) return false;
  const [year, month, day] = value.split("-").map(Number);
  if (year < 1) return false;
  const parsed = new Date(0);
  parsed.setUTCHours(0, 0, 0, 0);
  parsed.setUTCFullYear(year, month - 1, day);
  return (
    parsed.getUTCFullYear() === year &&
    parsed.getUTCMonth() === month - 1 &&
    parsed.getUTCDate() === day
  );
}

interface PreviewTokenInput {
  date: string;
  expires: string | undefined;
  signature: string | undefined;
  secret?: string;
  nowSeconds?: number;
  environment?: string;
}

export function validatePreviewToken({
  date,
  expires,
  signature,
  secret = process.env.PREVIEW_SIGNING_SECRET,
  nowSeconds = Math.floor(Date.now() / 1000),
  environment = process.env.NODE_ENV,
}: PreviewTokenInput): boolean {
  try {
    if (!isCanonicalDate(date)) return false;
    if (!expires || !UNIX_SECONDS_RE.test(expires)) return false;
    if (!signature || !LOWERCASE_SHA256_RE.test(signature)) return false;

    const expiry = Number(expires);
    if (!Number.isSafeInteger(expiry)) return false;
    if (!Number.isSafeInteger(nowSeconds) || nowSeconds < 0) return false;
    const lifetime = expiry - nowSeconds;
    if (lifetime <= 0 || lifetime > MAX_PREVIEW_LIFETIME_SECONDS) return false;

    if (!secret) return false;
    const secretBytes = Buffer.from(secret, "utf8");
    if (environment !== "test" && secretBytes.byteLength < MIN_NON_TEST_SECRET_BYTES) {
      return false;
    }

    const payload = `${date}:${expires}`;
    const expected = createHmac("sha256", secretBytes).update(payload, "ascii").digest();
    const provided = Buffer.from(signature, "hex");
    return provided.byteLength === expected.byteLength && timingSafeEqual(provided, expected);
  } catch {
    return false;
  }
}
