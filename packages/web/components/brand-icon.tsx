// Brand logo renderer with two-tier resolution:
//   1. LOCAL_ASSET — optimized web asset in /public/brand/companies/web/ (preferred)
//   2. MONOGRAM  — generic colored-circle + character fallback (currently empty;
//                  every brand in use has an optimized asset)
type MonogramSpec = { char: string; bg: string };

// Original PNGs remain at their existing paths for previously sent emails.
const LOCAL_ASSET: Record<string, string> = {
  bytedance: "/brand/companies/web/bytedance-v1.webp",
  alibaba: "/brand/companies/web/alibaba-v1.webp",
  tencent: "/brand/companies/web/tencent-v1.webp",
  deepseek: "/brand/companies/web/deepseek-v1.webp",
  xiaomi: "/brand/companies/web/xiaomi-v1.webp",
  huawei: "/brand/companies/web/huawei-v1.webp",
  weibo: "/brand/companies/web/weibo-v1.webp",
  wechat: "/brand/companies/web/wechat-v1.webp",
  douyin: "/brand/companies/web/douyin-v1.webp",
  xiaohongshu: "/brand/companies/web/xiaohongshu-v1.webp",
};

const MONOGRAM: Record<string, MonogramSpec> = {};

export function BrandIcon({
  slug,
  size = 32,
  className = "",
  title,
}: {
  slug: string;
  size?: number;
  className?: string;
  title?: string;
}) {
  const localSrc = LOCAL_ASSET[slug];
  if (localSrc) {
    return (
      // eslint-disable-next-line @next/next/no-img-element
      <img
        src={localSrc}
        alt={title ?? slug}
        style={{
          height: size,
          width: "auto",
          maxWidth: size * 3.5,
          objectFit: "contain",
        }}
        className={className}
        loading="lazy"
        decoding="async"
      />
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
