import { createHmac } from "node:crypto";
import { pathToFileURL } from "node:url";

function encodeJson(value) {
  return Buffer.from(JSON.stringify(value)).toString("base64url");
}

export function createServiceRoleJwt(secret) {
  if (typeof secret !== "string" || Buffer.byteLength(secret) < 32) {
    throw new Error("AIVIZENS_TEST_JWT_SECRET must be at least 32 bytes");
  }

  const header = encodeJson({ alg: "HS256", typ: "JWT" });
  const payload = encodeJson({
    role: "service_role",
    iss: "aivizens-integration-test",
  });
  const signature = createHmac("sha256", secret)
    .update(`${header}.${payload}`)
    .digest("base64url");
  return `${header}.${payload}.${signature}`;
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  process.stdout.write(createServiceRoleJwt(process.env.AIVIZENS_TEST_JWT_SECRET));
}
