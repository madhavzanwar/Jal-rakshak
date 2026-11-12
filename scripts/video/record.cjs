// Drives the JalRakshak demo build through scenes 3–10 and records them with Playwright.
// Usage: node record.cjs <work_dir> [base_url]
// Reads  <work_dir>/scenes.json (narration durations from narrate.py)
// Writes <work_dir>/rec/app.webm   (1920x1080, scenes 3–9 in one take)
//        <work_dir>/rec/phone.webm (390x844, scene 10)
//        <work_dir>/rec/timings.json  { app: {3:[start,end],...}, phone: {10:[start,end]} } in seconds of each video
const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

const work = process.argv[2];
const BASE = process.argv[3] || 'http://localhost:4173/Jal-rakshak/';
const scenes = JSON.parse(fs.readFileSync(path.join(work, 'scenes.json'), 'utf8'));
const LEAD = 0.5; // s of picture before the narration starts
const TAIL = 0.8; // s of picture after it ends
const MIN = { 6: 8.0, 9: 8.5 };
const target = Object.fromEntries(scenes.map((s) => [s.n, Math.max(s.dur + LEAD + TAIL, MIN[s.n] ?? 6)]));
// Scene-relative time (s) at which sentence i of scene n starts being spoken (same char-weighting as the subtitles).
const sentAt = (n, i) => {
  const sc = scenes.find((x) => x.n === n);
  const w = sc.narration.split(/(?<=[.!?])\s+/).map((x) => x.length + 12);
  const tot = w.reduce((a, b) => a + b, 0);
  return LEAD + (sc.dur * w.slice(0, i).reduce((a, b) => a + b, 0)) / tot;
};
const recDir = path.join(work, 'rec');
fs.rmSync(recDir, { recursive: true, force: true });
fs.mkdirSync(recDir, { recursive: true });

// Visible cursor + click ripple (headless recordings show no pointer).
const cursorScript = (touch) => `
(() => {
  const install = () => {
    if (document.getElementById('__cur')) return;
    const c = document.createElement('div'); c.id = '__cur';
    c.style.cssText = ${JSON.stringify(
      touch
        ? 'position:fixed;left:0;top:0;width:34px;height:34px;margin:-17px 0 0 -17px;border-radius:50%;background:rgba(56,189,248,.35);border:2px solid rgba(255,255,255,.85);z-index:2147483647;pointer-events:none;transition:opacity .2s;opacity:0'
        : 'position:fixed;left:0;top:0;width:26px;height:26px;z-index:2147483647;pointer-events:none;transform:translate(-3px,-2px);background:no-repeat url("data:image/svg+xml;utf8,<svg xmlns=%27http://www.w3.org/2000/svg%27 width=%2726%27 height=%2726%27 viewBox=%270 0 26 26%27><path d=%27M3 2 L3 21 L8.5 16 L12 24 L15.5 22.5 L12 15 L19.5 15 Z%27 fill=%27white%27 stroke=%27black%27 stroke-width=%271.6%27 stroke-linejoin=%27round%27/></svg>")',
    )};
    document.documentElement.appendChild(c);
    const pos = (e) => { c.style.left = e.clientX + 'px'; c.style.top = e.clientY + 'px'; ${touch ? "c.style.opacity='1';" : ''} };
    addEventListener('mousemove', pos, true);
    addEventListener('mousedown', (e) => {
      pos(e);
      const r = document.createElement('div');
      r.style.cssText = 'position:fixed;left:' + e.clientX + 'px;top:' + e.clientY + 'px;width:16px;height:16px;margin:-8px 0 0 -8px;border-radius:50%;border:3px solid #38bdf8;z-index:2147483646;pointer-events:none;transition:all .45s ease-out;opacity:1';
      document.documentElement.appendChild(r);
      requestAnimationFrame(() => { r.style.width = r.style.height = '56px'; r.style.margin = '-28px 0 0 -28px'; r.style.opacity = '0'; });
      setTimeout(() => r.remove(), 600);
    }, true);
  };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', install); else install();
})();`;

