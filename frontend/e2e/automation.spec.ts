import { execFileSync } from "node:child_process";
import { mkdirSync, writeFileSync } from "node:fs";
import http from "node:http";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { expect, test } from "@playwright/test";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(HERE, "..", "..");
const CONFIG = path.join(ROOT, ".test-tmp", "e2e-config");

async function startHookServer(): Promise<{ url: string; bodies: Record<string, unknown>[]; close: () => Promise<void> }> {
  const bodies: Record<string, unknown>[] = [];
  const server = http.createServer((req, res) => {
    const chunks: Buffer[] = [];
    req.on("data", (chunk: Buffer) => chunks.push(chunk));
    req.on("end", () => {
      try {
        bodies.push(JSON.parse(Buffer.concat(chunks).toString("utf-8")) as Record<string, unknown>);
      } catch {
        bodies.push({ unparsed: true });
      }
      res.writeHead(200, { "Content-Type": "application/json" });
      res.end(JSON.stringify({ ok: true }));
    });
  });
  await new Promise<void>((resolve) => server.listen(0, "127.0.0.1", resolve));
  const address = server.address();
  if (address === null || typeof address === "string") throw new Error("hook server failed to bind");
  return {
    url: `http://127.0.0.1:${address.port}/hook`,
    bodies,
    close: () => new Promise<void>((resolve) => server.close(() => resolve())),
  };
}

test("settings integration panel saves, tests and deletes a notification webhook", async ({ page }) => {
  const hook = await startHookServer();
  try {
    await page.goto("/");
    await page.locator('button.nav-item[aria-label="设置"]').click();
    await page.locator(".settings-nav-item", { hasText: "集成" }).click();

    await expect(page.getByRole("button", { name: "添加集成" })).toBeVisible();
    await page.getByRole("button", { name: "添加集成" }).click();

    await page.getByPlaceholder("slack-alerts").fill("e2e-hook");
    await page.getByPlaceholder("https://hooks.example.com/vulnclaw").fill(hook.url);
    await page.getByRole("button", { name: "保存集成" }).click();

    await expect(page.locator(".success-box")).toContainText("已保存集成 e2e-hook", { timeout: 15_000 });
    const row = page.locator(".integration-item", { hasText: "e2e-hook" });
    await expect(row).toBeVisible();

    await row.getByRole("button", { name: "测试" }).click();
    await expect(page.locator(".success-box")).toContainText("测试成功", { timeout: 15_000 });
    await expect.poll(() => hook.bodies.length, { timeout: 15_000 }).toBeGreaterThan(0);
    expect(hook.bodies[0]).toMatchObject({
      event: "run.completed",
      source: "vulnclaw",
      test: true,
    });

    await page.screenshot({ path: "e2e-artifacts/settings-integrations.png", fullPage: true });

    await row.getByRole("button", { name: "删除" }).click();
    const dialog = page.getByRole("dialog");
    await expect(dialog).toBeVisible();
    await dialog.getByRole("button", { name: "删除" }).click();
    await expect(page.locator(".success-box")).toContainText("已删除集成 e2e-hook", { timeout: 15_000 });
    await expect(page.locator(".integration-item", { hasText: "e2e-hook" })).toHaveCount(0);
    await expect(page.getByText("还没有配置任何集成")).toBeVisible();
  } finally {
    await hook.close();
  }
});

test("a finished task notifies the subscribed webhook", async ({ request }) => {
  const hook = await startHookServer();
  try {
    const created = await request.post("/api/integrations", {
      data: { name: "e2e-run-hook", kind: "webhook", url: hook.url },
    });
    expect(created.ok()).toBeTruthy();

    const scanTarget = path.join(ROOT, ".test-tmp", "codescan-target");
    mkdirSync(scanTarget, { recursive: true });
    writeFileSync(
      path.join(scanTarget, "app.py"),
      ["import subprocess", "", "", "def run(cmd):", "    return subprocess.run(cmd, shell=True)", ""].join("\n"),
      "utf-8",
    );

    const response = await request.post("/api/tasks/run", {
      data: { command: "codescan", target: scanTarget, resume: false },
    });
    expect(response.ok()).toBeTruthy();
    const task = (await response.json()) as { task_id: string };

    await expect
      .poll(
        () => hook.bodies.filter((body) => body.task_id === task.task_id).length,
        { timeout: 60_000 },
      )
      .toBeGreaterThan(0);
    const body = hook.bodies.find((item) => item.task_id === task.task_id)!;
    expect(body.event).toBe("run.completed");
    expect(body.command).toBe("codescan");
    expect(body.target).toBe(scanTarget);
    expect(body.source).toBe("vulnclaw");
  } finally {
    await request.delete("/api/integrations/e2e-run-hook");
    await hook.close();
  }
});

test("report center generates an executive template report", async ({ page, request }) => {
  execFileSync("python", [path.join(HERE, "seed.py"), "https://example.com"], {
    cwd: ROOT,
    env: { ...process.env, VULNCLAW_CONFIG_DIR: CONFIG, PYTHONIOENCODING: "utf-8" },
  });

  await page.goto("/");
  await page.locator('button.nav-item[aria-label="报告"]').click();

  await page.locator(".report-template-field select").selectOption("executive");
  await page.locator('input[list="report-targets"]').fill("https://example.com");
  await page.getByRole("button", { name: "生成", exact: true }).first().click();

  type ReportItem = { name: string; path: string; kind: string };
  let executive: ReportItem | undefined;
  await expect
    .poll(
      async () => {
        const reports = (await (await request.get("/api/reports")).json()) as ReportItem[];
        executive = reports.find(
          (item) => item.kind === "markdown" && item.name.includes("_executive_"),
        );
        return Boolean(executive);
      },
      { timeout: 30_000 },
    )
    .toBe(true);

  const content = await (
    await request.get(`/api/reports/content?path=${encodeURIComponent(executive!.path)}`)
  ).json();
  expect(content.content).toContain("Executive Summary");
  expect(content.content).not.toContain("Verified Findings — Location & Reproduction");
  expect(content.content).not.toContain("Target Historical Governance Context");

  await page.reload();
  await page.locator('button.nav-item[aria-label="报告"]').click();
  await expect(page.getByText(/_executive_/).first()).toBeVisible({ timeout: 30_000 });
  await page.screenshot({ path: "e2e-artifacts/report-executive.png", fullPage: true });
});

