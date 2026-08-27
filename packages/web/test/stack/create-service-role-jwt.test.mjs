import { createHmac } from "node:crypto";
import test from "node:test";
import assert from "node:assert/strict";
import { createServiceRoleJwt } from "./create-service-role-jwt.mjs";

const secret = "integration-test-only-postgrest-jwt-secret-32-bytes";

function decodeJson(segment) {
  return JSON.parse(Buffer.from(segment, "base64url").toString("utf8"));
}

test("creates a signed PostgREST service-role JWT without production credentials", () => {
  const token = createServiceRoleJwt(secret);
  const [header, payload, signature] = token.split(".");

  assert.deepEqual(decodeJson(header), { alg: "HS256", typ: "JWT" });
  assert.deepEqual(decodeJson(payload), {
    role: "service_role",
    iss: "aivizens-integration-test",
  });
  assert.equal(
    signature,
    createHmac("sha256", secret)
      .update(`${header}.${payload}`)
      .digest("base64url"),
  );
});
