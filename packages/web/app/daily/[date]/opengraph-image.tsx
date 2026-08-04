import "@/lib/og-windows-fix";
import { ImageResponse } from "next/og";
import { notFound } from "next/navigation";

import { getPublishedBrief, isBriefDate } from "@/lib/ai-briefs";
import { loadCjkFont } from "@/lib/og-font";

export const runtime = "nodejs";
export const contentType = "image/png";
export const size = { width: 1200, height: 630 };
export const alt = "AIVIZENS AI 日报";

// These bounds keep worst-case full-width prose within the fixed 1200×630
// layout at the font sizes below. The ellipsis is included in each bound.
const SUBJECT_MAX_CODE_POINTS = 32;
const EDITORIAL_MAX_CODE_POINTS = 96;

type Params = Promise<{ date: string }>;

function fitCodePoints(value: string, maxCodePoints: number): string {
  const codePoints = Array.from(value);
  if (codePoints.length <= maxCodePoints) return value;
  return `${codePoints.slice(0, maxCodePoints - 1).join("")}…`;
}

export default async function OpenGraphImage({
  params,
}: {
  params: Params;
}) {
  const { date } = await params;
  if (!isBriefDate(date)) notFound();

  const brief = await getPublishedBrief(date);
  if (!brief) notFound();

  const subject = fitCodePoints(
    brief.content.subject,
    SUBJECT_MAX_CODE_POINTS,
  );
  const editorial = fitCodePoints(
    brief.content.editorial,
    EDITORIAL_MAX_CODE_POINTS,
  );
  const textPayload = [
    "AIVIZENS",
    brief.briefDate,
    subject,
    editorial,
  ].join("");
  let regularFont: ArrayBuffer;
  let boldFont: ArrayBuffer;

  try {
    [regularFont, boldFont] = await Promise.all([
      loadCjkFont(400, textPayload),
      loadCjkFont(700, textPayload),
    ]);
  } catch {
    console.error("[daily-og] CJK font unavailable");
    return new ImageResponse(
      (
        <div
          style={{
            width: "100%",
            height: "100%",
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            justifyContent: "center",
            gap: 32,
            color: "#111827",
            background:
              "linear-gradient(135deg, #eef2ff 0%, #ffffff 52%, #f5f3ff 100%)",
          }}
        >
          <div
            style={{
              display: "flex",
              fontSize: 72,
              fontWeight: 700,
              letterSpacing: "0.08em",
              color: "#4f46e5",
            }}
          >
            AIVIZENS
          </div>
          <div
            style={{
              display: "flex",
              fontSize: 36,
              color: "#6b7280",
            }}
          >
            {brief.briefDate}
          </div>
        </div>
      ),
      size,
    );
  }

  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          flexDirection: "column",
          justifyContent: "space-between",
          padding: "64px 72px",
          color: "#111827",
          background:
            "linear-gradient(135deg, #eef2ff 0%, #ffffff 52%, #f5f3ff 100%)",
          fontFamily: "Noto Sans SC",
        }}
      >
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
          }}
        >
          <div
            style={{
              display: "flex",
              fontSize: 36,
              fontWeight: 700,
              letterSpacing: "0.08em",
              color: "#4f46e5",
            }}
          >
            AIVIZENS
          </div>
          <div
            style={{
              display: "flex",
              fontSize: 27,
              color: "#6b7280",
            }}
          >
            {brief.briefDate}
          </div>
        </div>

        <div
          style={{
            display: "flex",
            flexDirection: "column",
            gap: 28,
          }}
        >
          <div
            style={{
              display: "flex",
              maxWidth: 1040,
              fontSize: 64,
              lineHeight: 1.18,
              fontWeight: 700,
              letterSpacing: "-0.02em",
            }}
          >
            {subject}
          </div>
          <div
            style={{
              display: "flex",
              maxWidth: 1000,
              fontSize: 30,
              lineHeight: 1.5,
              color: "#4b5563",
            }}
          >
            {editorial}
          </div>
        </div>
      </div>
    ),
    {
      ...size,
      fonts: [
        {
          name: "Noto Sans SC",
          data: regularFont,
          style: "normal",
          weight: 400,
        },
        {
          name: "Noto Sans SC",
          data: boldFont,
          style: "normal",
          weight: 700,
        },
      ],
    },
  );
}
