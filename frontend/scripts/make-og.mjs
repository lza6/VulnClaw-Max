import { chromium } from "@playwright/test";

/**
 * 用真实浏览器把产品页截成 1200×630 的社交卡。
 * 用法：node scripts/make-og.mjs <页面地址> <输出路径>
 */
const url = process.argv[2] ?? "http://127.0.0.1:8899/index.html";
const out = process.argv[3] ?? "../site/assets/og.png";

const browser = await chromium.launch({ channel: "chrome" });
const page = await browser.newPage({ viewport: { width: 1200, height: 630 }, deviceScaleFactor: 1 });
await page.goto(url, { waitUntil: "networkidle" });
await page.screenshot({ path: out });
await browser.close();
console.log(`og image written: ${out}`);
