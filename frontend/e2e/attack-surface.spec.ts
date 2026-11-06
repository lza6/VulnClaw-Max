import { execFileSync } from "node:child_process";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { expect, test, type Page } from "@playwright/test";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(HERE, "..", "..");
const CONFIG = path.join(ROOT, ".test-tmp", "e2e-config");

function seedTarget(): void {
  execFileSync("python", [path.join(HERE, "seed.py"), "https://example.com"], {
    cwd: ROOT,
    env: { ...process.env, VULNCLAW_CONFIG_DIR: CONFIG, PYTHONIOENCODING: "utf-8" },
  });
}

async function openRiskPage(page: Page) {
  await page.goto("/");
  await page.locator('button.nav-item[aria-label="发现"]').click();
  await page.locator("select").first().selectOption("https://example.com");
}

test("attack surface view opens the 3D scene and keeps an equivalent table", async ({ page }) => {
  seedTarget();
  await openRiskPage(page);

  const panel = page.locator(".attack-surface");
  await expect(panel).toBeVisible();
  await expect(panel.getByRole("button")).toHaveAttribute("aria-expanded", "false");

  await panel.getByRole("button").click();
  await expect(panel.getByRole("button")).toHaveAttribute("aria-expanded", "true");
  await expect(panel.locator("canvas")).toBeVisible({ timeout: 20_000 });
  await expect(panel.getByRole("table")).toBeVisible();
  await expect(panel.getByRole("columnheader", { name: "发现" })).toBeVisible();

  await page.screenshot({ path: "e2e-artifacts/attack-surface-3d.png", fullPage: true });
});

test("attack surface view falls back to a static list when WebGL is unavailable", async ({ page }) => {
  seedTarget();
  await page.addInitScript(() => {
    const original = HTMLCanvasElement.prototype.getContext;
    HTMLCanvasElement.prototype.getContext = function patched(this: HTMLCanvasElement, id: string, options?: unknown) {
      if (String(id).startsWith("webgl")) return null;
      return original.call(this, id as never, options as never);
    } as typeof HTMLCanvasElement.prototype.getContext;
  });
  await openRiskPage(page);

  const panel = page.locator(".attack-surface");
  await panel.getByRole("button").click();
  await expect(panel.locator(".attack-surface-canvas .empty-state")).toContainText("WebGL");
  await expect(panel.locator("canvas")).toHaveCount(0);
  await expect(panel.getByRole("table")).toBeVisible();
});
