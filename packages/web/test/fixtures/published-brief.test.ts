import { describe, expect, it, vi } from "vitest";

vi.mock("server-only", () => ({}));

import { AiBriefContentSchema } from "@/lib/ai-briefs";
import {
  assertDisposableFixtureTarget,
  PUBLISHED_BRIEF_CONTENT,
  PUBLISHED_BRIEF_V3_CONTENT,
} from "./published-brief";

describe("published brief fixtures", () => {
  it("provides a valid standalone v3 issue without changing the legacy fixture", () => {
    const v3 = AiBriefContentSchema.parse(PUBLISHED_BRIEF_V3_CONTENT);
    expect(v3.version).toBe(3);
    expect(v3.opc_case?.sharer).toBe("Ruslan");
    expect(v3.intro_bullets).toHaveLength(4);
    expect([v3.today_ai, v3.ai_masters, v3.ai_research, v3.agent_tools])
      .not.toContain(null);

    const legacy = AiBriefContentSchema.parse(PUBLISHED_BRIEF_CONTENT);
    expect(legacy.version).toBe(1);
    expect(legacy.opc_case).toBeNull();
    expect(legacy.ai_engineering).not.toBeNull();
    expect(legacy.featured).toHaveLength(1);
  });
});

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
