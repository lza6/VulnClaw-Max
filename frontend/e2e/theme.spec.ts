import { expect, test, type Page } from "@playwright/test";

const VIEWS = ["home", "risk", "reports", "boundary", "history", "plugins", "settings", "advanced"] as const;
const STORAGE_KEY = "vulnclaw.ui.preferences";

const BASE_PREFERENCES = {
  language: "zh-CN",
  defaultCheckMode: "standard",
  reportFormat: "markdown",
  reportTemplate: "pentest",
  showTechnicalLogs: false,
  theme: "auto",
  defaultBoundary: { onlyPort: "", onlyHost: "", onlyPath: "", blockedHost: "", blockedPath: "", allowActions: [], blockActions: [] },
};

/** 只在存储为空时写入，才能验证"切换后刷新仍保持"这类持久化行为。 */
async function seedTheme(page: Page, theme: "auto" | "light" | "dark") {
  await page.addInitScript(
    ({ key, preferences }) => {
      if (!window.localStorage.getItem(key)) {
        window.localStorage.setItem(key, JSON.stringify(preferences));
      }
    },
    { key: STORAGE_KEY, preferences: { ...BASE_PREFERENCES, theme } },
  );
}

test("appearance section switches theme, persists it and syncs theme-color", async ({ page }) => {
  await page.emulateMedia({ colorScheme: "light" });
  await seedTheme(page, "auto");
  await page.goto("/#settings");
  await expect(page.locator("html")).toHaveAttribute("data-theme", "light");

  await page.getByRole("button", { name: /外观/ }).click();
  await page.getByLabel("界面主题").selectOption("dark");

  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
  await expect(page.locator('meta[name="theme-color"]')).toHaveAttribute("content", "#0b1220");
  const stored = await page.evaluate((key) => JSON.parse(window.localStorage.getItem(key) ?? "{}").theme, STORAGE_KEY);
  expect(stored).toBe("dark");

  await page.reload();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
});

test("auto theme follows the system colour scheme", async ({ page }) => {
  await page.emulateMedia({ colorScheme: "dark" });
  await seedTheme(page, "auto");
  await page.goto("/");
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");

  await page.emulateMedia({ colorScheme: "light" });
  await expect(page.locator("html")).toHaveAttribute("data-theme", "light");
});

for (const theme of ["light", "dark"] as const) {
  test(`every view renders in ${theme} theme`, async ({ page }) => {
    await page.emulateMedia({ colorScheme: theme });
    await seedTheme(page, theme);
    for (const view of VIEWS) {
      await page.goto(`/#${view}`);
      await expect(page.locator("html")).toHaveAttribute("data-theme", theme);
      await page.waitForTimeout(150);
      await page.screenshot({ path: `e2e-artifacts/theme-${theme}-${view}.png`, fullPage: true });
    }
  });
}
