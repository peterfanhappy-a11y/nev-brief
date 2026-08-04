const PRODUCTION_SITE_URL = "https://aivizens.com";

export function siteBaseUrl(): string {
  const configured =
    process.env.WEB_BASE_URL ||
    process.env.NEXT_PUBLIC_WEB_BASE_URL ||
    PRODUCTION_SITE_URL;

  return configured.replace(/\/+$/, "");
}
