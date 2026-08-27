export type AiSubscriberStatus =
  | "pending_confirmation"
  | "active"
  | "unsubscribed";

export type AiSubscriberEvent = "subscribe" | "confirm" | "unsubscribe";

export function canReceiveAiBrief(status: AiSubscriberStatus): boolean {
  return status === "active";
}

export function nextSubscriberStatus(
  current: AiSubscriberStatus,
  event: AiSubscriberEvent,
): AiSubscriberStatus {
  switch (event) {
    case "subscribe":
      return current === "unsubscribed" ? "pending_confirmation" : current;
    case "confirm":
      if (current === "pending_confirmation") {
        return "active";
      }
      break;
    case "unsubscribe":
      return "unsubscribed";
  }

  throw new Error(`Illegal AI subscriber transition: ${current} -> ${event}`);
}
