// Side-effect import that works around a @vercel/og@0.6.x Windows bug.
//
// The bundled @vercel/og initializes its default Latin font at module load:
//   fs.readFileSync(fileURLToPath(path.join(import.meta.url, "../noto-sans-v27-latin-regular.ttf")))
//
// `import.meta.url` is a `file:///D:/...` URL. On Windows, `path.join` treats it as a
// relative path and produces `.\file:\D:\...`, which `fileURLToPath` rejects with
// ERR_INVALID_URL. This patch detects the file-URL first arg, converts it to a path,
// then delegates to the original join. POSIX is unaffected.
//
// Must be imported BEFORE `next/og` in any route that uses ImageResponse.

import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

declare global {
  // eslint-disable-next-line no-var
  var __OG_WIN_PATCH_APPLIED__: boolean | undefined;
}

if (process.platform === "win32" && !globalThis.__OG_WIN_PATCH_APPLIED__) {
  const origJoin = path.join.bind(path);
  // @vercel/og does:  fileURLToPath(path.join(import.meta.url, "../foo.ttf"))
  // Linux happens to produce "file:/.../foo.ttf" which fileURLToPath accepts.
  // We mimic that by converting back to a file URL after joining on Windows.
  (path as unknown as { join: typeof path.join }).join = function patchedJoin(
    ...segs: string[]
  ): string {
    if (
      segs.length > 0 &&
      typeof segs[0] === "string" &&
      segs[0].startsWith("file:///")
    ) {
      try {
        const head = fileURLToPath(segs[0]);
        const joined = origJoin(head, ...segs.slice(1));
        return pathToFileURL(joined).href;
      } catch {
        // fall through to original behavior
      }
    }
    return origJoin(...segs);
  };
  globalThis.__OG_WIN_PATCH_APPLIED__ = true;
}

export {};
