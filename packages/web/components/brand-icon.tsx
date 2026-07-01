// Brand logo renderer.
//
// For brands in the simple-icons OSS package (https://simpleicons.org — brand
// owners contribute or approve their SVGs), we reference the icon by name and
// let the package own the actual artwork. Brands that aren't in the package
// yet fall back to a plain colored-circle monogram (a generic design, not the
// brand's trademark).
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

// Generic colored-circle monogram for brands not (yet) in simple-icons, or
// where simple-icons only carries a sub-brand (alibabacloud, tencentqq) that
// misrepresents the parent company. The character + color here is a plain
// design fallback, not a reproduction of the brand's trademarked logo.
const MONOGRAM: Record<string, { char: string; bg: string }> = {
  alibaba: { char: "阿", bg: "#FF6A00" },
  tencent: { char: "腾", bg: "#0052D9" },
  deepseek: { char: "DS", bg: "#4D6BFE" },
  xiaohongshu: { char: "红", bg: "#FE2C55" },
};

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