// Map tiles: cached on disk (work/tiles) and retried, so a flaky tile never shows as a grey square.
const tileDir = path.join(work, 'tiles');
fs.mkdirSync(tileDir, { recursive: true });
async function routeTiles(ctx) {
  await ctx.route(/tile\.openstreetmap\.org\/\d+\/\d+\/\d+\.png/, async (route) => {
    const m = route.request().url().match(/(\d+)\/(\d+)\/(\d+)\.png/);
    const file = path.join(tileDir, `${m[1]}_${m[2]}_${m[3]}.png`);
    if (fs.existsSync(file)) return route.fulfill({ status: 200, contentType: 'image/png', body: fs.readFileSync(file) });
    for (let i = 0; i < 4; i++) {
      try {
        const res = await route.fetch({ timeout: 15000 });
        if (res.ok()) {
          const body = await res.body();
          fs.writeFileSync(file, body);
          return route.fulfill({ status: 200, contentType: 'image/png', body });
        }
      } catch { /* retry */ }
      await new Promise((r) => setTimeout(r, 400 * (i + 1)));
    }
    return route.abort();
  });
}

function launchOpts() {
  const px = process.env.HTTPS_PROXY || process.env.https_proxy;
  // Map tiles come from tile.openstreetmap.org; route them through the session proxy when one is set.
  return px ? { proxy: { server: px, bypass: 'localhost,127.0.0.1' } } : {};
}

function driver(page, t0) {
  const now = () => (Date.now() - t0) / 1000;
  let mx = 960, my = 540;
  const sleep = (ms) => page.waitForTimeout(ms);
  // Time-bounded easing: however slow each mouse event is, the move ends after ~ms.
  async function glide(x, y, ms = 700) {
    const sx = mx, sy = my, t = Date.now();
    for (;;) {
      const k = Math.min(1, (Date.now() - t) / ms), e = k < 0.5 ? 2 * k * k : 1 - Math.pow(-2 * k + 2, 2) / 2;
      await page.mouse.move(sx + (x - sx) * e, sy + (y - sy) * e);
      if (k >= 1) break;
      await sleep(25);
    }
    mx = x; my = y;
  }
  async function box(loc) {
    await loc.waitFor({ state: 'visible', timeout: 20000 });
    await loc.scrollIntoViewIfNeeded();
    return loc.boundingBox();
  }
  async function hover(loc, ms = 700, dx = 0.5, dy = 0.5) {
    const b = await box(loc);
    await glide(b.x + b.width * dx, b.y + b.height * dy, ms);
  }
  async function click(loc, ms = 700, dx = 0.5, dy = 0.5) {
    await hover(loc, ms, dx, dy);
    await sleep(140);
    await page.mouse.down();
    await sleep(70);
    await page.mouse.up();
  }
  async function wheel(dy, ms = 900, x, y) {
    if (x !== undefined) await glide(x, y, 400);
    const t = Date.now();
    let done = 0;
    for (;;) {
      const k = Math.min(1, (Date.now() - t) / ms), e = k < 0.5 ? 2 * k * k : 1 - Math.pow(-2 * k + 2, 2) / 2;
      const step = Math.round(dy * e - done);
      if (step) { await page.mouse.wheel(0, step); done += step; }
      if (k >= 1) break;
      await sleep(40);
    }
  }
  return { now, sleep, glide, hover, click, wheel, get pos() { return [mx, my]; } };
}

