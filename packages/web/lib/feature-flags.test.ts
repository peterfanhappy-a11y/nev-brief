import { afterEach, describe, expect, it, vi } from "vitest";
import { subscriptionsEnabled } from "./feature-flags";

describe("subscription feature flag", () => {
  afterEach(() => {
    vi.unstubAllEnvs();
  });

  it.each(["false", "FALSE"])(
    "is disabled for an explicit false value (%s)",
    (value) => {
      vi.stubEnv("SUBSCRIPTIONS_ENABLED", value);
      expect(subscriptionsEnabled()).toBe(false);
    },
  );

  it("is enabled by default when no kill switch is configured", () => {
    vi.stubEnv("SUBSCRIPTIONS_ENABLED", "");
    expect(subscriptionsEnabled()).toBe(true);
  });

  it('remains enabled for an explicit "true" value', () => {
    vi.stubEnv("SUBSCRIPTIONS_ENABLED", "true");
    expect(subscriptionsEnabled()).toBe(true);
  });
});
