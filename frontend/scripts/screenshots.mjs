// Captures documentation screenshots of the demo build into ../docs/img/screens/.
// Usage: npm run build:demo && npx vite preview --port 4173 --base /Jal-rakshak/ &
//        SHOTS_URL=http://localhost:4173/Jal-rakshak/ npm run screens
import { mkdir } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';
import { chromium } from 'playwright';

const root = join(dirname(fileURLToPath(import.meta.url)), '..', '..');
const out = join(root, 'docs', 'img', 'screens');
const url = process.env.SHOTS_URL ?? 'http://localhost:4173/Jal-rakshak/';
const city = process.env.SHOTS_CITY ?? 'guwahati';
await mkdir(out, { recursive: true });

const browser = await chromium.launch();
const ctx = await browser.newContext({ viewport: { width: 1920, height: 1080 }, deviceScaleFactor: 1, serviceWorkers: 'block' });
const page = await ctx.newPage();
const settle = (ms = 1800) => page.waitForTimeout(ms);
const shot = async (name) => {
  await page.evaluate(() => document.activeElement instanceof HTMLElement && document.activeElement.blur());
  await page.screenshot({ path: join(out, name) });
  console.log('wrote', name);
};

// Pick an evocative frame: the one where the city's agent run was recorded (else 2/3 through).
await page.goto(`${url}#/`);
await page.getByTestId('demo-frame').waitFor();
const frame = Number(process.env.SHOTS_FRAME ?? (await page.getByTestId('demo-frame').getAttribute('max'))) * (process.env.SHOTS_FRAME ? 1 : 0.7);
await page.getByTestId('demo-frame').fill(String(Math.round(frame)));
await settle(2500);
await shot('dashboard.png');

await page.getByTestId('city-select').selectOption(city);
await page.getByTestId('city-name').waitFor();
await settle(2500);
await shot('dashboard-guwahati.png');

await page.getByTestId('ward-row').first().click();
await page.getByTestId('ward-panel').waitFor();
await settle(2000);
await shot('ward-drilldown.png');

await page.getByTestId('run-agents').click();
await page.getByTestId('drafted-alert').waitFor({ timeout: 90_000 });
await page.getByRole('button', { name: 'Show all' }).click().catch(() => {});
await page.getByTestId('run-complete').waitFor();
await settle(2000);
await shot('agents.png');

await page.getByTestId('review-alert').click();
await page.getByTestId('alert-editor').waitFor();
await page.getByRole('tab', { name: 'हिन्दी' }).click();
await page.getByTestId('reviewer-name').fill('Duty Officer R. Baruah');
await settle(800);
await shot('admin.png');
await page.getByTestId('approve-alert').click();
await page.getByTestId('dispatch-log').waitFor();
await settle(600);
await shot('admin-sent.png');

const mobile = await browser.newContext({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 1, isMobile: true, hasTouch: true, serviceWorkers: 'block' });
const m = await mobile.newPage();
await m.goto(`${url}#/citizen`);
const q = process.env.SHOTS_PLACE ?? 'anil nagar';
await m.getByTestId('citizen-place').fill(q);
await m.getByTestId('citizen-check').click();
const pick = m.getByText('Which place did you mean?');
await Promise.race([m.getByTestId('citizen-risk-card').waitFor(), pick.waitFor()]);
if (await pick.isVisible()) await m.locator('section ul button').first().click();
await m.getByTestId('citizen-risk-card').waitFor();
await m.waitForTimeout(800);
await m.screenshot({ path: join(out, 'citizen-mobile.png') });
console.log('wrote citizen-mobile.png');

await browser.close();
