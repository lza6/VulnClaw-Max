import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";

const here = dirname(fileURLToPath(import.meta.url));
const css = readFileSync(resolve(here, "../../styles.css"), "utf-8");

describe("design token budget", () => {
  it("does not add new hard-coded hex colors", () => {
    const unique = new Set(css.match(/#[0-9a-fA-F]{3,8}\b/g) ?? []);
    expect(unique.size).toBeLessThanOrEqual(37);
  });

  it("keeps the semantic token surface at least as broad as before", () => {
    expect(css.match(/var\(--/g)?.length ?? 0).toBeGreaterThanOrEqual(365);
  });
});
