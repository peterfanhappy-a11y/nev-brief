import "@/lib/og-windows-fix";
import { ImageResponse } from "next/og";
import {
  fetchCandidates,
  findCandidateByPrefix,
  humanDate,
  isValidBriefDate,
} from "@/lib/briefs";
import { loadCjkFont } from "@/lib/og-font";
import { topicLabel } from "@/lib/topics";

export const runtime = "nodejs";
export const contentType = "image/png";
export const size = { width: 1200, height: 630 };
export const alt = "NEV 早报";

type Params = { date: string; id: string };

const ID_PREFIX_RE = /^[0-9a-f]{4,32}$/i;

export default async function OGImage({ params }: { params: Params }) {
  const { date, id } = params;

  if (!isValidBriefDate(date) || !ID_PREFIX_RE.test(id)) {
    const fallbackFont = await loadCjkFont(700, "NEV 早报");
    return new ImageResponse(
      <div style={{ fontSize: "60px" }}>NEV 早报</div>,
      {
        ...size,
        fonts: [
          { name: "Noto Sans SC", data: fallbackFont, style: "normal", weight: 700 },
        ],
      },
    );
  }

  const candidates = await fetchCandidates(date);
  const item = candidates ? findCandidateByPrefix(candidates, id) : null;
  const dateHuman = humanDate(date);

  if (!item) {
    const fallbackText = `🚗 NEV 早报 · ${dateHuman}`;
    const fallbackFont = await loadCjkFont(700, fallbackText);
    return new ImageResponse(
      (
        <div
          style={{
            width: "100%",
            height: "100%",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            background: "linear-gradient(135deg, #0066FF 0%, #003E99 100%)",
            color: "white",
            fontSize: "60px",
          }}
        >
          {fallbackText}
        </div>
      ),
      {
        ...size,
        fonts: [
          { name: "Noto Sans SC", data: fallbackFont, style: "normal", weight: 700 },
        ],
      },
    );
  }

  const topicLabels = Array.from(
    new Set(item.topics.slice(0, 5).map(topicLabel)),
  );
  const brands = item.brands.slice(0, 4);
  const summary =
    item.summary.length > 140
      ? item.summary.slice(0, 140) + "…"
      : item.summary;
  const titleClipped =
    item.title.length > 60 ? item.title.slice(0, 60) + "…" : item.title;

  const textPayload =
    "🚗NEV 早报·· aivizens.com📰" +
    dateHuman +
    titleClipped +
    summary +
    topicLabels.join("#") +
    brands.join("") +
    (item.primary_source || "多源汇总") +
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
          background: "white",
          padding: "56px 64px",
        }}
      >
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: "12px",
            color: "#0066FF",
            fontSize: "26px",
            fontWeight: 700,
          }}
        >
          <span style={{ display: "flex" }}>🚗 NEV 早报</span>
          <span style={{ display: "flex", color: "#999", fontSize: "20px", fontWeight: 400 }}>
            {`· ${dateHuman}`}
          </span>
        </div>

        <div
          style={{
            display: "flex",
            flexWrap: "wrap",
            gap: "8px",
            marginTop: "28px",
            marginBottom: "20px",
          }}
        >
          {topicLabels.map((t) => (
            <div
              key={t}
              style={{
                display: "flex",
                background: "rgba(0,200,150,0.12)",
                color: "#00A87C",
                padding: "6px 14px",
                borderRadius: "8px",
                fontSize: "20px",
              }}
            >
              {`#${t}`}
            </div>
          ))}
          {brands.map((b) => (
            <div
              key={b}
              style={{
                display: "flex",
                background: "rgba(0,102,255,0.12)",
                color: "#0066FF",
                padding: "6px 14px",
                borderRadius: "8px",
                fontSize: "20px",
              }}
            >
              {b}
            </div>
          ))}
        </div>

        <div
          style={{
            fontSize: "46px",
            fontWeight: 800,
            color: "#1a1a1a",
            lineHeight: 1.25,
            marginBottom: "24px",
          }}
        >
          {titleClipped}
        </div>

        <div
          style={{
            fontSize: "24px",
            color: "#4a4a4a",
            lineHeight: 1.5,
            marginBottom: "auto",
          }}
        >
          {summary}
        </div>

        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            fontSize: "20px",
            color: "#999",
            borderTop: "1px solid #eee",
            paddingTop: "20px",
          }}
        >
          <div style={{ display: "flex" }}>{`📰 ${item.primary_source || "多源汇总"}`}</div>
          <div style={{ display: "flex" }}>aivizens.com</div>
        </div>
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