(async () => {
  const browser = await chromium.launch(launchOpts());
  const timings = { app: {}, phone: {} };

  // ------------------------------------------------------------------ desktop take: scenes 3–9
  const ctx = await browser.newContext({
    viewport: { width: 1920, height: 1080 },
    deviceScaleFactor: 1,
    serviceWorkers: 'block',
    ignoreHTTPSErrors: true,
    acceptDownloads: true,
    recordVideo: { dir: recDir, size: { width: 1920, height: 1080 } },
  });
  await ctx.addInitScript(cursorScript(false));
  await routeTiles(ctx);
  const page = await ctx.newPage();
  const t0 = Date.now();
  const d = driver(page, t0);
  let sceneStart = 0;
  const begin = (n) => { sceneStart = d.now(); timings.app[n] = [sceneStart]; console.log(`scene ${n} start ${sceneStart.toFixed(2)}s (target ${target[n].toFixed(2)}s)`); };
  const finish = async (n) => {
    const left = sceneStart + target[n] - d.now();
    if (left > 0) await d.sleep(left * 1000);
    else console.warn(`  scene ${n} overran by ${(-left).toFixed(2)}s`);
    timings.app[n].push(d.now());
  };
  const until = async (sec) => { const left = sceneStart + sec - d.now(); if (left > 0) await d.sleep(left * 1000); };

  // Pre-roll (trimmed away): visit Guwahati once so its map tiles are cached, then start from the overview.
  await page.goto(BASE + '#/?city=guwahati');
  await page.getByTestId('city-name').waitFor();
  await d.sleep(4000);
  await page.goto(BASE + '#/');
  await page.reload();
  await page.getByTestId('demo-frame').waitFor();
  await page.getByTestId('city-rail').waitFor();
  await d.sleep(3500);

  // Scene 3 — command centre overview, replay playing
  begin(3);
  await d.glide(150, 300, 900);
  await d.hover(page.getByTestId('city-rail').getByRole('button', { name: /Dibrugarh/ }).first(), 900);
  await d.hover(page.getByTestId('city-rail').getByRole('button', { name: /Guwahati/ }).first(), 700);
  await d.click(page.getByTestId('demo-play'), 900);
  await d.glide(900, 500, 1500);
  await until(sentAt(3, 1) + 1.0);
  await d.hover(page.getByTestId('national-panel'), 1000, 0.5, 0.3);
  await until(sentAt(3, 2));
  await d.hover(page.getByTestId('demo-pill').first(), 900);
  await d.sleep(1200);
  await d.hover(page.getByTestId('demo-caption'), 900, 0.3);
  await until(target[3] - 1.2);
  if ((await page.getByTestId('demo-play').getAttribute('aria-label')) === 'Pause replay') await d.click(page.getByTestId('demo-play'), 500);
  await page.getByTestId('demo-frame').fill('5');
  await finish(3);

  // Scene 4 — Guwahati detail: factors first, then the explanation
  begin(4);
  await d.click(page.getByTestId('city-rail').getByRole('button', { name: /Guwahati/ }).first(), 800);
  await page.getByTestId('city-name').waitFor();
  await d.sleep(1500);
  await d.hover(page.getByTestId('risk-score'), 800);
  await until(sentAt(4, 1));
  const cp = page.getByTestId('city-panel');
  await d.hover(cp.getByText(/rain 24 h/i).first(), 700);
  await d.sleep(1200);
  const pb = await cp.boundingBox();
  await d.wheel(640, 1400, pb.x + pb.width / 2, 600); // horizon + rainfall charts
  await d.sleep(2200);
  await d.wheel(380, 1100); // Brahmaputra gauge card
  await d.hover(page.getByTestId('gauge-card'), 700, 0.5, 0.6);
  await until(sentAt(4, 2) - 1.3);
  await d.wheel(-1500, 1200); // back up to the gauge + explanation
  await d.hover(page.getByTestId('risk-explanation'), 800, 0.35);
  await finish(4);

  // Scene 5 — ward drill-down: click the Anil Nagar zone (4th ward circle) on the map
  begin(5);
  const circles = page.locator('.leaflet-overlay-pane path.leaflet-interactive');
  let opened = false;
  try {
    const cb = await circles.nth(3).boundingBox();
    await d.glide(cb.x + cb.width * 0.5, cb.y + cb.height * 0.78, 1000);
    await d.sleep(500);
    await page.mouse.down(); await d.sleep(70); await page.mouse.up();
    await page.getByTestId('ward-panel').waitFor({ timeout: 3000 });
    opened = true;
  } catch { /* fall back to the list */ }
  if (!opened) await d.click(page.getByTestId('ward-row').first());
  await page.getByTestId('ward-panel').waitFor();
  await d.sleep(900);
  const wp = page.getByTestId('ward-panel');
  await d.hover(wp.getByRole('meter').nth(0), 700, 0.6);
  await d.hover(wp.getByRole('meter').nth(3), 900, 0.6);
  await d.sleep(500);
  await d.hover(wp.getByText('Nearest shelters & facilities'), 900, 0.3);
  await finish(5);

  // Scene 6 — drag the replay slider forward: wards and gauge go red
  begin(6);
  const slider = page.getByTestId('demo-frame');
  const sb = await slider.boundingBox();
  const max = Number(await slider.getAttribute('max'));
  const thumb = 16;
  const xOf = (v) => sb.x + thumb / 2 + (v / max) * (sb.width - thumb);
  const cy = sb.y + sb.height / 2;
  await d.glide(xOf(5), cy, 800);
  await d.sleep(200);
  await page.mouse.down();
  await d.glide(xOf(10), cy, 2600);
  await page.mouse.up();
  if ((await slider.inputValue()) !== '10') await slider.fill('10');
  await d.sleep(600);
  await d.hover(page.getByTestId('risk-score'), 1000);
  await finish(6);

  // Scene 7 — run the response agents; steps stream on the Agents page (actions follow the narration)
  begin(7);
  await d.click(page.getByTestId('run-agents'), 900);
  await page.getByTestId('lane-monitor').getByTestId('agent-step').first().waitFor();
  const laneScroll = async (id, ms = 1000) => {
    const b = await page.getByTestId(`lane-${id}`).boundingBox();
    if (b) await d.wheel(b.y - 130, ms, 700, 620);
  };
  const step = (lane, i) => page.getByTestId(`lane-${lane}`).getByTestId('agent-step').nth(i);
  await until(sentAt(7, 1) + 0.8);
  await d.hover(step('monitor', 1), 800, 0.3); // get_city_risk result
  await d.sleep(1500);
  await d.hover(page.getByText('Monitor decision', { exact: false }).first(), 900);
  await until(sentAt(7, 2));
  await laneScroll('alert_drafter');
  await d.hover(step('alert_drafter', 0), 700, 0.3);
  await until(sentAt(7, 3));
  await d.hover(step('alert_drafter', 3), 800, 0.3); // 7/7 alert guards passed
  await until(sentAt(7, 4));
  await laneScroll('evacuation_planner');
  await d.hover(step('evacuation_planner', 0), 700, 0.3);
  await d.sleep(1200);
  await laneScroll('sitrep', 900);
  await page.getByTestId('run-complete').waitFor({ timeout: 60000 });
  await until(sentAt(7, 5));
  await d.wheel(-8000, 1100, 700, 600);
  await d.click(step('monitor', 0).getByText('Tool input'), 700);
  await d.sleep(900);
  await d.hover(page.getByTestId('drafted-alert'), 800, 0.4, 0.35);
  await until(target[7] - 1.5);
  await d.hover(page.getByTestId('review-alert'), 800);
  await finish(7);

  // Scene 8 — human approval in Admin
  begin(8);
  await d.click(page.getByTestId('review-alert'), 500);
  await page.getByTestId('alert-editor').waitFor();
  await until(sentAt(8, 1) - 0.4);
  const tabs = page.getByRole('tablist', { name: 'Alert language' }).getByRole('tab');
  for (const name of ['हिन्दी', 'मराठी', 'தமிழ்', 'বাংলা']) {
    await d.click(tabs.filter({ hasText: name }), 380);
    await d.sleep(380);
  }
  await d.click(page.getByTestId('reviewer-name'), 500);
  await page.getByTestId('reviewer-name').pressSequentially('Duty Officer R. Baruah', { delay: 25 });
  await d.click(page.getByTestId('approve-alert'), 600);
  await page.getByTestId('alert-status').filter({ hasText: /sent/i }).waitFor();
  await d.sleep(300);
  await d.hover(page.getByTestId('alert-status'), 700);
  await until(sentAt(8, 2) + 1.0);
  await d.hover(page.getByTestId('dispatch-log'), 900, 0.3, 0.2);
  await finish(8);

  // Scene 9 — situation report + Export PDF
  begin(9);
  const sitrep = page.getByTestId('sitrep');
  const srb = await sitrep.boundingBox();
  await d.wheel(srb.y - 260, 1500, 1150, 700);
  await d.sleep(400);
  const dl = page.waitForEvent('download', { timeout: 15000 }).catch(() => null);
  await d.click(page.getByTestId('export-pdf'), 900);
  const file = await dl;
  if (file) { await file.saveAs(path.join(recDir, 'sitrep.pdf')).catch(() => {}); console.log('  sitrep pdf downloaded:', file.suggestedFilename()); }
  await d.sleep(600);
  await d.hover(sitrep.locator('h3').first(), 1000, 0.3);
  await d.wheel(260, 1200);
  await finish(9);

  await d.sleep(1500); // tail so the last scene is fully inside the recording
  const appVideo = page.video();
  await ctx.close();
  fs.renameSync(await appVideo.path(), path.join(recDir, 'app.webm'));

  // ------------------------------------------------------------------ phone take: scene 10
  const mctx = await browser.newContext({
    viewport: { width: 390, height: 844 },
    deviceScaleFactor: 1,
    isMobile: true,
    hasTouch: true,
    serviceWorkers: 'block',
    ignoreHTTPSErrors: true,
    recordVideo: { dir: recDir, size: { width: 390, height: 844 } },
  });
  await mctx.addInitScript(cursorScript(true));
  await routeTiles(mctx);
  const m = await mctx.newPage();
  const m0 = Date.now();
  const md = driver(m, m0);
  await m.goto(BASE + '#/');
  await m.getByTestId('demo-frame').waitFor();
  await m.getByTestId('demo-frame').fill('10'); // same replay moment as the desktop take
  await m.evaluate(() => { location.hash = '#/citizen'; });
  await m.getByTestId('citizen-place').waitFor();
  await md.sleep(1500);
  const ms0 = md.now();
  timings.phone[10] = [ms0];
  sceneStart = ms0;
  console.log(`scene 10 start ${ms0.toFixed(2)}s (phone, target ${target[10].toFixed(2)}s)`);
  await md.click(m.getByTestId('citizen-place'), 700);
  await m.getByTestId('citizen-place').pressSequentially('Pandu', { delay: 120 });
  await md.sleep(300);
  await md.click(m.getByTestId('citizen-check'), 500);
  const chooser = m.getByRole('heading', { name: 'Which place did you mean?' });
  await Promise.race([m.getByTestId('citizen-risk-card').waitFor(), chooser.waitFor()]);
  if (await chooser.isVisible()) await md.click(m.locator('section ul button').first(), 500);
  await m.getByTestId('citizen-risk-card').waitFor();
  const scrollTo = async (loc, ms = 1200) => {
    const b = await loc.boundingBox();
    if (!b) return;
    const from = await m.evaluate(() => scrollY);
    const to = Math.max(0, from + b.y - 70);
    const t = Date.now();
    for (;;) {
      const k = Math.min(1, (Date.now() - t) / ms), e = k < 0.5 ? 2 * k * k : 1 - Math.pow(-2 * k + 2, 2) / 2;
      await m.evaluate((y) => scrollTo(0, y), from + (to - from) * e);
      if (k >= 1) break;
      await md.sleep(30);
    }
  };
  const left = () => sceneStart + target[10] - md.now();
  await md.sleep(400);
  await scrollTo(m.getByTestId('citizen-risk-card'));
  // sentence 1 lists: risk, what to do now, nearest shelter, emergency numbers
  const s1 = sentAt(10, 1), s1len = scenes.find((x) => x.n === 10).dur + LEAD - s1;
  const untilM = async (sec) => { const l = sceneStart + sec - md.now(); if (l > 0) await md.sleep(l * 1000); };
  await untilM(s1 + 0.5 * s1len);
  await scrollTo(m.getByTestId('citizen-shelter'));
  await untilM(s1 + 0.78 * s1len);
  await scrollTo(m.getByTestId('emergency-numbers'));
  const rest = left();
  if (rest > 0) await md.sleep(rest * 1000);
  timings.phone[10].push(md.now());
  await md.sleep(1500);
  const phoneVideo = m.video();
  await mctx.close();
  fs.renameSync(await phoneVideo.path(), path.join(recDir, 'phone.webm'));

  await browser.close();
  fs.writeFileSync(path.join(recDir, 'timings.json'), JSON.stringify({ target, ...timings }, null, 2));
  console.log('recorded', JSON.stringify(timings));
})().catch((e) => { console.error(e); process.exit(1); });
