import type { MetadataRoute } from "next";
import { siteBaseUrl } from "@/lib/briefs";

export default function robots(): MetadataRoute.Robots {
  const base = siteBaseUrl();
  return {
    rules: [
      {
        userAgent: "*",
        allow: ["/", "/nev", "/nev/d/"],
        disallow: ["/api/", "/manage", "/unsubscribe"],
      },
    ],
    sitemap: `${base}/sitemap.xml`,
    host: base,
  };
}
