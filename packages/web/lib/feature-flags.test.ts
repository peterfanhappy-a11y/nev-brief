import { afterEach, describe, expect, it, vi } from "vitest";
import { subscriptionsEnabled } from "./feature-flags";

describe("subscription feature flag", () => {
  afterEach(() => {
    vi.unstubAllEnvs();
  });

  it.each([undefined, "", "false", "TRUE", " true", "true "])(
    "is disabled for %s",
    (value) => {
      vi.stubEnv("SUBSCRIPTIONS_ENABLED", value ?? "");
      expect(subscriptionsEnabled()).toBe(false);
    },
  );

  it('is enabled only for the exact string "true"', () => {
    vi.stubEnv("SUBSCRIPTIONS_ENABLED", "true");
    expect(subscriptionsEnabled()).toBe(true);
  });
});
