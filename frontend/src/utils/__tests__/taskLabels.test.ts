import { describe, expect, it } from "vitest";
import { formatTaskStatus } from "../taskLabels";

describe("formatTaskStatus", () => {
  it("leaves unknown statuses untouched", () => {
    expect(formatTaskStatus("mystery-state")).toBe("mystery-state");
  });

  it("maps known statuses to a non-key label", () => {
    const label = formatTaskStatus("running");
    expect(label).not.toBe("status.running");
    expect(label.length).toBeGreaterThan(0);
  });
});
