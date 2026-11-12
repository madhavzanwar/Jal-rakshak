// Renders the 1920x1080 title cards (scenes 1, 2, 11, 12) and the phone-scene backdrop as PNGs.
// Usage: node cards.cjs <repo_root> <out_dir>
const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');
const [root, out] = process.argv.slice(2);
fs.mkdirSync(out, { recursive: true });

const logo = fs.readFileSync(path.join(root, 'frontend/public/favicon.svg'), 'utf8');
const archPng = path.join(root, 'docs/img/architecture.png');
const arch = fs.existsSync(archPng) ? 'data:image/png;base64,' + fs.readFileSync(archPng).toString('base64') : null;

const css = `
*{box-sizing:border-box;margin:0;padding:0}
html,body{width:1920px;height:1080px;overflow:hidden}
body{font-family:Inter,'Noto Sans',sans-serif;color:#e2e8f0;
  background:radial-gradient(1200px 700px at 85% -10%,rgba(14,165,233,.22),transparent 60%),
             radial-gradient(900px 600px at -10% 110%,rgba(20,184,166,.20),transparent 60%),#070c17;}
.wrap{position:absolute;inset:0;padding:100px 140px 190px;display:flex;flex-direction:column}
.brand{display:flex;align-items:center;gap:22px}
.brand svg{width:84px;height:84px}
.brand .name{font-size:54px;font-weight:700;letter-spacing:-.5px;color:#fff}
.brand .name b{color:#38bdf8;font-weight:700}
.brand .sub{font-size:17px;letter-spacing:5px;color:#94a3b8;margin-top:4px}
.kicker{font-size:22px;letter-spacing:4px;text-transform:uppercase;color:#2dd4bf;font-weight:600}
h1{font-size:88px;line-height:1.05;font-weight:800;letter-spacing:-2px;color:#fff}
h1 .t{color:#38bdf8}
.lead{font-size:34px;line-height:1.45;color:#cbd5e1;max-width:1400px}
.bar{height:6px;width:160px;border-radius:3px;background:linear-gradient(90deg,#0ea5e9,#14b8a6)}
.team{font-size:30px;color:#e2e8f0}
.team span{color:#94a3b8}
.facts{display:grid;grid-template-columns:repeat(3,1fr);gap:28px;margin-top:56px}
.fact{border:1px solid rgba(255,255,255,.08);background:rgba(15,23,42,.7);border-radius:20px;padding:34px 34px 38px}
.fact .n{font-size:58px;font-weight:800;color:#fff}
.fact .n.r{color:#f87171}.fact .n.o{color:#fb923c}.fact .n.s{color:#38bdf8}
.fact p{font-size:26px;line-height:1.4;color:#cbd5e1;margin-top:12px}
.url{font-family:'JetBrains Mono',ui-monospace,monospace;font-size:34px;color:#7dd3fc}
.row{display:flex;align-items:center;gap:22px;margin-top:22px}
.lbl{font-size:20px;letter-spacing:3px;text-transform:uppercase;color:#64748b;width:200px}
.pill{display:inline-block;border:1px solid rgba(232,121,249,.4);background:rgba(217,70,239,.12);color:#f5d0fe;border-radius:999px;padding:8px 20px;font-size:20px}
.arch{margin-top:24px;flex:1;min-height:0;display:flex;align-items:center;justify-content:center}
.arch img{height:100%;width:auto;max-width:100%;border-radius:20px;background:#f5f8fb;box-shadow:0 30px 80px rgba(0,0,0,.45)}
.stack{display:flex;flex-wrap:wrap;gap:16px;margin-top:40px}
.stack div{font-size:30px;border:1px solid rgba(255,255,255,.1);border-radius:14px;padding:16px 26px;background:rgba(15,23,42,.7)}
`;
const brand = `<div class="brand">${logo}<div><div class="name"><b>Jal</b>Rakshak</div><div class="sub">FLOOD EARLY WARNING · INDIA</div></div></div>`;
const team = `<div class="team">Madhav Zanwar · Divyani Papalkar <span>· PCCoE Pune</span></div>`;

