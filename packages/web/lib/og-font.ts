// CJK font loader for next/og ImageResponse.
//
// Why: @vercel/og bundled with Next.js 14 only ships Noto Sans Latin, which
// renders Chinese characters as tofu blocks. On Windows it also hits a path
// bug ("ERR_INVALID_URL: .\\file:\\D:\\...") trying to load that default
// bundle. Passing an explicit `fonts` argument to ImageResponse bypasses
// both problems.
//
// Strategy: hit Google Fonts CSS endpoint with a known text payload so the
// returned @font-face only includes the glyphs we need (much smaller than
// the full ~10MB CJK font). Cache the result for the worker's lifetime.

async function fetchGoogleFontBytes(
  family: string,
  weight: number,
  text: string,
): Promise<ArrayBuffer> {
  const params = new URLSearchParams({
    family: `${family}:wght@${weight}`,
    text,
  });
  // The opentype.js bundled inside @vercel/og rejects WOFF2 ("Unsupported
  // OpenType signature wOF2"). Use an IE9 UA so Google Fonts returns a
  // WOFF (not WOFF2) @font-face block — opentype.js parses WOFF fine.
  const cssRes = await fetch(
    `https://fonts.googleapis.com/css2?${params}`,
    {
      headers: {
        "User-Agent":
          "Mozilla/5.0 (compatible; MSIE 9.0; Windows NT 6.1; Trident/5.0)",
      },
    },
  );
  if (!cssRes.ok) {
    throw new Error(`google fonts css ${cssRes.status}`);
  }
  const css = await cssRes.text();
  // Prefer woff, fall back to truetype.
  let match = css.match(/src:\s*url\(([^)]+)\)\s*format\(['"]woff['"]\)/);
  if (!match) {
    match = css.match(/src:\s*url\(([^)]+)\)\s*format\(['"]truetype['"]\)/);
  }
  if (!match) {
    throw new Error("no woff/ttf url in google fonts css: " + css.slice(0, 200));
  }
  const fontRes = await fetch(match[1]);
  if (!fontRes.ok) {
    throw new Error(`font fetch ${fontRes.status}`);
  }
  return fontRes.arrayBuffer();
}

const cache = new Map<string, Promise<ArrayBuffer>>();

/**
 * Fetch Noto Sans SC bytes containing only the glyphs in `text`. Cached per
 * (weight, text) pair so the second call within the worker is free.
 */
export function loadCjkFont(weight: 400 | 700, text: string): Promise<ArrayBuffer> {
  const key = `${weight}:${text}`;
  const existing = cache.get(key);
  if (existing) return existing;
  const promise = fetchGoogleFontBytes("Noto Sans SC", weight, text);
  cache.set(key, promise);
  return promise;
}
