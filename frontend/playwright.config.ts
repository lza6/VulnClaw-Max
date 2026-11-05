import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  timeout: 60_000,
  fullyParallel: false,
  workers: 1,
  reporter: [["list"]],
  use: {
    baseURL: "http://127.0.0.1:8877",
    channel: "chrome",
    headless: true,
    locale: "zh-CN",
    viewport: { width: 1440, height: 1000 },
    screenshot: "only-on-failure",
    trace: "retain-on-failure",
  },
  webServer: [
    {
      command: "node e2e/mock-llm.mjs",
      url: "http://127.0.0.1:19090/health",
      reuseExistingServer: false,
      timeout: 30_000,
    },
    {
      command: "node e2e/start-vulnclaw.mjs",
      url: "http://127.0.0.1:8877/api/health",
      reuseExistingServer: false,
      timeout: 120_000,
    },
  ],
});
