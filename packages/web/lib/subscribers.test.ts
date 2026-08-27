import { describe, expect, it } from "vitest";
import { parseProduct, productLabel } from "./subscribers";

describe("subscriber helpers", () => {
  it("maps AI product labels", () => {
    expect(parseProduct("ai")).toBe("ai");
    expect(productLabel("ai")).toBe("AIVIZENS · AI 趋势");
  });
});
