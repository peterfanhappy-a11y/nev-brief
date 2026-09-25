import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  revalidatePath: vi.fn(),
}));

const SECRET = "0123456789abcdef0123456789abcdef";

vi.mock("next/cache", () => ({
  revalidatePath: mocks.revalidatePath,
}));

import { POST } from "./route";

function request(
  body: unknown = { briefDate: "2026-09-24" },
  token = SECRET,
): Request {
  const headers = new Headers({ "content-type": "application/json" });
  if (token) headers.set("authorization", `Bearer ${token}`);

  return new Request(
    "https://www.aivizens.com/api/internal/revalidate-homepage",
    {
      method: "POST",
      headers,
      body: JSON.stringify(body),
    },
  );
}

describe("POST /api/internal/revalidate-homepage", () => {
  beforeEach(() => {
    vi.stubEnv("HOMEPAGE_REVALIDATE_SECRET", SECRET);
  });

  afterEach(() => {
    vi.unstubAllEnvs();
    vi.clearAllMocks();
  });

  it.each(["", "wrong-secret"])(
    "rejects an unauthorized request without changing the homepage cache (%s)",
    async (token) => {
      const response = await POST(request(undefined, token));

      expect(response.status).toBe(401);
      await expect(response.json()).resolves.toEqual({ error: "unauthorized" });
      expect(mocks.revalidatePath).not.toHaveBeenCalled();
    },
  );

  it("fails closed when the server secret is not configured", async () => {
    vi.stubEnv("HOMEPAGE_REVALIDATE_SECRET", "");

    const response = await POST(request());

    expect(response.status).toBe(500);
    await expect(response.json()).resolves.toEqual({
      error: "server_configuration",
    });
    expect(mocks.revalidatePath).not.toHaveBeenCalled();
  });

  it("fails closed when the server secret is shorter than 32 bytes", async () => {
    vi.stubEnv("HOMEPAGE_REVALIDATE_SECRET", "too-short");

    const response = await POST(request(undefined, "too-short"));

    expect(response.status).toBe(500);
    await expect(response.json()).resolves.toEqual({
      error: "server_configuration",
    });
    expect(mocks.revalidatePath).not.toHaveBeenCalled();
  });

  it.each([
    [{}],
    [{ briefDate: "2026-02-29" }],
    [{ briefDate: "2026-09-24", extra: true }],
  ])("rejects an invalid request body (%j)", async (body) => {
    const response = await POST(request(body));

    expect(response.status).toBe(400);
    await expect(response.json()).resolves.toEqual({ error: "invalid_body" });
    expect(mocks.revalidatePath).not.toHaveBeenCalled();
  });

  it("invalidates only the homepage and returns a private success response", async () => {
    const response = await POST(request());

    expect(response.status).toBe(200);
    expect(response.headers.get("cache-control")).toBe("private, no-store");
    await expect(response.json()).resolves.toEqual({
      ok: true,
      briefDate: "2026-09-24",
    });
    expect(mocks.revalidatePath).toHaveBeenCalledOnce();
    expect(mocks.revalidatePath).toHaveBeenCalledWith("/", "page");
  });
});
