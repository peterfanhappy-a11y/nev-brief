import { readFile } from "node:fs/promises";

const manifestUrl = new URL("../.next/prerender-manifest.json", import.meta.url);
const homepageUrl = new URL("../.next/server/app/index.html", import.meta.url);
const manifest = JSON.parse(await readFile(manifestUrl, "utf8"));
const homepage = manifest.routes?.["/"];

if (homepage?.initialRevalidateSeconds !== 300) {
  console.error(
    `expected homepage ISR revalidation of 300 seconds, got ${homepage?.initialRevalidateSeconds ?? "missing route"}`,
  );
  process.exit(1);
}

if (process.env.ALLOW_UNAVAILABLE_HOMEPAGE_BUILD !== "true") {
  const homepageHtml = await readFile(homepageUrl, "utf8");
  if (homepageHtml.includes("日报暂时无法加载")) {
    console.error("homepage ISR contains the unavailable fallback");
    process.exit(1);
  }
}

console.log("homepage ISR verified: 300 seconds");
