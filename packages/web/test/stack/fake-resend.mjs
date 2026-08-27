import { createServer } from "node:http";

const port = Number(process.env.AIVIZENS_TEST_RESEND_PORT ?? "55438");
const messages = [];
const attempts = [];
let failuresRemaining = 0;

function json(response, status, value) {
  response.writeHead(status, { "content-type": "application/json" });
  response.end(JSON.stringify(value));
}

async function body(request) {
  const chunks = [];
  for await (const chunk of request) chunks.push(chunk);
  if (chunks.length === 0) return {};
  return JSON.parse(Buffer.concat(chunks).toString("utf8"));
}

const server = createServer(async (request, response) => {
  const url = new URL(request.url ?? "/", `http://127.0.0.1:${port}`);

  try {
    if (request.method === "GET" && url.pathname === "/health") {
      return json(response, 200, { ok: true });
    }
    if (request.method === "GET" && url.pathname === "/_test/messages") {
      return json(response, 200, messages);
    }
    if (request.method === "GET" && url.pathname === "/_test/attempts") {
      return json(response, 200, attempts);
    }
    if (request.method === "DELETE" && url.pathname === "/_test/messages") {
      messages.length = 0;
      attempts.length = 0;
      failuresRemaining = 0;
      response.writeHead(204);
      return response.end();
    }
    if (request.method === "POST" && url.pathname === "/_test/fail-next") {
      const payload = await body(request);
      if (!Number.isInteger(payload.count) || payload.count < 0 || payload.count > 20) {
        return json(response, 400, { name: "validation_error", message: "invalid count" });
      }
      failuresRemaining = payload.count;
      response.writeHead(204);
      return response.end();
    }
    if (request.method === "POST" && url.pathname === "/emails") {
      const payload = await body(request);
      const idempotencyKey = request.headers["idempotency-key"] ?? null;
      attempts.push({
        id: `attempt-${attempts.length + 1}`,
        body: payload,
        idempotencyKey,
      });
      if (failuresRemaining > 0) {
        failuresRemaining -= 1;
        return json(response, 503, {
          name: "application_error",
          message: "fake transport unavailable",
        });
      }
      const id = `email-${messages.length + 1}`;
      messages.push({
        id,
        body: payload,
        idempotencyKey,
      });
      return json(response, 200, { id });
    }
    return json(response, 404, { name: "not_found", message: "not found" });
  } catch {
    return json(response, 400, { name: "validation_error", message: "invalid JSON" });
  }
});

server.listen(port, "127.0.0.1", () => {
  process.stdout.write(`fake Resend listening on 127.0.0.1:${port}\n`);
});

function shutdown() {
  server.close(() => process.exit(0));
}

process.on("SIGINT", shutdown);
process.on("SIGTERM", shutdown);
