import http, { createServer } from "node:http";
import https from "node:https";
import { pathToFileURL } from "node:url";

const HOP_BY_HOP_HEADERS = new Set([
  "connection",
  "keep-alive",
  "proxy-authenticate",
  "proxy-authorization",
  "te",
  "trailer",
  "transfer-encoding",
  "upgrade",
]);

function forwardedHeaders(headers, host) {
  const result = {};
  for (const [name, value] of Object.entries(headers)) {
    if (!HOP_BY_HOP_HEADERS.has(name) && value !== undefined) {
      result[name] = value;
    }
  }
  if (host) result.host = host;
  return result;
}

function mappedPath(requestUrl) {
  const url = new URL(requestUrl ?? "/", "http://supabase.test");
  if (url.pathname !== "/rest/v1" && !url.pathname.startsWith("/rest/v1/")) {
    return null;
  }
  const pathname = url.pathname.slice("/rest/v1".length) || "/";
  return `${pathname}${url.search}`;
}

export function createSupabaseRestProxy({ upstreamUrl }) {
  const upstream = new URL(upstreamUrl);
  if (upstream.protocol !== "http:" && upstream.protocol !== "https:") {
    throw new Error("PostgREST upstream URL must use http or https");
  }
  const requestUpstream = upstream.protocol === "https:" ? https.request : http.request;

  return createServer((request, response) => {
    const path = mappedPath(request.url);
    if (path === null) {
      response.writeHead(404, { "content-type": "application/json" });
      response.end(JSON.stringify({ message: "test proxy route not found" }));
      return;
    }

    const upstreamRequest = requestUpstream(
      upstream,
      {
        method: request.method,
        path,
        headers: forwardedHeaders(request.headers, upstream.host),
      },
      (upstreamResponse) => {
        response.writeHead(
          upstreamResponse.statusCode ?? 502,
          forwardedHeaders(upstreamResponse.headers),
        );
        upstreamResponse.pipe(response);
      },
    );

    upstreamRequest.on("error", () => {
      if (!response.headersSent) {
        response.writeHead(502, { "content-type": "application/json" });
      }
      response.end(JSON.stringify({ message: "test PostgREST upstream unavailable" }));
    });
    request.pipe(upstreamRequest);
  });
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  const upstreamUrl = process.env.AIVIZENS_TEST_POSTGREST_URL;
  const port = Number.parseInt(process.env.AIVIZENS_TEST_REST_PORT ?? "55437", 10);
  if (!upstreamUrl || !Number.isInteger(port) || port < 1 || port > 65535) {
    throw new Error("test proxy requires AIVIZENS_TEST_POSTGREST_URL and a valid port");
  }
  createSupabaseRestProxy({ upstreamUrl }).listen(port, "127.0.0.1", () => {
    process.stdout.write(`Supabase REST test proxy listening on 127.0.0.1:${port}\n`);
  });
}
