import { execFileSync } from "node:child_process";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { expect, test } from "@playwright/test";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
const CONFIG = path.join(ROOT, ".test-tmp", "e2e-config");

test("finding triage persists after a reload", async ({ page, request }) => {
  execFileSync("python", [path.join(path.dirname(fileURLToPath(import.meta.url)), "seed.py"), "https://example.com"], {
    cwd: ROOT,
    env: { ...process.env, VULNCLAW_CONFIG_DIR: CONFIG, PYTHONIOENCODING: "utf-8" },
  });

  await page.goto("/");
  await page.locator('button.nav-item[aria-label="发现"]').click();
  await page.locator("select").first().selectOption("https://example.com");
  const triage = page.locator(".finding-triage-row").first();
  await expect(triage).toBeVisible();

  await triage.locator("select").selectOption("confirmed");
  await expect
    .poll(async () => {
      const response = await request.get("/api/findings?target=https%3A%2F%2Fexample.com");
      const findings = (await response.json()) as Array<{ triage_status: string }>;
      return findings[0]?.triage_status;
    })
    .toBe("confirmed");

  await page.reload();
  await page.locator('button.nav-item[aria-label="发现"]').click();
  await page.locator("select").first().selectOption("https://example.com");
  await expect(page.locator(".finding-triage-row select").first()).toHaveValue("confirmed");
  await page.screenshot({ path: "e2e-artifacts/triage.png", fullPage: true });
});