const cards = {
  card01: `<div class="wrap">${brand}
    <div style="margin-top:auto">
      <div class="kicker">Agentic flood early warning for India</div>
      <h1 style="margin-top:26px">Warnings people<br/>can <span class="t">act on</span>.</h1>
      <p class="lead" style="margin-top:34px">Open forecasts → ward-level risk → AI agents draft multilingual alerts → a human approves.</p>
      <div class="bar" style="margin:48px 0 30px"></div>${team}
    </div></div>`,
  card02: `<div class="wrap">${brand}
    <div style="margin-top:auto">
      <div class="kicker">The problem</div>
      <h1 style="margin-top:22px">Warnings exist.<br/><span class="t">Last-mile action doesn't.</span></h1>
      <div class="facts">
        <div class="fact"><div class="n s">Forecasts</div><p>Rainfall and river forecasts already exist — but as charts and bulletins, not local instructions.</p></div>
        <div class="fact"><div class="n o">Overload</div><p>District officers must turn data into alerts by hand, in several languages, under time pressure.</p></div>
        <div class="fact"><div class="n r">Too late</div><p>Citizens get generic warnings with no clear "what do I do now, and where do I go?"</p></div>
      </div>
    </div></div>`,
  card11: `<div class="wrap" style="padding:44px 150px 150px">
    <div style="display:flex;align-items:flex-end;justify-content:space-between">
      <div><div class="kicker">How it's built</div><h1 style="font-size:54px;margin-top:10px">One command · no paid services · <span class="t">open source</span></h1></div>
    </div>
    ${arch ? `<div class="arch"><img src="${arch}"/></div>` :
      `<div class="stack">${['Open-Meteo','GloFAS','OpenStreetMap','Leaflet','OSRM','Ollama · Qwen2.5','FastAPI','React PWA','LightGBM'].map((s) => `<div>${s}</div>`).join('')}</div>`}
    </div>`,
  card12: `<div class="wrap">${brand}
    <div style="margin-top:auto">
      <h1>JalRakshak — warnings<br/>people can <span class="t">act on</span>.</h1>
      <div class="bar" style="margin:46px 0 34px"></div>
      <div class="row"><div class="lbl">Code</div><div class="url">github.com/madhavzanwar/Jal-rakshak</div></div>
      <div class="row"><div class="lbl">Live demo</div><div class="url">madhavzanwar.github.io/Jal-rakshak</div></div>
      <div class="row" style="margin-top:46px"><div class="lbl">Team</div>${team}</div>
      <div class="row" style="margin-top:34px"><div class="lbl"></div><span class="pill">Demo uses a synthetic replay inspired by Assam monsoon floods · not an official warning</span></div>
    </div></div>`,
  phone_bg: `<div class="wrap" style="padding:0">
    <div style="position:absolute;left:140px;top:300px;width:560px">
      <div class="kicker">Citizen view</div>
      <h1 style="font-size:64px;margin-top:18px">Flood risk<br/>near <span class="t">you</span></h1>
      <p class="lead" style="font-size:28px;margin-top:26px">Light page for low-end phones · works offline · English & Hindi</p>
    </div>
    <div style="position:absolute;right:140px;top:300px;width:520px;text-align:right">
      <div class="kicker" style="color:#38bdf8">No app install</div>
      <p class="lead" style="font-size:28px;margin-top:26px">Your risk · what to do now · nearest shelter · emergency numbers like 112</p>
    </div></div>`,
};

(async () => {
  const b = await chromium.launch();
  const p = await b.newPage({ viewport: { width: 1920, height: 1080 } });
  for (const [name, body] of Object.entries(cards)) {
    await p.setContent(`<!doctype html><html><head><meta charset="utf-8"><style>${css}</style></head><body>${body}</body></html>`);
    await p.evaluate(() => document.fonts.ready);
    await p.waitForTimeout(200);
    await p.screenshot({ path: path.join(out, `${name}.png`) });
    console.log('card', name);
  }
  await b.close();
})();
