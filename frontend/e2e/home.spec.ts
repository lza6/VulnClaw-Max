import { expect, test } from "@playwright/test";

test("home starts a quick recon task and renders the live result", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: /欢迎使用 VulnClaw/ })).toBeVisible();

  const start = page.getByRole("button", { name: "开始", exact: true }).first();
  await expect(start).toBeDisabled();

  await page.locator("textarea").first().fill("example.com");
  await page.getByRole("button", { name: /快速/ }).first().click();
  await expect(start).toBeEnabled();

  const requestPromise = page.waitForRequest(
    (request) => request.url().includes("/api/tasks/run") && request.method() === "POST",
  );
  await start.click();
  const request = await requestPromise;
  expect(request.postDataJSON().command).toBe("recon");

  await expect(page.getByText(/扫描完成|Task finished/).first()).toBeVisible({ timeout: 30_000 });
  await page.screenshot({ path: "e2e-artifacts/home-task.png", fullPage: true });
});
