import { expect, test } from "@playwright/test";

test("history opens a run detail with timeline and artifacts", async ({ page, request }) => {
  const created = await request.post("/api/tasks/run", {
    data: { command: "recon", target: "example.com", options: {} },
  });
  expect(created.ok()).toBeTruthy();
  const taskId = (await created.json()).task_id as string;

  await expect
    .poll(
      async () => {
        const response = await request.get("/api/tasks");
        const tasks = (await response.json()) as Array<{ task_id: string; status: string }>;
        return tasks.find((task) => task.task_id === taskId)?.status;
      },
      { timeout: 30_000 },
    )
    .toMatch(/completed|failed/);

  await page.goto("/");
  await page.locator('button.nav-item[aria-label="历史"]').click();
  await expect(page.getByRole("heading", { name: "运行记录" })).toBeVisible({ timeout: 15_000 });

  await page.getByRole("button", { name: "查看运行详情" }).last().click();
  const dialog = page.getByRole("dialog");
  await expect(dialog).toBeVisible();
  await expect(dialog.getByText("事件时间线")).toBeVisible();
  await expect(dialog.getByText("运行产物")).toBeVisible();
  await page.screenshot({ path: "e2e-artifacts/run-detail.png", fullPage: true });
  await dialog.getByRole("button", { name: "关闭" }).click();
  await expect(dialog).toBeHidden();
});
