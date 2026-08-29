import { describe, expect, it } from "vitest";

import vector from "../../ai-brief/tests/fixtures/preview-token-vector.json";

import { validatePreviewToken } from "@/lib/preview-token";

const validToken = {
  date: vector.date,
  expires: String(vector.expires),
  signature: vector.signature,
  secret: vector.secret,
  nowSeconds: vector.now,
  environment: "production",
} as const;

describe("validatePreviewToken", () => {
  it("accepts the shared Python/TypeScript HMAC vector", () => {
    expect(validatePreviewToken(validToken)).toBe(true);
  });

  it("accepts canonical four-digit years below 100 without applying a 1900 offset", () => {
    expect(
      validatePreviewToken({
        ...validToken,
        date: "0099-08-04",
        signature:
          "2b37638b01cba4230978a01c24f62f88761f17837331d243e95b286f5105a869",
      }),
    ).toBe(true);
  });

  it.each([
    ["date", { date: "2026-08-05" }],
    ["expiry", { expires: String(vector.expires + 1) }],
    ["signature", { signature: `1${vector.signature.slice(1)}` }],
  ])("rejects a tampered %s", (_field, change) => {
    expect(validatePreviewToken({ ...validToken, ...change })).toBe(false);
  });

  it("rejects a token at its expiry boundary", () => {
    expect(
      validatePreviewToken({ ...validToken, nowSeconds: vector.expires }),
    ).toBe(false);
  });

  it("rejects a token with more than 900 seconds remaining", () => {
    expect(
      validatePreviewToken({ ...validToken, nowSeconds: vector.expires - 901 }),
    ).toBe(false);
  });

  it.each([
    ["2026-8-04", String(vector.expires), vector.signature],
    ["2026-02-29", String(vector.expires), vector.signature],
    [vector.date, ` ${vector.expires}`, vector.signature],
    [vector.date, `${vector.expires}.0`, vector.signature],
    [vector.date, String(vector.expires), vector.signature.toUpperCase()],
    [vector.date, String(vector.expires), "z".repeat(64)],
    [vector.date, String(vector.expires), vector.signature.slice(2)],
  ])(
    "rejects malformed token fields without throwing (%s, %s, %s)",
    (date, expires, signature) => {
      expect(() =>
        validatePreviewToken({
          ...validToken,
          date,
          expires,
          signature,
        }),
      ).not.toThrow();
      expect(
        validatePreviewToken({
          ...validToken,
          date,
          expires,
          signature,
        }),
      ).toBe(false);
    },
  );

  it.each([undefined, ""])("rejects a missing secret (%s)", (secret) => {
    expect(validatePreviewToken({ ...validToken, secret })).toBe(false);
  });

  it("rejects a secret shorter than 32 UTF-8 bytes outside tests", () => {
    expect(
      validatePreviewToken({
        ...validToken,
        secret: "é".repeat(15),
        environment: "production",
      }),
    ).toBe(false);
  });

  it("allows a short secret only in the test environment", () => {
    expect(
      validatePreviewToken({
        date: "2026-08-04",
        expires: "1785812100",
        signature:
          "ef754f3efd5394b92a9ae020e076338d2b3ee1fb0d38ccec6ba3e4c105ac8b28",
        secret: "test-secret",
        nowSeconds: vector.now,
        environment: "test",
      }),
    ).toBe(true);
  });
});
