import { Buffer } from "node:buffer";
import { describe, expect, it } from "vitest";
import {
  createConfirmationToken,
  hashConfirmationToken,
} from "./subscription-token";

describe("confirmation tokens", () => {
  it("creates a 32-byte token with a SHA-256 hash for storage", () => {
    const { rawToken, tokenHash } = createConfirmationToken();

    expect(Buffer.from(rawToken, "base64url")).toHaveLength(32);
    expect(rawToken).toMatch(/^[A-Za-z0-9_-]+$/);
    expect(tokenHash).toBe(hashConfirmationToken(rawToken));
    expect(tokenHash).toMatch(/^[0-9a-f]{64}$/);
  });

  it("derives deterministic lowercase SHA-256 hashes", () => {
    expect(hashConfirmationToken("known confirmation token")).toBe(
      "d99dfbae6d33e359357e849ed2eafa870f11d43b4738bc03ae02fefb37ef7f44",
    );
  });
});
