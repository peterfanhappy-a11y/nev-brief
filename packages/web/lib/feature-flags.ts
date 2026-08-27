export function subscriptionsEnabled(): boolean {
  return process.env.SUBSCRIPTIONS_ENABLED?.toLowerCase() !== "false";
}
