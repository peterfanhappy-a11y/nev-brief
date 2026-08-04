import type { MetadataRoute } from "next";

import { siteBaseUrl } from "@/lib/site-url";

export default function robots(): MetadataRoute.Robots {
  const base = siteBaseUrl();
  return {
    rules: [
      {
        userAgent: "*",
        allow: ["/", "/daily/"],
        disallow: [
          "/confirm",
          "/unsubscribe",
          "/rate",
          "/api",
          "/preview",
        ],
      },
    ],
    sitemap: `${base}/sitemap.xml`,
    host: base,
  };
}
