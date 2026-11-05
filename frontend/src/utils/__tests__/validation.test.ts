import { describe, expect, it } from "vitest";
import { parseOptionalPort } from "../validation";

describe("parseOptionalPort", () => {
  it("returns undefined for blank input", () => {
    expect(parseOptionalPort("  ")).toBeUndefined();
  });

  it("accepts the valid boundaries", () => {
    expect(parseOptionalPort("1")).toBe(1);
    expect(parseOptionalPort("65535")).toBe(65535);
  });

  it("rejects zero, overflow, and non-numeric input", () => {
    expect(() => parseOptionalPort("0")).toThrow();
    expect(() => parseOptionalPort("65536")).toThrow();
    expect(() => parseOptionalPort("80a")).toThrow();
  });
});
