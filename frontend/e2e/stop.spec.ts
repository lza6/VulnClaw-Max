import { expect, test } from "@playwright/test";

test("completed task stop returns 409 and the terminal stream does not reconnect", async ({
  page,
  request,
}) => {
  await page.goto("/");
  await page.locator("textarea").first().fill("example.com");
  await page.getByRole("button", { name: /快速/ }).first().click();
  await page.getByRole("button", { name: "开始", exact: true }).first().click();
  await expect(page.getByText(/扫描完成|Task finished/).first()).toBeVisible({ timeout: 30_000 });

  const tasks = (await (await request.get("/api/tasks")).json()) as Array<{
    task_id: string;
    status: string;
  }>;
  const completed = tasks.find((task) => task.status === "completed");
  expect(completed).toBeTruthy();

  const stop = await request.post(`/api/tasks/${completed!.task_id}/stop`);
  expect(stop.status()).toBe(409);

  const reconnectRequests: string[] = [];
  page.on("request", (request) => {
    if (request.url().includes(`/api/tasks/${completed!.task_id}/stream`)) {
      reconnectRequests.push(request.url());
    }
  });
  await page.waitForTimeout(4_000);
  expect(reconnectRequests).toEqual([]);
});
