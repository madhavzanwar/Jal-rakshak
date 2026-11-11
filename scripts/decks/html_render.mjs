// Render HTML/SVG to PNG or PDF with Playwright's preinstalled Chromium.
// Usage: node html_render.mjs jobs.json
// jobs.json: [{"type":"png","src":"a.html","out":"a.png","width":1600,"height":900,"scale":2,"transparent":false},
//             {"type":"pdf","src":"b.html","out":"b.pdf"}]
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import { pathToFileURL } from "node:url";
import { resolve } from "node:path";

const require = createRequire(import.meta.url);
const { chromium } = require("playwright");

const jobs = JSON.parse(readFileSync(process.argv[2], "utf8"));
const browser = await chromium.launch();
try {
  for (const job of jobs) {
    const scale = job.scale ?? 1;
    const ctx = await browser.newContext({
      viewport: { width: job.width ?? 1200, height: job.height ?? 800 },
      deviceScaleFactor: scale,
    });
    const page = await ctx.newPage();
    await page.goto(pathToFileURL(resolve(job.src)).href, { waitUntil: "networkidle" });
    await page.evaluate(() => document.fonts.ready);
    if (job.type === "png") {
      await page.screenshot({ path: job.out, omitBackground: !!job.transparent, fullPage: false });
    } else if (job.type === "pdf") {
      await page.pdf({ path: job.out, format: "A4", printBackground: true, preferCSSPageSize: true });
    }
    await ctx.close();
  }
} finally {
  await browser.close();
}
