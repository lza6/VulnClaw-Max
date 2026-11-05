import { execFileSync } from "node:child_process";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { expect, test } from "@playwright/test";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
const CONFIG = path.join(ROOT, ".test-tmp", "e2e-config");

test("report center downloads SARIF with the right extension", async ({ page, request }) => {
  execFileSync("python", [path.join(path.dirname(fileURLToPath(import.meta.url)), "seed.py"), "https://example.com"], {
    cwd: ROOT,
    env: { ...process.env, VULNCLAW_CONFIG_DIR: CONFIG, PYTHONIOENCODING: "utf-8" },
  });

  await page.goto("/");
  await page.locator('button.nav-item[aria-label="报告"]').click();

  await page.locator('input[list="report-targets"]').fill("https://example.com");
  await page.getByRole("button", { name: "生成", exact: true }).first().click();
  await expect
    .poll(
      async () => {
        const reports = (await (await request.get("/api/reports")).json()) as Array<{ name: string }>;
        return reports.some((item) => item.name.includes("findings.sarif"));
      },
      { timeout: 30_000 },
    )
    .toBe(true);
  const dialog = page.getByRole("dialog");
  if (await dialog.isVisible().catch(() => false)) {
    await dialog.getByRole("button", { name: "关闭" }).click();
  }

  await page.reload();
  await page.locator('button.nav-item[aria-label="报告"]').click();
  await expect(page.getByText(/findings\.sarif/).first()).toBeVisible({ timeout: 30_000 });
  await page.locator(".report-filter-grid select").first().selectOption("sarif");
  const sarifRow = page.getByRole("button", { name: /findings\.sarif/ }).first();
  await expect(sarifRow).toBeVisible({ timeout: 15_000 });
  await sarifRow.click();

  const downloadPromise = page.waitForEvent("download");
  await page.getByRole("button", { name: "导出副本" }).click();
  const download = await downloadPromise;
  expect(download.suggestedFilename()).toMatch(/\.sarif$/);
  await page.screenshot({ path: "e2e-artifacts/report-sarif.png", fullPage: true });
});
