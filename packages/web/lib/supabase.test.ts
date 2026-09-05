import { beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  client: {},
  createClient: vi.fn(),
  WebSocket: vi.fn(),
}));

vi.mock("@supabase/supabase-js", () => ({
  createClient: mocks.createClient,
}));

vi.mock("ws", () => ({
  default: mocks.WebSocket,
}));

import { getSupabaseAdmin } from "./supabase";

describe("Supabase admin client", () => {
  beforeEach(() => {
    vi.stubEnv("SUPABASE_URL", "https://example.supabase.co");
    vi.stubEnv("SUPABASE_SERVICE_ROLE_KEY", "test-service-role-key");
    mocks.createClient.mockReturnValue(mocks.client);
  });

  it("provides a WebSocket transport for Node.js 20 server runtimes", () => {
    expect(getSupabaseAdmin()).toBe(mocks.client);
    expect(mocks.createClient).toHaveBeenCalledWith(
      "https://example.supabase.co",
      "test-service-role-key",
      {
        auth: { persistSession: false, autoRefreshToken: false },
        realtime: { transport: mocks.WebSocket },
      },
    );
  });
});
