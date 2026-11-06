import { expect, test } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

const VIEWS = ["home", "risk", "reports", "boundary", "history", "plugins", "settings", "advanced"] as const;
const STORAGE_KEY = "vulnclaw.ui.preferences";

/**
 * 只拦 serious / critical：moderate 里有大量"色彩对比"以外的风格建议，
 * 会把视觉改版变成一场无休止的值调整。
 */
/** 等入场动画落地：动画中间态的不透明度会让 axe 算出假的对比度。 */
async function waitForSettled(page: import("@playwright/test").Page) {
  await page.waitForFunction(() => {
    const nodes = [document.querySelector(".view-mount"), document.querySelector(".goby-task-panel")].filter(Boolean);
    return nodes.every((node) => Number(getComputedStyle(node as Element).opacity) > 0.99);
  });
}

async function expectNoSeriousViolations(page: import("@playwright/test").Page, label: string) {
  const results = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa"]).analyze();
  const blocking = results.violations.filter((violation) => violation.impact === "serious" || violation.impact === "critical");
  expect(
    blocking.flatMap((violation) =>
      violation.nodes.map((node) => `${label}: ${violation.id} → ${node.target.join(" ")} | ${node.any[0]?.message ?? ""}`),
    ),
  ).toEqual([]);
}

for (const theme of ["light", "dark"] as const) {
  test(`no serious accessibility violations in ${theme} theme`, async ({ page }) => {
    await page.addInitScript(
      ({ key, value }) => {
        window.localStorage.setItem(key, JSON.stringify(value));
      },
      {
        key: STORAGE_KEY,
        value: {
          language: "zh-CN",
          defaultCheckMode: "standard",
          reportFormat: "markdown",
          reportTemplate: "pentest",
          showTechnicalLogs: false,
          theme,
          defaultBoundary: { onlyPort: "", onlyHost: "", onlyPath: "", blockedHost: "", blockedPath: "", allowActions: [], blockActions: [] },
        },
      },
    );

    for (const view of VIEWS) {
      await page.goto(`/#${view}`);
      await expect(page.locator("html")).toHaveAttribute("data-theme", theme);
      await waitForSettled(page);
      await expectNoSeriousViolations(page, `${theme}/${view}`);
    }
  });
}
