// Brand logo renderer with three-tier resolution:
//   1. LOCAL_PNG — user-supplied PNG in /public/brand/companies/ (highest priority)
//   2. simple-icons — brand SVGs from the simple-icons OSS package
//   3. MONOGRAM   — generic colored-circle + character fallback
import {
  siBytedance,
  siHuawei,
  siKuaishou,
  siSinaweibo,
  siTiktok,
  siXiaomi,
} from "simple-icons";

type SimpleIcon = {
  path: string;
  title: string;
  hex: string;
  slug: string;
};

// Local PNGs the user obtained + placed under /public/brand/companies/.
// These take precedence over simple-icons whenever both are available.
const LOCAL_PNG: Record<string, string> = {
  alibaba: "/brand/companies/alibaba.png",
  tencent: "/brand/companies/tencent.png",
  deepseek: "/brand/companies/deepseek.png",
  xiaohongshu: "/brand/companies/xiaohongshu.png",
};

// Douyin and TikTok are the same product/logo under different regional brands
// operated by the same company, so we reuse the TikTok icon for the douyin slug.
const BRAND_ICONS: Record<string, SimpleIcon | undefined> = {
  bytedance: siBytedance,
  xiaomi: siXiaomi,
  huawei: siHuawei,
  sinaweibo: siSinaweibo,
  douyin: siTiktok,
  kuaishou: siKuaishou,
};

// Generic colored-circle monogram for brands not covered by LOCAL_PNG or
// simple-icons. The character + color is a plain design fallback, not a
// reproduction of the brand's trademarked artwork.
const MONOGRAM: Record<string, { char: string; bg: string }> = {};

export function BrandIcon({
  slug,
  size = 32,
  colorMode = "mono",
  className = "",
  title,
}: {
  slug: string;
  size?: number;
  colorMode?: "mono" | "brand";
  className?: string;
  title?: string;
}) {
  const localSrc = LOCAL_PNG[slug];
  if (localSrc) {
    return (
      // eslint-disable-next-line @next/next/no-img-element
      <img
        src={localSrc}
        alt={title ?? slug}
        style={{
          height: size,
          width: "auto",
          maxWidth: size * 3,
          objectFit: "contain",
        }}
        className={className}
        loading="lazy"
        decoding="async"
      />
    );
  }

  const icon = BRAND_ICONS[slug];
  if (icon) {
    return (
      <svg
        role="img"
        viewBox="0 0 24 24"
        width={size}
        height={size}
        fill={colorMode === "brand" ? `#${icon.hex}` : "currentColor"}
        className={className}
        aria-label={title ?? icon.title}
      >
        <title>{title ?? icon.title}</title>
        <path d={icon.path} />
      </svg>
    );
  }

  const mono = MONOGRAM[slug];
  if (mono) {
    return (
      <div
        role="img"
        aria-label={title ?? slug}
        title={title ?? slug}
        className={`inline-flex items-center justify-center rounded-full font-bold text-white ${className}`}
        style={{
          width: size,
          height: size,
          backgroundColor: mono.bg,
          fontSize: mono.char.length > 1 ? size * 0.4 : size * 0.5,
          lineHeight: 1,
        }}
      >
        {mono.char}
      </div>
    );
  }

  return null;
}
