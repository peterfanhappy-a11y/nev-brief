import { readFile, stat } from "node:fs/promises";

import nextConfig from "../next.config.mjs";

const assets = [
  "bytedance-v1.webp",
  "alibaba-v1.webp",
  "tencent-v1.webp",
  "deepseek-v1.webp",
  "xiaomi-v1.webp",
  "huawei-v1.webp",
  "weibo-v1.webp",
  "wechat-v1.webp",
  "douyin-v1.webp",
  "xiaohongshu-v1.webp",
];
const assetDirectory = new URL("../public/brand/companies/web/", import.meta.url);
const maxAssetBytes = 12 * 1024;
const maxTotalBytes = 45_000;

let totalBytes = 0;
for (const asset of assets) {
  const assetUrl = new URL(asset, assetDirectory);
  const [metadata, contents] = await Promise.all([stat(assetUrl), readFile(assetUrl)]);

  if (contents.subarray(0, 4).toString("ascii") !== "RIFF" ||
      contents.subarray(8, 12).toString("ascii") !== "WEBP") {
    throw new Error(`${asset} is not a WebP asset`);
  }
  if (metadata.size > maxAssetBytes) {
    throw new Error(`${asset} exceeds ${maxAssetBytes} bytes`);
  }
  totalBytes += metadata.size;
}

if (totalBytes > maxTotalBytes) {
  throw new Error(`brand assets total ${totalBytes} exceeds ${maxTotalBytes} bytes`);
}

const headerRules = await nextConfig.headers?.();
const assetRule = headerRules?.find(
  (rule) => rule.source === "/brand/companies/web/:path*",
);
const cacheControl = assetRule?.headers?.find(
  (header) => header.key.toLowerCase() === "cache-control",
);

if (cacheControl?.value !== "public, max-age=31536000, immutable") {
  throw new Error("optimized brand assets are missing immutable cache headers");
}

console.log(`brand assets verified: ${assets.length} files, ${totalBytes} bytes`);
