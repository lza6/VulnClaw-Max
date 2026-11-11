import { expect, test } from "@playwright/test";

test("dialog traps Tab and returns focus on Escape", async ({ page }) => {
  await page.goto("/");
  await page.locator("textarea").first().fill("example.com");
  await page.getByRole("button", { name: /深度/ }).first().click();
  const start = page.getByRole("button", { name: "开始", exact: true }).first();
  await start.click();

  const dialog = page.getByRole("dialog");
  await expect(dialog).toBeVisible();
  for (let index = 0; index < 6; index += 1) {
    await page.keyboard.press("Tab");
    const inDialog = await dialog.evaluate((node) => node.contains(document.activeElement));
    expect(inDialog).toBeTruthy();
  }
  await page.keyboard.press("Escape");
  await expect(dialog).toBeHidden();
  await expect(start).toBeFocused();
});
