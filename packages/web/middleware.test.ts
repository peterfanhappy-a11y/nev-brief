import { NextRequest } from "next/server";
import { describe, expect, it } from "vitest";

import { middleware } from "./middleware";

describe("preview response policy", () => {
  it("sets a real private no-store HTTP response header", () => {
    const request = new NextRequest(
      "https://aivizens.invalid/preview/2026-08-04?expires=1785812100&signature=private",
    );

    const response = middleware(request);

    expect(response.headers.get("Cache-Control")).toBe("private, no-store");
    expect(response.headers.get("Referrer-Policy")).toBe("no-referrer");
  });
});
