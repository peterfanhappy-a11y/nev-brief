import { createServer } from "node:http";
import assert from "node:assert/strict";
import test from "node:test";
import { createSupabaseRestProxy } from "./supabase-rest-proxy.mjs";

function listen(server) {
  return new Promise((resolve, reject) => {
    server.once("error", reject);
    server.listen(0, "127.0.0.1", () => {
      const address = server.address();
      if (!address || typeof address === "string") {
        reject(new Error("test server has no TCP address"));
        return;
      }
      resolve(`http://127.0.0.1:${address.port}`);
    });
  });
}

function close(server) {
  return new Promise((resolve, reject) => {
    server.close((error) => (error ? reject(error) : resolve()));
  });
}

test("maps only Supabase /rest/v1 requests to the PostgREST root", async () => {
  const upstreamRequests = [];
  const upstream = createServer((request, response) => {
    const chunks = [];
    request.on("data", (chunk) => chunks.push(chunk));
    request.on("end", () => {
      upstreamRequests.push({
        method: request.method,
        url: request.url,
        contentType: request.headers["content-type"],
        authorization: request.headers.authorization,
        body: Buffer.concat(chunks).toString("utf8"),
      });
      response.writeHead(200, { "content-type": "application/json" });
      response.end(JSON.stringify({ ok: true }));
    });
  });
  const upstreamUrl = await listen(upstream);
  const proxy = createSupabaseRestProxy({ upstreamUrl });
  const proxyUrl = await listen(proxy);

  try {
    const mapped = await fetch(
      `${proxyUrl}/rest/v1/ai_subscribers?select=id%2Cstatus`,
      {
        method: "POST",
        headers: {
          "content-type": "application/json",
          authorization: "Bearer signed-test-token",
        },
        body: JSON.stringify({ email: "proxy-test@example.com" }),
      },
    );
    assert.equal(mapped.status, 200);
    assert.deepEqual(await mapped.json(), { ok: true });
    assert.deepEqual(upstreamRequests, [
      {
        method: "POST",
        url: "/ai_subscribers?select=id%2Cstatus",
        contentType: "application/json",
        authorization: "Bearer signed-test-token",
        body: JSON.stringify({ email: "proxy-test@example.com" }),
      },
    ]);

    const unrelated = await fetch(`${proxyUrl}/auth/v1/user`);
    assert.equal(unrelated.status, 404);
    assert.deepEqual(upstreamRequests, [
      {
        method: "POST",
        url: "/ai_subscribers?select=id%2Cstatus",
        contentType: "application/json",
        authorization: "Bearer signed-test-token",
        body: JSON.stringify({ email: "proxy-test@example.com" }),
      },
    ]);
  } finally {
    await close(proxy);
    await close(upstream);
  }
});
