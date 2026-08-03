import { createHash, randomBytes } from "node:crypto";

export function hashConfirmationToken(rawToken: string): string {
  return createHash("sha256").update(rawToken).digest("hex");
}

export function createConfirmationToken(): {
  rawToken: string;
  tokenHash: string;
} {
  const rawToken = randomBytes(32).toString("base64url");

  return { rawToken, tokenHash: hashConfirmationToken(rawToken) };
}
