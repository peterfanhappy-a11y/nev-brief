import { describe, expect, it } from "vitest";
import {
  canReceiveAiBrief,
  nextSubscriberStatus,
  type AiSubscriberEvent,
  type AiSubscriberStatus,
} from "./subscription-types";

describe("AI subscriber states", () => {
  it("allows delivery only to active subscribers", () => {
    expect(canReceiveAiBrief("pending_confirmation")).toBe(false);
    expect(canReceiveAiBrief("active")).toBe(true);
    expect(canReceiveAiBrief("unsubscribed")).toBe(false);
  });

  it("requires confirmation after resubscription", () => {
    expect(nextSubscriberStatus("unsubscribed", "subscribe")).toBe(
      "pending_confirmation",
    );
  });

  it.each<
    [AiSubscriberStatus, AiSubscriberEvent, AiSubscriberStatus]
  >([
    ["pending_confirmation", "subscribe", "pending_confirmation"],
    ["active", "subscribe", "active"],
    ["unsubscribed", "subscribe", "pending_confirmation"],
    ["pending_confirmation", "confirm", "active"],
    ["pending_confirmation", "unsubscribe", "unsubscribed"],
    ["active", "unsubscribe", "unsubscribed"],
    ["unsubscribed", "unsubscribe", "unsubscribed"],
  ])("transitions %s via %s to %s", (current, event, expected) => {
    expect(nextSubscriberStatus(current, event)).toBe(expected);
  });

  it.each<[AiSubscriberStatus, AiSubscriberEvent]>([
    ["active", "confirm"],
    ["unsubscribed", "confirm"],
  ])("rejects an illegal %s → %s transition", (current, event) => {
    expect(() => nextSubscriberStatus(current, event)).toThrow(
      `Illegal AI subscriber transition: ${current} -> ${event}`,
    );
  });
});
