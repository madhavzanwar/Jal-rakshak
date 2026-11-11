"""Programmatic architecture diagram for JalRakshak.

Writes docs/img/architecture.svg and renders docs/img/architecture.png (2x) with Playwright.
Run: /opt/tools/bin/python scripts/decks/architecture.py
"""
from __future__ import annotations

import json
import subprocess
from html import escape
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OUT_DIR = ROOT / "docs" / "img"
CACHE = HERE / ".cache"

W, H = 1920, 1080
NAVY = "#0B1F3A"
INK = "#12263F"
MUTED = "#4A5D73"
TEAL = "#0E7C86"
TEAL_L = "#E3F4F5"
LINE = "#C9D6E2"
SKY = "#EEF4FA"
AMBER = "#F08A24"
AMBER_L = "#FFF1E3"
RED = "#D64545"
GREEN = "#2E9E5B"
YELLOW = "#E5B21E"
VIOLET = "#5B4DB7"
VIOLET_L = "#EFEDFB"

parts: list[str] = []


def rect(x, y, w, h, fill="#FFFFFF", stroke=LINE, sw=2, rx=16, dash=None):
    d = f' stroke-dasharray="{dash}"' if dash else ""
    parts.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" fill="{fill}" '
                 f'stroke="{stroke}" stroke-width="{sw}"{d}/>')


def text(x, y, s, size=18, weight=400, fill=INK, anchor="start", italic=False):
    st = ' font-style="italic"' if italic else ""
    parts.append(f'<text x="{x}" y="{y}" font-size="{size}" font-weight="{weight}" fill="{fill}" '
                 f'text-anchor="{anchor}"{st}>{escape(s)}</text>')


def lines(x, y, items, size=17, fill=MUTED, gap=None, weight=400):
    gap = gap or int(size * 1.35)
    for i, s in enumerate(items):
        text(x, y + i * gap, s, size=size, fill=fill, weight=weight)


def arrow(x1, y1, x2, y2, color=TEAL, dash=None, label=None, lx=None, ly=None, width=3):
    d = f' stroke-dasharray="{dash}"' if dash else ""
    mid = "ah-" + color.strip("#")
    parts.append(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{color}" '
                 f'stroke-width="{width}"{d} marker-end="url(#{mid})"/>')
    if label:
        text(lx if lx is not None else (x1 + x2) / 2, ly if ly is not None else (y1 + y2) / 2 - 10,
             label, size=15, fill=color, weight=600, anchor="middle")


def poly_arrow(points, color=TEAL, dash=None, width=3):
    d = f' stroke-dasharray="{dash}"' if dash else ""
    mid = "ah-" + color.strip("#")
    pts = " ".join(f"{x},{y}" for x, y in points)
    parts.append(f'<polyline points="{pts}" fill="none" stroke="{color}" stroke-width="{width}"{d} '
                 f'marker-end="url(#{mid})" stroke-linejoin="round"/>')


def header(x, y, s, color=TEAL):
    text(x, y, s.upper(), size=15, weight=700, fill=color)


def chip(x, y, w, s, fill, fg="#FFFFFF", h=30, size=15):
    rect(x, y, w, h, fill=fill, stroke=fill, sw=0, rx=h / 2)
    text(x + w / 2, y + h / 2 + size * 0.36, s, size=size, weight=600, fill=fg, anchor="middle")


