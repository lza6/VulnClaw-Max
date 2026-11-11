import { expect, test } from "@playwright/test";

const VIEWS = ["home", "risk", "reports", "boundary", "history", "plugins", "settings", "advanced"] as const;

test("no console errors across the eight views", async ({ page }) => {
  const errors: string[] = [];
  page.on("console", (message) => {
    if (message.type() === "error") errors.push(message.text());
  });
  page.on("pageerror", (error) => errors.push(error.message));
  for (const view of VIEWS) {
    await page.goto(`/#${view}`);
    await expect(page.locator(".view-mount")).toBeVisible({ timeout: 15_000 });
  }
  expect(errors, errors.join("\n")).toEqual([]);
});