test("plugins page lists the builtin detection plugins", async ({ page, request }) => {
  const inventory = (await (await request.get("/api/plugins")).json()) as {
    plugins: Array<{ plugin_id: string; origin: string }>;
    errors: unknown[];
  };
  expect(inventory.errors).toEqual([]);
  const ids = inventory.plugins.map((plugin) => plugin.plugin_id);
  expect(ids).toEqual(
    expect.arrayContaining(["builtin.web.headers", "builtin.web.jwt", "builtin.web.js_endpoints"]),
  );

  await page.goto("/");
  await page.locator('button.nav-item[aria-label="插件"]').click();

  await expect(page.getByText("builtin.web.headers")).toBeVisible({ timeout: 15_000 });
  await expect(page.locator(".plugin-card")).toHaveCount(inventory.plugins.length);

  await page.locator(".plugin-filter-grid select").first().selectOption("verification");
  await expect(page.getByText("builtin.web.headers")).toBeVisible();
  await expect(page.getByText("builtin.web.js_endpoints")).toHaveCount(0);

  await page.locator(".plugin-filter-grid select").first().selectOption("all");
  await page.locator(".plugin-filter-grid input").fill("no-such-plugin");
  await expect(page.getByText("没有匹配的插件")).toBeVisible();

  await page.locator(".plugin-filter-grid input").fill("");
  await page.screenshot({ path: "e2e-artifacts/plugins.png", fullPage: true });
});

test("a finished task lands in the delivery history and can be retried", async ({ page, request }) => {
  const hook = await startHookServer();
  try {
    await request.post("/api/integrations", {
      data: { name: "e2e-history-hook", kind: "webhook", url: hook.url },
    });
    const created = await request.post("/api/tasks/run", {
      data: { command: "codescan", target: path.join(ROOT, ".test-tmp", "codescan-target"), resume: false },
    });
    expect(created.ok()).toBeTruthy();
    const task = (await created.json()) as { task_id: string };
    await expect
      .poll(() => hook.bodies.filter((body) => body.task_id === task.task_id).length, { timeout: 60_000 })
      .toBeGreaterThan(0);

    await page.goto("/");
    await page.locator('button.nav-item[aria-label="设置"]').click();
    await page.locator(".settings-nav-item", { hasText: "集成" }).click();

    const row = page.locator(".integration-item", { hasText: "e2e-history-hook" });
    await expect(row).toContainText("投递成功", { timeout: 15_000 });
    await expect(page.locator(".delivery-history-item").first()).toContainText("投递成功");

    const history = (await (await request.get("/api/integrations/deliveries")).json()) as Array<{
      name: string;
      ok: boolean;
      event: string;
    }>;
    expect(history[0]).toMatchObject({ name: "e2e-history-hook", ok: true, event: "run.completed" });
    await page.screenshot({ path: "e2e-artifacts/settings-delivery-history.png", fullPage: true });
  } finally {
    await request.delete("/api/integrations/e2e-history-hook");
    await hook.close();
  }
});

test("scheduled jobs can be created, paused and deleted from settings", async ({ page, request }) => {
  await page.goto("/");
  await page.locator('button.nav-item[aria-label="设置"]').click();
  await page.locator(".settings-nav-item", { hasText: "自动化" }).click();

  await page.getByRole("button", { name: "添加定时任务" }).click();
  await page.getByPlaceholder("nightly-recon").fill("e2e-nightly");
  await page.getByPlaceholder("example.com").fill("example.com");
  await page.locator(".integration-form input[type=number]").fill("30");
  await page.getByRole("button", { name: "保存定时任务" }).click();

  await expect(page.locator(".success-box")).toContainText("已保存定时任务 e2e-nightly", { timeout: 15_000 });
  const row = page.locator(".schedule-item", { hasText: "e2e-nightly" });
  await expect(row).toContainText("每 30 分钟");
  await expect(row).toContainText("已启用");

  const stored = (await (await request.get("/api/schedules")).json()) as Array<{
    name: string;
    interval_seconds: number;
    enabled: boolean;
  }>;
  const job = stored.find((item) => item.name === "e2e-nightly")!;
  expect(job.interval_seconds).toBe(1800);
  expect(job.enabled).toBe(true);

  await page.screenshot({ path: "e2e-artifacts/settings-schedules.png", fullPage: true });

  await row.getByRole("button", { name: "停用" }).click();
  await expect(row).toContainText("已停用", { timeout: 15_000 });

  await page.getByRole("button", { name: "立即执行到期任务" }).click();
  await expect(page.locator(".success-box")).toContainText("当前没有到期任务", { timeout: 15_000 });

  await row.getByRole("button", { name: "删除" }).click();
  const dialog = page.getByRole("dialog");
  await dialog.getByRole("button", { name: "删除" }).click();
  await expect(page.locator(".success-box")).toContainText("已删除定时任务 e2e-nightly", { timeout: 15_000 });
  await expect(page.locator(".schedule-item", { hasText: "e2e-nightly" })).toHaveCount(0);
});
