"""Asset preparation: icons, backgrounds, screenshots (with placeholders), model metrics."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
CACHE = HERE / ".cache"
ICON_SRC = HERE / "icons"
SCREENS = ROOT / "docs" / "img" / "screens"
ARCH_PNG = ROOT / "docs" / "img" / "architecture.png"
BACKTEST = ROOT / "backend" / "models" / "backtest.json"

ICON_COLORS = {"white": "#FFFFFF", "navy": "#0B1F3A", "teal": "#0E7C86", "amber": "#C96A12"}
ICON_PX = 160

SCREEN_NAMES = ["dashboard", "dashboard-guwahati", "ward-drilldown", "agents", "admin", "citizen-mobile"]
SCREEN_LABELS = {
    "dashboard": "Command-centre dashboard",
    "dashboard-guwahati": "Guwahati city view",
    "ward-drilldown": "Ward drill-down",
    "agents": "Agent timeline",
    "admin": "Admin approval (5 languages)",
    "citizen-mobile": "Citizen view (mobile)",
}


def _font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    name = "Inter-Bold.otf" if bold else "Inter-Regular.otf"
    for base in ("/usr/share/fonts/opentype/inter", "/usr/share/fonts/truetype/inter"):
        p = Path(base) / name
        if p.exists():
            return ImageFont.truetype(str(p), size)
    return ImageFont.load_default()


def render_icons() -> dict[str, Path]:
    """Rasterise every vendored Lucide SVG in each colour (one Playwright screenshot, then crop)."""
    out_dir = CACHE / "icons"
    out_dir.mkdir(parents=True, exist_ok=True)
    names = sorted(p.stem for p in ICON_SRC.glob("*.svg"))
    stamp = out_dir / ".stamp"
    key = ",".join(names) + "|" + ",".join(ICON_COLORS)
    if stamp.exists() and stamp.read_text() == key:
        return {f"{n}:{c}": out_dir / f"{n}-{c}.png" for n in names for c in ICON_COLORS}
    cols = len(names)
    rows = len(ICON_COLORS)
    cells = []
    for r, (cname, hexc) in enumerate(ICON_COLORS.items()):
        for c, n in enumerate(names):
            svg = (ICON_SRC / f"{n}.svg").read_text().replace("<svg ", f'<svg width="{ICON_PX}" height="{ICON_PX}" ', 1)
            cells.append(f'<div style="position:absolute;left:{c*ICON_PX}px;top:{r*ICON_PX}px;'
                         f'width:{ICON_PX}px;height:{ICON_PX}px;color:{hexc}">{svg}</div>')
    html = CACHE / "icons.html"
    html.write_text('<!doctype html><html><head><meta charset="utf-8"><style>html,body{margin:0;background:transparent}'
                    '</style></head><body>' + "".join(cells) + "</body></html>")
    sheet = CACHE / "icons_sheet.png"
    jobs = CACHE / "icon_jobs.json"
    jobs.write_text(json.dumps([{"type": "png", "src": str(html), "out": str(sheet), "width": cols * ICON_PX,
                                 "height": rows * ICON_PX, "scale": 1, "transparent": True}]))
    subprocess.run(["node", str(HERE / "html_render.mjs"), str(jobs)], check=True)
    img = Image.open(sheet).convert("RGBA")
    result = {}
    for r, cname in enumerate(ICON_COLORS):
        for c, n in enumerate(names):
            p = out_dir / f"{n}-{cname}.png"
            img.crop((c * ICON_PX, r * ICON_PX, (c + 1) * ICON_PX, (r + 1) * ICON_PX)).save(p)
            result[f"{n}:{cname}"] = p
    stamp.write_text(key)
    return result


def wave_background(kind: str = "dark") -> Path:
    """Full-bleed 16:9 background: deep navy gradient with translucent teal waves at the bottom."""
    import math

    p = CACHE / f"bg-{kind}.png"
    if p.exists():
        return p
    CACHE.mkdir(exist_ok=True)
    w, h = 2400, 1350
    top, bot = (11, 31, 58), (9, 52, 78)
    img = Image.new("RGBA", (w, h))
    px = ImageDraw.Draw(img)
    for y in range(h):
        t = y / h
        px.line([(0, y), (w, y)], fill=tuple(int(top[i] + (bot[i] - top[i]) * t) for i in range(3)) + (255,))
    for amp, base, period, phase, alpha in [(38, 1080, 900, 0.0, 34), (46, 1150, 1200, 1.3, 46), (30, 1235, 700, 2.4, 64)]:
        layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        d = ImageDraw.Draw(layer)
        pts = [(x, base + amp * math.sin(2 * math.pi * x / period + phase)) for x in range(0, w + 10, 10)]
        d.polygon(pts + [(w, h), (0, h)], fill=(34, 184, 192, alpha))
        img = Image.alpha_composite(img, layer)
    img.convert("RGB").save(p, optimize=True)
    return p


def placeholder(name: str, w: int = 1600, h: int = 1000) -> Path:
    """Neutral placeholder used only until the real screenshot exists."""
    CACHE.mkdir(exist_ok=True)
    p = CACHE / f"placeholder-{name}.png"
    if name == "citizen-mobile":
        w, h = 780, 1560
    img = Image.new("RGB", (w, h), (238, 244, 250))
    d = ImageDraw.Draw(img)
    d.rectangle([20, 20, w - 20, h - 20], outline=(201, 214, 226), width=6)
    d.text((w // 2, h // 2 - 40), "Screenshot pending", font=_font(56, True), fill=(74, 93, 115), anchor="mm")
    d.text((w // 2, h // 2 + 40), f"docs/img/screens/{name}.png", font=_font(36), fill=(74, 93, 115), anchor="mm")
    img.save(p)
    return p


def screen(name: str) -> tuple[Path, bool]:
    """Return (path, is_real)."""
    p = SCREENS / f"{name}.png"
    if p.exists():
        return p, True
    return placeholder(name), False


def missing_screens() -> list[str]:
    return [n for n in SCREEN_NAMES if not (SCREENS / f"{n}.png").exists()]


def backtest() -> dict | None:
    if BACKTEST.exists():
        try:
            return json.loads(BACKTEST.read_text())
        except json.JSONDecodeError:
            return None
    return None
