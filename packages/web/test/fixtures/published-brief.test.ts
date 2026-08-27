import { describe, expect, it } from "vitest";

import { assertDisposableFixtureTarget } from "./published-brief";

describe("assertDisposableFixtureTarget", () => {
  it("rejects fixture mutation when the disposable-stack marker is missing", () => {
    expect(() =>
      assertDisposableFixtureTarget({
        AIVIZENS_DISPOSABLE_STACK: undefined,
        SUPABASE_URL: "http://127.0.0.1:55437",
      }),
    ).toThrow(/AIVIZENS_DISPOSABLE_STACK/);
  });

  it.each([
    "https://project.supabase.co",
    "https://127.0.0.1:55437",
    "http://192.0.2.10:55437",
  ])("rejects fixture mutation for non-http-loopback URL %s", (supabaseUrl) => {
    expect(() =>
      assertDisposableFixtureTarget({
        AIVIZENS_DISPOSABLE_STACK: "true",
        SUPABASE_URL: supabaseUrl,
      }),
    ).toThrow(/loopback/);
  });

  it.each([
    "http://127.0.0.1:55437",
    "http://localhost:55437",
    "http://[::1]:55437",
  ])("allows fixture mutation only for marked loopback URL %s", (supabaseUrl) => {
    expect(() =>
      assertDisposableFixtureTarget({
        AIVIZENS_DISPOSABLE_STACK: "true",
        SUPABASE_URL: supabaseUrl,
      }),
    ).not.toThrow();
  });
});
