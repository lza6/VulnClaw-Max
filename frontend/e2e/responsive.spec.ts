import { expect, test } from "@playwright/test";

const VIEWS = ["home", "risk", "reports", "boundary", "history", "plugins", "settings", "advanced"] as const;

for (const width of [768, 1024]) {
  test(`views do not overflow at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 });
    for (const view of VIEWS) {
      await page.goto(`/#${view}`);
      await expect(page.locator(".view-mount")).toBeVisible({ timeout: 15_000 });
      const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
      expect(overflow, `${view} overflows horizontally`).toBeLessThanOrEqual(1);
    }
    await page.screenshot({ path: `e2e-artifacts/responsive-${width}.png`, fullPage: true });
  });
}
