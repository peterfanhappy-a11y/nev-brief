import { getSupabaseAdmin } from "@/lib/supabase";

export type Candidate = {
  rank: number;
  cluster_id: string;
  title: string;
  summary: string;
  brands: string[];
  topics: string[];
  key_data?: { type: string; values: Record<string, unknown> };
  source_links: { name: string; url: string }[];
  primary_source: string;
  source_count: number;
  global_importance?: number;
};

export type SalesRow = {
  brand_code: string;
  brand_name: string;
  units: number;
  yoy: number | null;
  wow: number | null;
};

const DATE_RE = /^\d{4}-\d{2}-\d{2}$/;

export function isValidBriefDate(date: string): boolean {
  if (!DATE_RE.test(date)) return false;
  const d = new Date(date + "T00:00:00Z");
  return !isNaN(d.getTime());
}

export async function fetchCandidates(briefDate: string): Promise<Candidate[] | null> {
  const sb = getSupabaseAdmin();
  const { data, error } = await sb
    .from("daily_briefs")
    .select("candidates")
    .eq("brief_date", briefDate)
    .maybeSingle();
  if (error) {
    console.error("[briefs] fetch_candidates", error);
    return null;
  }
  if (!data) return null;
  const arr = (data.candidates as Candidate[] | null) ?? [];
  return arr;
}

/**
 * Sales-card rows for the given date. Mirrors composer/sales_card.py:
 * - Prefer canonical vehicle_sales_daily rows (latest week_date <= brief_date).
 * - Fall back to candidate key_data.values.brand_sales when the table is empty.
 * Returns sorted by units desc, capped at 10.
 */
export async function fetchSalesCard(
  briefDate: string,
  candidates: Candidate[],
): Promise<SalesRow[]> {
  const sb = getSupabaseAdmin();
  const { data, error } = await sb
    .from("vehicle_sales_daily")
    .select("brand_code, brand_name, units, yoy, wow, week_date")
    .lte("week_date", briefDate)
    .order("week_date", { ascending: false });

  let rows: SalesRow[] = [];
  if (!error && data && data.length > 0) {
    const seen = new Set<string>();
    for (const r of data) {
      if (seen.has(r.brand_code)) continue;
      seen.add(r.brand_code);
      rows.push({
        brand_code: r.brand_code,
        brand_name: r.brand_name,
        units: r.units,
        yoy: r.yoy,
        wow: r.wow,
      });
    }
  }

  if (rows.length === 0) {
    const byBrand = new Map<string, SalesRow>();
    for (const c of candidates) {
      const kd = c.key_data;
      if (!kd || kd.type !== "sales") continue;
      const values = kd.values as { brand_sales?: unknown } | undefined;
      const bs = values?.brand_sales;
      if (!Array.isArray(bs)) continue;
      for (const r of bs) {
        if (typeof r !== "object" || r === null) continue;
        const row = r as Record<string, unknown>;
        const brand = typeof row.brand === "string" ? row.brand : null;
        const units = typeof row.units === "number" ? row.units : null;
        if (!brand || units == null || units <= 0) continue;
        const yoyPct = typeof row.yoy_pct === "number" ? row.yoy_pct : null;
        const existing = byBrand.get(brand);
        if (!existing || existing.units < units) {
          byBrand.set(brand, {
            brand_code: brand,
            brand_name: brand,
            units,
            yoy: yoyPct != null ? yoyPct / 100 : null,
            wow: null,
          });
        }
      }
    }
    rows = Array.from(byBrand.values());
  }

  rows.sort((a, b) => b.units - a.units);
  return rows.slice(0, 10);
}

export function findCandidateByPrefix(
  candidates: Candidate[],
  idPrefix: string,
): Candidate | null {
  const p = idPrefix.toLowerCase();
  return (
    candidates.find((c) => c.cluster_id.toLowerCase().startsWith(p)) ?? null
  );
}

export function humanDate(briefDate: string): string {
  const [y, m, d] = briefDate.split("-");
  return `${y}年${parseInt(m, 10)}月${parseInt(d, 10)}日`;
}

export function siteBaseUrl(): string {
  return (
    process.env.WEB_BASE_URL ??
    process.env.NEXT_PUBLIC_WEB_BASE_URL ??
    "https://aivizens.com"
  );
}

/**
 * Closest brief_date strictly before and after `briefDate` in daily_briefs.
 * Used to render prev/next day navigation; nulls when none exists. Caller
 * should handle the empty-day case at the destination page (it already
 * renders the "尚未生成" empty card).
 */
export async function fetchNeighborDates(briefDate: string): Promise<{
  prev: string | null;
  next: string | null;
}> {
  const sb = getSupabaseAdmin();
  const [prevRes, nextRes] = await Promise.all([
    sb
      .from("daily_briefs")
      .select("brief_date")
      .lt("brief_date", briefDate)
      .order("brief_date", { ascending: false })
      .limit(1)
      .maybeSingle(),
    sb
      .from("daily_briefs")
      .select("brief_date")
      .gt("brief_date", briefDate)
      .order("brief_date", { ascending: true })
      .limit(1)
      .maybeSingle(),
  ]);
  return {
    prev: prevRes.data?.brief_date ?? null,
    next: nextRes.data?.brief_date ?? null,
  };
}

export function formatUnits(n: number): string {
  return n.toLocaleString("en-US");
}

export function formatYoyPct(yoy: number): string {
  const pct = Math.round(yoy * 100);
  return pct > 0 ? `+${pct}%` : `${pct}%`;
}
