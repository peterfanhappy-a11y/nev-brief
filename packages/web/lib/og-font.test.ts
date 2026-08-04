import { afterEach, describe, expect, it, vi } from "vitest";

import { loadCjkFont } from "@/lib/og-font";

describe("loadCjkFont", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("evicts a rejected request so a later attempt can succeed and be cached", async () => {
    const fontBytes = new Uint8Array([1, 2, 3, 4]).buffer;
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce({ ok: false, status: 503 })
      .mockResolvedValueOnce({
        ok: true,
        text: async () =>
          "@font-face { src: url(https://fonts.example/retry.woff) format('woff'); }",
      })
      .mockResolvedValueOnce({
        ok: true,
        arrayBuffer: async () => fontBytes,
      });
    vi.stubGlobal("fetch", fetchMock);

    await expect(loadCjkFont(400, "失败后重试🚀")).rejects.toThrow(
      "google fonts css 503",
    );
    await expect(loadCjkFont(400, "失败后重试🚀")).resolves.toBe(fontBytes);
    await expect(loadCjkFont(400, "失败后重试🚀")).resolves.toBe(fontBytes);
    expect(fetchMock).toHaveBeenCalledTimes(3);
  });
});
