import { revalidatePath } from "next/cache";
import { NextResponse } from "next/server";
import { z } from "zod";

export const runtime = "nodejs";

const Body = z
  .object({
    briefDate: z.string().date(),
  })
  .strict();

const responseOptions = {
  headers: { "Cache-Control": "private, no-store" },
};

export async function POST(request: Request) {
  const secret = process.env.HOMEPAGE_REVALIDATE_SECRET?.trim();
  if (!secret || Buffer.byteLength(secret, "utf8") < 32) {
    return NextResponse.json(
      { error: "server_configuration" },
      { ...responseOptions, status: 500 },
    );
  }

  if (request.headers.get("authorization") !== `Bearer ${secret}`) {
    return NextResponse.json(
      { error: "unauthorized" },
      { ...responseOptions, status: 401 },
    );
  }

  let body: z.infer<typeof Body>;
  try {
    body = Body.parse(await request.json());
  } catch {
    return NextResponse.json(
      { error: "invalid_body" },
      { ...responseOptions, status: 400 },
    );
  }

  revalidatePath("/", "page");

  return NextResponse.json(
    { ok: true, briefDate: body.briefDate },
    responseOptions,
  );
}
