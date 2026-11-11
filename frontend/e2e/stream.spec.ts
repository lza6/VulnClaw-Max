import { expect, test } from "@playwright/test";

test("SSE disconnect shows a reconnecting banner", async ({ page }) => {
  await page.route("**/api/tasks/*/stream", (route) => route.abort());
  await page.goto("/");

  await page.locator("textarea").first().fill("example.com");
  await page.getByRole("button", { name: /快速/ }).first().click();
  const start = page.getByRole("button", { name: "开始", exact: true }).first();
  await expect(start).toBeEnabled();
  await start.click();

  await expect(page.getByTestId("stream-status")).toContainText("连接已断开", { timeout: 15_000 });
  await page.screenshot({ path: "e2e-artifacts/stream-reconnecting.png", fullPage: true });
});
