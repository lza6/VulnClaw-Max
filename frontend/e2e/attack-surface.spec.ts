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
  await page.getByTestId("risk-target-select").selectOption("https://example.com");
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

test.describe("reduced motion", () => {
  test.use({ reducedMotion: "reduce" });

  test("renders a static SVG topology instead of the 3D canvas", async ({ page }) => {
    seedTarget();
    await openRiskPage(page);
    const panel = page.locator(".attack-surface");
    await panel.getByRole("button").click();
    await expect(panel.locator("svg.attack-surface-static")).toBeVisible();
    await expect(panel.locator("canvas")).toHaveCount(0);
    await expect(panel.getByRole("table")).toBeVisible();
  });
});

test("3D scene keeps a 50fps browser frame budget while dragging", async ({ page }) => {
  seedTarget();
  await openRiskPage(page);
  const panel = page.locator(".attack-surface");
  await panel.getByRole("button").click();
  const canvas = panel.locator("canvas");
  await expect(canvas).toBeVisible({ timeout: 20_000 });

  const fps = await page.evaluate(async () => {
    const element = document.querySelector(".attack-surface canvas") as HTMLCanvasElement | null;
    if (!element) return 0;
    const rect = element.getBoundingClientRect();
    const fire = (type: string, x: number, y: number) =>
      element.dispatchEvent(
        new PointerEvent(type, {
          clientX: rect.left + x,
          clientY: rect.top + y,
          bubbles: true,
          pointerId: 1,
          pointerType: "mouse",
          buttons: 1,
        }),
      );
    fire("pointerdown", rect.width / 2, rect.height / 2);
    const deltas: number[] = [];
    let last = performance.now();
    for (let index = 0; index < 60; index += 1) {
      await new Promise((resolve) => requestAnimationFrame(resolve));
      fire("pointermove", rect.width / 2 + index, rect.height / 2);
      const now = performance.now();
      deltas.push(now - last);
      last = now;
    }
    fire("pointerup", rect.width / 2, rect.height / 2);
    const average = deltas.reduce((sum, value) => sum + value, 0) / deltas.length;
    return 1000 / average;
  });
  expect(fps).toBeGreaterThanOrEqual(50);
  await page.screenshot({ path: "e2e-artifacts/attack-surface-fps.png", fullPage: true });
});

test.describe("touch input", () => {
  test.use({ hasTouch: true, viewport: { width: 390, height: 844 } });

  test("touch drag on the 3D canvas keeps the scene mounted", async ({ page }) => {
    seedTarget();
    await openRiskPage(page);
    const panel = page.locator(".attack-surface");
    await panel.getByRole("button").click();
    const canvas = panel.locator("canvas");
    await expect(canvas).toBeVisible({ timeout: 20_000 });

    await page.evaluate(() => {
      const element = document.querySelector(".attack-surface canvas") as HTMLCanvasElement | null;
      if (!element) return;
      const rect = element.getBoundingClientRect();
      const fire = (type: string, x: number, y: number) =>
        element.dispatchEvent(
          new PointerEvent(type, {
            clientX: rect.left + x,
            clientY: rect.top + y,
            bubbles: true,
            pointerId: 7,
            pointerType: "touch",
            isPrimary: true,
            buttons: 1,
          }),
        );
      fire("pointerdown", rect.width / 2, rect.height / 2);
      fire("pointermove", rect.width / 2 + 40, rect.height / 2 + 10);
      fire("pointermove", rect.width / 2 + 80, rect.height / 2 + 20);
      fire("pointerup", rect.width / 2 + 80, rect.height / 2 + 20);
    });

    await expect(canvas).toBeVisible();
    await expect(panel.getByRole("table")).toBeVisible();
    await page.screenshot({ path: "e2e-artifacts/attack-surface-touch.png", fullPage: true });
  });
});
