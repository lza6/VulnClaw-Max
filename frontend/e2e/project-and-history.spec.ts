import { execFileSync } from "node:child_process";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { expect, test } from "@playwright/test";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(HERE, "..", "..");
const CONFIG = path.join(ROOT, ".test-tmp", "e2e-config");

test("a project can be attached to a new task", async ({ page, request }) => {
  const created = await request.post("/api/projects", {
    data: { name: "E2E Project", customer: "Acme" },
  });
  expect(created.ok()).toBeTruthy();
  const project = (await created.json()) as { slug: string };

  await page.goto("/");
  await page.locator('select[aria-label="项目"]').selectOption(project.slug);
  await page.locator("textarea").first().fill("example.com");
  await page.getByRole("button", { name: /快速/ }).first().click();

  const requestPromise = page.waitForRequest(
    (req) => req.url().includes("/api/tasks/run") && req.method() === "POST",
  );
  await page.getByRole("button", { name: "开始", exact: true }).first().click();
  const payload = (await requestPromise).postDataJSON() as {
    options: { project?: string };
  };
  expect(payload.options.project).toBe(project.slug);

  await expect(page.getByText(/扫描完成|Task finished/).first()).toBeVisible({ timeout: 30_000 });

  const tasks = (await (await request.get("/api/tasks")).json()) as Array<{
    options: { project?: string };
  }>;
  expect(tasks[0].options.project).toBe(project.slug);
  await page.screenshot({ path: "e2e-artifacts/home-project-task.png", fullPage: true });
});

test("history lists the snapshots of the selected target", async ({ page, request }) => {
  execFileSync("python", [path.join(HERE, "seed.py"), "https://example.com"], {
    cwd: ROOT,
    env: { ...process.env, VULNCLAW_CONFIG_DIR: CONFIG, PYTHONIOENCODING: "utf-8" },
  });

  const snapshots = (await (
    await request.get(`/api/targets/${encodeURIComponent("https://example.com")}/snapshots`)
  ).json()) as Array<{ snapshot_id: string }>;
  expect(snapshots.length).toBeGreaterThan(0);

  await page.goto("/");
  await page.locator('button.nav-item[aria-label="历史"]').click();
  await page.locator(".history-page select").first().selectOption("https://example.com");

  await expect(page.getByText(/\d{8}_\d{6}_\d*\w*_scan/).first()).toBeVisible({ timeout: 15_000 });
  await page.screenshot({ path: "e2e-artifacts/history-snapshots.png", fullPage: true });
});
