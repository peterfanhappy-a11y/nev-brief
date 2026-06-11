import "@/lib/og-windows-fix";
import { ImageResponse } from "next/og";
import {
  fetchCandidates,
  fetchSalesCard,
  humanDate,
  isValidBriefDate,
} from "@/lib/briefs";
import { loadCjkFont } from "@/lib/og-font";
import { topicLabel } from "@/lib/topics";

export const runtime = "nodejs";
export const contentType = "image/png";
export const size = { width: 1200, height: 630 };
export const alt = "NEV 早报";

type Params = { date: string };

export default async function OGImage({ params }: { params: Params }) {
  const { date } = params;

  const dateHuman = isValidBriefDate(date) ? humanDate(date) : date;
  const candidates = isValidBriefDate(date) ? await fetchCandidates(date) : [];
  const salesCard =
    isValidBriefDate(date) && candidates && candidates.length > 0
      ? await fetchSalesCard(date, candidates)
      : [];

  const topItems = (candidates ?? [])
    .slice()
    .sort(
      (a, b) => (b.global_importance ?? 0) - (a.global_importance ?? 0),
    )
    .slice(0, 3);

  const topBrands = salesCard.slice(0, 5);
  const topicLabelsForOG = Array.from(
    new Set(topItems.flatMap((i) => i.topics).slice(0, 6).map(topicLabel)),
  );

  // Collect every glyph we'll actually render so Google Fonts returns a
  // subset font (a few KB instead of ~10MB).
  const textPayload =
    "🚗NEV 早报新能源汽车行业每日精选#·" +
    dateHuman +
    topItems.map((i) => i.title).join("") +
    topBrands.map((b) => b.brand_name + "万辆").join("") +
    topicLabelsForOG.join("") +
    "0123456789";

  const [regularFont, boldFont] = await Promise.all([
    loadCjkFont(400, textPayload),
    loadCjkFont(700, textPayload),
  ]);

  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          flexDirection: "column",
          background:
            "linear-gradient(135deg, #0066FF 0%, #003E99 100%)",
          color: "white",
          padding: "60px",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: "16px" }}>
          <div style={{ fontSize: "56px" }}>🚗</div>
          <div style={{ fontSize: "44px", fontWeight: 800 }}>NEV 早报</div>
        </div>
        <div
          style={{
            display: "flex",
            fontSize: "28px",
            opacity: 0.85,
            marginTop: "8px",
            marginBottom: "32px",
          }}
        >
          {`${dateHuman} · 新能源汽车行业每日精选`}
        </div>

        {topItems.length > 0 && (
          <div
            style={{
              display: "flex",
              flexDirection: "column",
              gap: "12px",
              backgroundColor: "rgba(255,255,255,0.10)",
              borderRadius: "16px",
              padding: "24px 28px",
              marginBottom: "20px",
            }}
          >
            {topItems.map((item, i) => (
              <div
                key={item.cluster_id}
                style={{
                  display: "flex",
                  alignItems: "flex-start",
                  gap: "12px",
                  fontSize: "26px",
                  lineHeight: 1.3,
                }}
              >
                <div
                  style={{
                    minWidth: "36px",
                    height: "36px",
                    background: "#00C896",
                    borderRadius: "8px",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    fontWeight: 700,
                    fontSize: "22px",
                  }}
                >
                  {i + 1}
                </div>
                <div style={{ flex: 1 }}>
                  {item.title.length > 38
                    ? item.title.slice(0, 38) + "…"
                    : item.title}
                </div>
              </div>
            ))}
          </div>
        )}

        {topBrands.length > 0 && (
          <div
            style={{
              display: "flex",
              flexWrap: "wrap",
              gap: "10px",
              marginBottom: "auto",
            }}
          >
            {topBrands.map((b) => (
              <div
                key={b.brand_code}
                style={{
                  display: "flex",
                  background: "rgba(255,255,255,0.18)",
                  padding: "8px 16px",
                  borderRadius: "999px",
                  fontSize: "20px",
                }}
              >
                {`${b.brand_name} ${(b.units / 10000).toFixed(1)}万`}
              </div>
            ))}
          </div>
        )}

        {topicLabelsForOG.length > 0 && (
          <div
            style={{
              display: "flex",
              flexWrap: "wrap",
              gap: "10px",
              marginTop: "auto",
            }}
          >
            {topicLabelsForOG.map((label) => (
              <div
                key={label}
                style={{
                  display: "flex",
                  background: "rgba(0,200,150,0.25)",
                  padding: "6px 14px",
                  borderRadius: "8px",
                  fontSize: "18px",
                }}
              >
                {`#${label}`}
              </div>
            ))}
          </div>
        )}
      </div>
    ),
    {
      ...size,
      fonts: [
        { name: "Noto Sans SC", data: regularFont, style: "normal", weight: 400 },
        { name: "Noto Sans SC", data: boldFont, style: "normal", weight: 700 },
      ],
    },
  );
}
