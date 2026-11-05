import { afterEach, describe, expect, it, vi } from "vitest";
import { getTasks } from "../web";

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("requestJson error handling", () => {
  it("surfaces JSON detail messages", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify({ detail: "backend exploded" }), {
          status: 500,
          headers: { "content-type": "application/json" },
        }),
      ),
    );
    await expect(getTasks()).rejects.toThrow(/backend exploded/);
  });

  it("rejects non-JSON success bodies", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response("<html>", { status: 200, headers: { "content-type": "text/html" } }),
      ),
    );
    await expect(getTasks()).rejects.toThrow(/non-JSON/);
  });

  it("reports an unreachable backend", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("offline")));
    await expect(getTasks()).rejects.toThrow(/Unable to reach/);
  });
});
