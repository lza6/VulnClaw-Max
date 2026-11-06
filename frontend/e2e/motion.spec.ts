import { expect, test } from "@playwright/test";

test.use({ reducedMotion: "reduce" });

test("reduced motion keeps every interaction working and animations at zero", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: /欢迎使用 VulnClaw/ })).toBeVisible();

  // 视图挂载后立即可见：reduce 下不允许靠动画"淡进来"
  await expect(page.locator(".view-mount")).toHaveCSS("opacity", "1");

  // 过渡时长被全局 reduced-motion 兜底压到接近 0（计算值可能是 1e-05s 这种写法）
  const duration = await page.locator(".primary-btn").first().evaluate((el) => getComputedStyle(el).transitionDuration);
  const seconds = duration.split(",").map((part) => Number.parseFloat(part));
  expect(Math.max(...seconds)).toBeLessThan(0.001);

  await page.locator("textarea").first().fill("example.com");
  await page.getByRole("button", { name: /深度/ }).first().click();
  await page.getByRole("button", { name: "开始", exact: true }).first().click();

  const dialog = page.getByRole("dialog");
  await expect(dialog).toBeVisible();
  await expect(dialog.getByRole("heading")).toContainText("深度");
  await dialog.getByRole("button", { name: "取消" }).click();
  await expect(page.getByRole("dialog")).toHaveCount(0);

  await page.goto("/#risk");
  await expect(page.locator(".view-mount")).toHaveCSS("opacity", "1");
});
