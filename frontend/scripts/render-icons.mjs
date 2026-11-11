// Renders public/favicon.svg into the PNG icons used by the PWA manifest.
// Usage: npm run icons   (uses the preinstalled Playwright Chromium)
import { readFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';
import { chromium } from 'playwright';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');
const svg = await readFile(join(root, 'public/favicon.svg'), 'utf8');
const targets = [
  { file: 'icons/icon-192.png', size: 192, pad: 0.06, bg: 'transparent' },
  { file: 'icons/icon-512.png', size: 512, pad: 0.06, bg: 'transparent' },
  { file: 'icons/icon-maskable-512.png', size: 512, pad: 0.2, bg: '#0b1220' },
  { file: 'icons/apple-touch-icon.png', size: 180, pad: 0.12, bg: '#0b1220' },
];
const browser = await chromium.launch();
const page = await browser.newPage();
for (const t of targets) {
  const inner = Math.round(t.size * (1 - 2 * t.pad));
  await page.setViewportSize({ width: t.size, height: t.size });
  await page.setContent(
    `<html><body style="margin:0;background:${t.bg};display:grid;place-items:center;width:${t.size}px;height:${t.size}px">` +
      `<div style="width:${inner}px;height:${inner}px">${svg.replace('<svg ', `<svg width="${inner}" height="${inner}" `)}</div></body></html>`,
  );
  await page.screenshot({ path: join(root, 'public', t.file), omitBackground: t.bg === 'transparent' });
  console.log('wrote', t.file);
}
await browser.close();