def build_svg() -> str:
    parts.clear()
    # ---------- column 1: open data sources ----------
    header(40, 62, "Open data sources (free, no keys)")
    sources = [
        ("Open-Meteo Forecast", ["Hourly rainfall: next 72 h", "+ observed past 7 days"]),
        ("GloFAS (Copernicus)", ["River discharge forecast via", "Open-Meteo Flood API"]),
        ("GloFAS reanalysis", ["~40 yrs of discharge →", "percentile danger thresholds"]),
        ("OpenStreetMap", ["Basemap tiles + Nominatim", "geocoding for citizen search"]),
        ("OSRM routing", ["Road routes to shelters", "(straight-line fallback)"]),
    ]
    y0, bh, gap = 86, 150, 30
    for i, (t, sub) in enumerate(sources):
        y = y0 + i * (bh + gap)
        rect(40, y, 300, bh, fill="#FFFFFF")
        text(62, y + 44, t, size=22, weight=700)
        lines(62, y + 80, sub, size=17)
        arrow(340, y + bh / 2, 384, y + bh / 2)

    # ---------- column 2: adapters + cache ----------
    header(392, 62, "Adapters + cache")
    rect(392, 86, 250, 870, fill=SKY, stroke=LINE)
    text(414, 134, "Data adapters", size=22, weight=700)
    lines(414, 172, ["Async HTTP client", "retry + backoff", "per-source timeouts"], size=17)
    rect(410, 270, 214, 190, fill="#FFFFFF")
    text(428, 308, "JSON disk cache", size=19, weight=700)
    lines(428, 342, ["TTL per source", "stale-on-error", "fallback → UI", "shows \"stale\""], size=16)
    rect(410, 490, 214, 168, fill="#FFFFFF")
    text(428, 528, "City seed", size=19, weight=700)
    lines(428, 562, ["12 cities, wards,", "gauges, shelters", "(synthetic, labelled)"], size=16)
    text(414, 720, "Works offline on", size=17, fill=MUTED)
    text(414, 744, "last-known data", size=17, fill=MUTED)
    arrow(642, 300, 688, 300)

    # ---------- column 3: risk engine ----------
    header(690, 62, "Risk engine (deterministic)")
    rect(690, 86, 320, 560, fill="#FFFFFF", stroke=TEAL, sw=3)
    text(712, 134, "Ward flood-risk score", size=22, weight=700)
    comps = [("Rain", "IMD 24 h categories", "#2A7FC1"),
             ("River", "GloFAS peak ÷ danger", TEAL),
             ("Antecedent", "7-day soil wetness", "#7A8B9E"),
             ("Vulnerability", "low-lying, drainage", VIOLET)]
    for i, (a, b, c) in enumerate(comps):
        y = 168 + i * 70
        rect(712, y, 14, 46, fill=c, stroke=c, rx=7, sw=0)
        text(740, y + 20, a, size=18, weight=700)
        text(740, y + 42, b, size=16, fill=MUTED)
    text(712, 476, "0–100 score, next 72 h", size=19, weight=700)
    chip(712, 496, 66, "Green", GREEN, size=14)
    chip(784, 496, 70, "Yellow", YELLOW, fg=INK, size=14)
    chip(860, 496, 72, "Orange", AMBER, size=14)
    chip(938, 496, 52, "Red", RED, size=14)
    text(712, 566, "Factor-level explanation", size=16, fill=MUTED)
    text(712, 590, "for every ward (no black box)", size=16, fill=MUTED)

    rect(690, 690, 320, 266, fill=VIOLET_L, stroke=VIOLET, sw=2, dash="8 6")
    text(712, 734, "LightGBM (optional)", size=21, weight=700, fill=VIOLET)
    lines(712, 770, ["P(flood-day) per city", "honest time-split backtest", "trained on GloFAS + ERA5", "reanalysis; test 2021–24"], size=16)
    arrow(850, 690, 850, 650, color=VIOLET)
    arrow(1010, 300, 1054, 300)

    # ---------- column 4: agent layer ----------
    header(1056, 62, "Agent layer · own ReAct tool-calling loop", color=AMBER)
    rect(1056, 86, 450, 700, fill=AMBER_L, stroke=AMBER, sw=3)
    agents = [("1  Monitor", "decides whether to alert"),
              ("2  Alert drafter", "SMS ≤160 + WhatsApp, 5 languages"),
              ("3  Evacuation planner", "nearest shelter / hospital, OSRM"),
              ("4  SitRep", "district-officer report (PDF)")]
    for i, (a, b) in enumerate(agents):
        y = 108 + i * 104
        rect(1078, y, 406, 84, fill="#FFFFFF", stroke="#F3C08E")
        text(1100, y + 36, a, size=20, weight=700)
        text(1124, y + 64, b, size=16, fill=MUTED)
        if i < 3:
            arrow(1281, y + 84, 1281, y + 102, color=AMBER, width=2.5)
    rect(1078, 532, 196, 140, fill="#FFFFFF", stroke="#F3C08E")
    text(1094, 566, "Guardrails", size=18, weight=700)
    lines(1094, 594, ["numbers = data", "script + length", "must include 112"], size=15, gap=22)
    rect(1288, 532, 196, 140, fill="#FFFFFF", stroke="#F3C08E")
    text(1304, 566, "Step log", size=18, weight=700)
    lines(1304, 594, ["reasoning, tool", "inputs + outputs", "for every step"], size=15, gap=22)
    rect(1078, 690, 406, 76, fill=AMBER, stroke=AMBER, rx=12)
    text(1281, 724, "Human approval gate", size=20, weight=700, fill="#FFFFFF", anchor="middle")
    text(1281, 750, "nothing is sent without an officer", size=15, fill="#FFFFFF", anchor="middle")

    rect(1056, 826, 450, 130, fill=NAVY, stroke=NAVY)
    text(1078, 868, "Ollama · Qwen2.5 3B (local LLM)", size=21, weight=700, fill="#FFFFFF")
    lines(1078, 900, ["runs on the laptop, no cloud LLM / API key", "deterministic rules fallback if offline"], size=16, fill="#C7D6E6")
    parts.append(f'<line x1="1281" y1="786" x2="1281" y2="824" stroke="{NAVY}" stroke-width="3" '
                 f'marker-end="url(#ah-0B1F3A)" marker-start="url(#as-0B1F3A)"/>')

    # ---------- column 5: API + PWA ----------
    header(1552, 62, "Serve + act")
    rect(1552, 86, 330, 130, fill=NAVY, stroke=NAVY)
    text(1574, 130, "FastAPI  /api", size=22, weight=700, fill="#FFFFFF")
    lines(1574, 162, ["cities, risk, agents, alerts,", "sitrep, evacuation, citizen"], size=16, fill="#C7D6E6")
    arrow(1506, 150, 1550, 150)
    arrow(1717, 216, 1717, 256)

    rect(1552, 258, 330, 420, fill="#FFFFFF", stroke=TEAL, sw=3)
    text(1574, 302, "React PWA", size=22, weight=700)
    text(1574, 330, "installable · offline-capable", size=16, fill=MUTED)
    tiles = ["Dashboard map", "Ward drill-down", "Agent timeline", "Admin approval", "Citizen view"]
    for i, t in enumerate(tiles):
        y = 352 + i * 62
        fill = AMBER_L if t == "Admin approval" else TEAL_L
        rect(1574, y, 286, 50, fill=fill, stroke=fill, rx=10)
        text(1592, y + 32, t, size=18, weight=600)
    poly_arrow([(1552, 563), (1530, 563), (1530, 728), (1488, 728)], color=AMBER, dash="9 6")

    rect(1552, 722, 330, 108, fill=SKY, stroke=LINE)
    text(1574, 760, "Demo replay mode", size=20, weight=700)
    lines(1574, 790, ["synthetic Assam-monsoon-inspired", "flood · static GitHub Pages build"], size=15, gap=21)
    arrow(1717, 722, 1717, 682)

    rect(1552, 860, 330, 96, fill="#FFFFFF", stroke=LINE, dash="8 6")
    text(1574, 898, "Dispatch (simulated)", size=20, weight=700)
    text(1574, 926, "SMS / WhatsApp log only", size=16, fill=MUTED)
    poly_arrow([(1484, 766), (1530, 766), (1530, 906), (1550, 906)], color=AMBER)

    # ---------- footer band ----------
    text(40, 1036, "Open source end-to-end · zero paid services · one command: docker compose up",
         size=18, weight=600, fill=TEAL)
    text(1882, 1036, "JalRakshak architecture", size=16, fill=MUTED, anchor="end")

    markers = []
    for c in {TEAL, AMBER, VIOLET, NAVY}:
        cid = c.strip("#")
        markers.append(f'<marker id="ah-{cid}" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="5" '
                       f'markerHeight="5" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="{c}"/></marker>')
        markers.append(f'<marker id="as-{cid}" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="5" '
                       f'markerHeight="5" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="{c}"/></marker>')
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" '
            f'font-family="Inter, \'Noto Sans\', Arial, sans-serif">'
            f'<defs>{"".join(markers)}</defs>'
            f'<rect width="{W}" height="{H}" fill="#F7FAFC"/>' + "".join(parts) + "</svg>\n")


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    CACHE.mkdir(exist_ok=True)
    svg = build_svg()
    svg_path = OUT_DIR / "architecture.svg"
    svg_path.write_text(svg, encoding="utf-8")
    html = CACHE / "architecture.html"
    html.write_text(f'<!doctype html><html><head><meta charset="utf-8"><style>html,body{{margin:0}}</style>'
                    f'</head><body>{svg}</body></html>', encoding="utf-8")
    jobs = CACHE / "arch_jobs.json"
    jobs.write_text(json.dumps([{"type": "png", "src": str(html), "out": str(OUT_DIR / "architecture.png"),
                                 "width": W, "height": H, "scale": 2}]))
    subprocess.run(["node", str(HERE / "html_render.mjs"), str(jobs)], check=True)
    print("wrote", svg_path, OUT_DIR / "architecture.png")


if __name__ == "__main__":
    main()
