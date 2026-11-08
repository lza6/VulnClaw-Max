import { expect, test } from "@playwright/test";

test("MCP server can be disabled and re-enabled from the settings page", async ({ page, request }) => {
  await page.goto("/#settings");
  await page.locator('button.nav-item[aria-label="设置"]').click();

  const diagnosticsSection = page.getByText("诊断", { exact: true }).first();
  await diagnosticsSection.click();

  const firstToggle = page.locator("[data-testid^='mcp-toggle-']").first();
  await expect(firstToggle).toBeVisible();

  // Track the specific server this row controls so other servers never skew the assertion.
  const serverName = (await firstToggle.getAttribute("data-testid"))?.replace("mcp-toggle-", "") ?? "";
  expect(serverName).not.toBe("");

  const stateOf = async (): Promise<boolean | null> => {
    const response = await request.get("/api/mcp");
    const data = (await response.json()) as { services: Array<{ name: string; enabled: boolean }> };
    return data.services.find((s) => s.name === serverName)?.enabled ?? null;
  };

  const initialEnabled = await stateOf();
  expect(initialEnabled).not.toBeNull();

  await firstToggle.click();
  await expect.poll(stateOf).toBe(!initialEnabled);

  await expect(firstToggle).toBeEnabled({ timeout: 10_000 });
  await firstToggle.click();
  await expect.poll(stateOf).toBe(initialEnabled);
});

test("boundary page exposes audit export downloads", async ({ page, request }) => {
  await page.goto("/");
  await page.locator('button.nav-item[aria-label="范围"]').click();

  const jsonlLink = page.getByTestId("audit-export-jsonl");
  const csvLink = page.getByTestId("audit-export-csv");
  await expect(jsonlLink).toBeVisible();
  await expect(csvLink).toBeVisible();

  const response = await request.get("/api/audit/export?format=csv");
  expect(response.status()).toBe(200);
  const body = await response.text();
  // CSV export starts with a header row; JSONL export has one JSON object per line.
  expect(body.length).toBeGreaterThan(0);
});
