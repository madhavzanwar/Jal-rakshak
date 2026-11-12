"""Text deliverables per kit: abstract (.md + 1-page .pdf), README_SUBMIT.md, extras; and SOURCES.md."""
from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import markdown
import pymupdf

import content as C

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SUB = ROOT / "submission"
CACHE = HERE / ".cache"

TAGLINE = "Agentic AI flood early warning for India: open data, local LLM, 5 languages"
SHORT = ("JalRakshak turns free rainfall and river forecasts into ward-level flood risk for 12 Indian cities, then "
         "local-LLM agents draft 5-language SMS/WhatsApp alerts, evacuation routes and a situation report for an "
         "officer to approve. Zero paid services; runs on a laptop.")

SOURCES = [
    ("≈40 Mha (≈12% of land) flood-prone — Rashtriya Barh Ayog (1980), restated by PIB (Ministry of Jal Shakti), 2022",
     "https://pib.gov.in/PressReleasePage.aspx?PRID=1848476"),
    ("1,09,374 deaths and ₹4,00,097 crore damage from floods and heavy rain, 1953–2018 — Standing Committee on "
     "Water Resources, 17th Lok Sabha, reported by Down To Earth (6 Aug 2021)",
     "https://www.downtoearth.org.in/natural-disasters/floods-heavy-rains-killed-100-000-in-65-years-caused-loss-of-rs-4-lakh-crore-78340"),
    ("2.2 million (22 lakh) people affected in 2,542 villages of 28/35 Assam districts as of 26 June 2022; 217,413 "
     "people in 564 relief camps — UNICEF India, Assam Floods 2022 Situation Report, 27 June 2022",
     "https://www.unicef.org/media/123376/file/India-Assam-Foods-SitRep-27-June-2022.pdf"),
    ("24 hours' warning of a hazard can reduce damage by 30% — Global Commission on Adaptation (2019), cited by "
     "the UN Early Warnings for All initiative",
     "https://www.un.org/en/climatechange/early-warnings-for-all"),
    ("UN Early Warnings for All fact sheet (Aug 2025), same 24 h / 30% figure",
     "https://www.un.org/sites/un2.un.org/files/earlywarnings_fastfacts_2025-08.pdf"),
    ("Mother-tongue shares, Census 2011 (C-16): Hindi 43.63%, Bengali 8.03%, Marathi 6.86%, Tamil 5.70% "
     "(sum ≈64%) — reported by Factly",
     "https://factly.in/a-major-dravidian-language-is-now-the-mother-tongue-of-only-18-9-indians-down-from-23-in-1971"),
    ("Flood-prone area later revised to 49.8 Mha by the 12th Plan working group — Central Water Commission",
     "https://cwc.gov.in/fm-projects"),
]

ESTIMATES = [
    "≈₹185 crore/yr avoidable damage = 30% damage reduction (GCA) × 10% of flood-exposed households reached "
    "(our assumption) × ₹6,150 crore/yr average flood damage (₹4,00,097 crore ÷ 65 years, Standing Committee). "
    "Illustrative only; ignores growth in exposure and inflation.",
    "5.5 crore residents = sum of the city population figures in our seed data (backend/jalrakshak/data/cities.py) "
    "for the 12 cities; ward values are synthetic and labelled as such.",
]


# ------------------------------------------------------------------ abstract
def abstract_md(kit: dict) -> str:
    return f"""# JalRakshak: agentic flood early warning and response for India

**Team:** Madhav Zanwar, Divyani Papalkar ({C.COLLEGE})  
**Event:** {kit['event_long']} · **Track:** {kit['track']}  
**Code:** {C.GITHUB} · **Live demo:** {C.DEMO_URL}

## Problem
About 40 million hectares, roughly 12% of India, is flood-prone, and floods and heavy rain killed 1,09,374 people
between 1953 and 2018 [1, 2]. Good rainfall and river forecasts exist, but they rarely become ward-level,
local-language instructions that a district officer can approve and a citizen can act on in time.

## Solution
JalRakshak is an agentic early-warning and response platform that runs on a laptop with zero paid services or
API keys. It pulls free Open-Meteo rainfall forecasts and GloFAS river-discharge forecasts for 12 flood-prone
cities (Mumbai, Chennai, Guwahati, Patna, Kochi, Srinagar, Kolkata, Bhubaneswar, Surat, Hyderabad, Pune,
Dibrugarh) and computes a transparent 0–100 ward-level flood-risk score for the next 72 hours from IMD rainfall
categories, GloFAS percentile thresholds, antecedent rain and ward vulnerability, shown as Green, Yellow, Orange
or Red with every factor visible. An optional LightGBM model adds a flood-day probability, reported with an honest
time-split backtest.

## Agentic layer
Four agents run on a local open LLM (Ollama, Qwen2.5 3B) through our own ReAct tool-calling loop, with a
deterministic rules fallback. The **Monitor** decides when to alert; the **Alert drafter** writes SMS (≤160
characters) and WhatsApp alerts in English, हिन्दी, मराठी, தமிழ் and বাংলা; the **Evacuation planner** finds the
nearest safe shelters and hospitals with OSRM routing; the **SitRep** agent writes a district-officer situation
report (PDF). Guardrails reject invented numbers, wrong scripts and over-length messages and require the 112
helpline. Every step is logged with its reasoning and inputs, and nothing is sent without human approval
(dispatch is simulated in the prototype).

## Users and impact
Officers get a map dashboard, ward drill-down, agent timeline and one-click approval. Citizens get a light,
offline-capable page for low-end phones with their risk, what to do now, the nearest shelter and emergency
numbers. Just 24 hours' warning can cut damage by about 30% [3].

## Built with
FastAPI, React PWA (Leaflet, Recharts), Ollama + Qwen2.5, LightGBM, OpenStreetMap, OSRM, Open-Meteo, GloFAS;
`docker compose up`; demo replay of a synthetic Assam-monsoon-inspired flood. Open source (MIT).

<p class="src">[1] Rashtriya Barh Ayog (1980) via PIB, 2022. [2] Standing Committee on Water Resources, 17th Lok
Sabha (via Down To Earth, 2021). [3] Global Commission on Adaptation, via UN Early Warnings for All. Full URLs in
submission/SOURCES.md.</p>
"""


CSS = """
@page { size: A4; margin: 14mm 15mm 12mm 15mm; }
body { font-family: Inter, 'Noto Sans', 'Noto Sans Devanagari', 'Noto Sans Tamil', 'Noto Sans Bengali', sans-serif;
       font-size: %(fs)spt; line-height: 1.38; color: #12263F; }
h1 { font-size: 17pt; color: #0B1F3A; margin: 0 0 5pt 0; letter-spacing: -0.2pt; }
h2 { font-size: 11.5pt; color: #0E7C86; margin: 9pt 0 2pt 0; text-transform: uppercase; letter-spacing: 0.4pt; }
p { margin: 0 0 4pt 0; }
strong { color: #0B1F3A; }
code { font-family: 'DejaVu Sans Mono', monospace; font-size: 0.92em; background: #EEF4FA; padding: 0 2pt; }
p.src { font-size: 8pt; color: #4A5D73; margin-top: 9pt; border-top: 1px solid #C9D6E2; padding-top: 4pt; }
body > p:nth-of-type(1) { font-size: 9pt; color: #4A5D73; }
"""


def md_to_pdf(md_text: str, out_pdf: Path, max_pages: int = 1) -> int:
    CACHE.mkdir(exist_ok=True)
    body = markdown.markdown(md_text, extensions=["extra", "nl2br"] if False else ["extra"])
    for fs in (10.5, 10, 9.6, 9.2, 8.8):
        html = CACHE / (out_pdf.stem + ".html")
        html.write_text(f'<!doctype html><html><head><meta charset="utf-8"><style>{CSS % {"fs": fs}}</style>'
                        f"</head><body>{body}</body></html>", encoding="utf-8")
        jobs = CACHE / "pdf_jobs.json"
        jobs.write_text(json.dumps([{"type": "pdf", "src": str(html), "out": str(out_pdf)}]))
        subprocess.run(["node", str(HERE / "html_render.mjs"), str(jobs)], check=True)
        pages = len(pymupdf.open(out_pdf))
        if pages <= max_pages:
            return pages
    raise SystemExit(f"{out_pdf} does not fit on {max_pages} page(s)")


def word_count(md_text: str) -> int:
    t = re.sub(r"<[^>]+>", " ", md_text)
    t = re.sub(r"[#*`>|]", " ", t)
    t = re.sub(r"https?://\S+", " URL ", t)
    return len([w for w in t.split() if re.search(r"\w", w)])


# ------------------------------------------------------------------ VYTRON round 2 abstract (300–500 words)
def vytron_abstract() -> str:
    return f"""# JalRakshak: agentic flood early warning and response for India

**Team:** Madhav Zanwar, Divyani Papalkar, {C.COLLEGE}  
**GitHub:** {C.GITHUB}  
**Live demo:** {C.DEMO_URL}

Floods are India's most frequent large disaster. Roughly 40 million hectares, about 12% of the country, is
flood-prone, and floods and heavy rain killed 1,09,374 people between 1953 and 2018 according to Parliament's
Standing Committee on Water Resources. In June 2022 alone, about 22 lakh people in 28 Assam districts were
affected. Forecasts already exist; what is missing is the last mile: turning rainfall and river forecasts into
ward-level, local-language instructions that a district officer can trust and a citizen can act on in time.

JalRakshak is an agentic early-warning and response platform built only on free, open data and open-source
software. Every three hours it pulls Open-Meteo rainfall forecasts and GloFAS river-discharge forecasts for 12
flood-prone cities: Mumbai, Chennai, Guwahati, Patna, Kochi, Srinagar, Kolkata, Bhubaneswar, Surat, Hyderabad,
Pune and Dibrugarh. A deterministic risk engine combines India Meteorological Department heavy-rain categories,
GloFAS percentile danger thresholds, the past week's rain and ward vulnerability into a transparent 0–100 score
for the next 72 hours, shown as Green, Yellow, Orange or Red with every factor visible. An optional LightGBM model
adds a flood-day probability, evaluated with an honest time-split backtest so we report real accuracy rather than
a flattering one.

On top of the score sits an agentic layer running on a local open model, Qwen2.5 3B through Ollama, using our own
ReAct tool-calling loop. A Monitor agent decides whether and where to alert. An Alert drafter writes SMS and
WhatsApp messages in English, Hindi, Marathi, Tamil and Bengali, using vetted templates for the Indic languages.
An Evacuation planner finds the nearest safe shelters and hospitals and routes people there with OSRM. A SitRep
agent writes a situation report for the district officer as a PDF. Guardrails reject invented numbers, wrong
scripts and over-length messages and insist on the 112 helpline. Every step is logged with its reasoning and
inputs, a rules engine takes over if the model is unavailable, and nothing is sent until a human approves it.

Citizens get a light, offline-capable web app that works on low-end phones: type a locality and see the risk,
what to do now, the nearest shelter and emergency numbers. The whole system runs on a laptop with one command,
`docker compose up`, needs no paid services or API keys, and includes a demo replay of a synthetic flood inspired
by Assam's monsoon so judges can watch the full flow.

The UN's Early Warnings for All initiative notes that just 24 hours' warning can cut damage by about 30%.
JalRakshak aims to make that warning local, understandable and actionable.
"""


# ------------------------------------------------------------------ chapters from DEMO_SCRIPT.md
def chapters() -> list[tuple[str, str]]:
    script = (ROOT / "docs" / "DEMO_SCRIPT.md").read_text(encoding="utf-8")
    scenes = re.findall(r"## Scene \d+ — (.+?)\n.*?\*\*Narration:\*\* (.+?)\n", script, re.S)
    words = [len(n.split()) for _, n in scenes]
    total = sum(words)
    duration = None
    video = SUB / "JalRakshak_demo.mp4"
    if video.exists() and shutil.which("ffprobe"):
        r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0",
                            str(video)], capture_output=True, text=True)
        try:
            duration = float(r.stdout.strip())
        except ValueError:
            duration = None
    timings_file = next(iter(sorted((ROOT / "scripts").glob("video/**/*timing*.json"))), None)
    starts = None
    if timings_file:
        try:
            data = json.loads(timings_file.read_text())
            items = data if isinstance(data, list) else data.get("scenes", [])
            starts = [float(it.get("start", it.get("start_s"))) for it in items]
            if len(starts) != len(scenes):
                starts = None
        except Exception:  # noqa: BLE001
            starts = None
    if starts is None:
        dur = duration or total / 2.45
        t, starts = 0.0, []
        for w in words:
            starts.append(t)
            t += dur * w / total
    out = []
    for (name, _), s in zip(scenes, starts):
        out.append((f"{int(s // 60)}:{int(s % 60):02d}", name.strip()))
    return out


# ------------------------------------------------------------------ README_SUBMIT
COMMON_LINKS = f"""| Field | Value |
|---|---|
| GitHub repository | {C.GITHUB} |
| Live demo (static replay, no install) | {C.DEMO_URL} |
| Demo video file | `{C.VIDEO_FILE}` |
| YouTube link | <paste after upload> |
"""

TEAM_BLOCK = f"""| Field | Value |
|---|---|
| Team name | JalRakshak |
| Members | Madhav Zanwar, Divyani Papalkar |
| Institute | {C.COLLEGE} |
| Project title | JalRakshak: agentic flood early warning and response for India |
| Tagline | {TAGLINE} |
| Short description (≈300 chars) | {SHORT} |
"""


def readme(kit_id: str, kit: dict, deck: Path, n: int, extra: dict) -> str:
    deck_name = deck.name
    pdf_name = deck.stem + ".pdf"
    head = f"# {kit['event_long']} — what to upload where\n\nPlatform: **{kit['platform']}** · Prize: {kit['prize']} · " \
           f"Track/theme: **{kit['track']}**\n\nAll files are in `submission/{kit_id}/`. Regenerate everything with " \
           f"`scripts/decks/build_all.sh`.\n"
    files = f"""
## Files in this kit

| File | What it is |
|---|---|
| `{deck_name}` | Pitch deck, {n} slides, 16:9 |
| `_render/{pdf_name}` | PDF export of the deck (generated locally by build_all.sh, gitignored; upload this where a PDF is required) |
| `abstract.md` / `abstract.pdf` | One-page abstract |
"""
    for f, d in extra.get("files", []):
        files += f"| `{f}` | {d} |\n"
    body = extra["body"]
    tail = f"""
## Links (paste exactly)

{COMMON_LINKS}
## Team details

{TEAM_BLOCK}
## Before you press submit

- [ ] Open the deck in PowerPoint / Google Slides once and check fonts (Inter; Noto Sans for Indic text). If
      Inter is missing, install it or export the PDF from `_render/` instead.
- [ ] Upload `{C.VIDEO_FILE}` to YouTube (unlisted is fine unless the rules say public) and paste the link above
      and into every "video" field.
- [ ] Check the live demo link opens on a phone.
- [ ] Keep the GitHub repository public until results are announced.
"""
    return head + files + body + tail


def kit_extras(kit_id: str, kit: dict, deck: Path, n: int, kit_dir: Path) -> dict:
    deck_name = deck.name
    pdf = deck.stem + ".pdf"
    if kit_id == "khacks-4.0":
        return {"body": f"""
## IMPORTANT: move the content into the official K! Hacks idea template

`templates/khacks_template.pptx` was **not** available when this kit was built, so `{deck_name}` is a clean
10-slide deck in our own design. **Before uploading**, download the official K! Hacks 4.0 idea-submission
template from the Unstop event page and copy the content in, slide by slide, **without changing the template's
structure** (keep its slide order, titles and logos). Suggested mapping:

| Template section (typical) | Take content from our slide |
|---|---|
| Title / team details | 1 (title) and 10 (team) |
| Problem statement | 2 |
| Proposed solution / idea | 3 |
| Agentic AI / innovation / uniqueness | 4 and 5 |
| Prototype / screenshots / demo | 6 |
| Architecture / technical approach | 7 |
| Feasibility, ML, validation | 8 |
| Impact / benefits | 9 |
| Team | 10 |

If the official template is later saved as `templates/khacks_template.pptx`, re-run the build and fill it in
place instead.

## Unstop submission form (K! Hacks 4.0)

| Unstop field | What to enter / upload |
|---|---|
| Track / theme | **Disaster Management** (mention *Agentic AI* in the title/description) |
| Idea title | JalRakshak: Agentic AI for flood early warning and response |
| Idea description | Short description below + first paragraph of `abstract.md` |
| Presentation (PPT/PDF) | The official template filled with our content (export to PDF if the form asks for PDF) |
| Abstract / supporting document (if asked) | `abstract.pdf` |
| GitHub / prototype link | {C.GITHUB} |
| Demo link | {C.DEMO_URL} |
| Video link (if asked) | YouTube link: <paste after upload> |
"""}
    if kit_id == "hacknova-2.0":
        return {"body": f"""
## Unstop submission form (HackNova'27 2.0)

| Unstop field | What to enter / upload |
|---|---|
| Theme | **ResQTech (Disaster Resilience)** |
| Project / idea title | JalRakshak: agentic flood early warning and response for India |
| Problem statement | Slide 2 text, or the "Problem" paragraph of `abstract.md` |
| Solution description | Short description below + "Solution" and "Agentic layer" paragraphs of `abstract.md` |
| Presentation | `{deck_name}` (or `_render/{pdf}` if PDF only). Sections: problem (2), solution (3), methodology (4–6), demo screenshots (7–9), architecture (10), expected impact (11), tech stack (12), team (13) |
| Abstract (if asked) | `abstract.pdf` |
| GitHub link | {C.GITHUB} |
| Prototype / demo link | {C.DEMO_URL} |
| Video link (if asked) | YouTube link: <paste after upload> |
"""}
    if kit_id == "vytron-26":
        ab = vytron_abstract()
        (kit_dir / "abstract_round2.md").write_text(ab, encoding="utf-8")
        # count only the abstract prose (exclude title and link header lines)
        prose = "\n".join(l for l in ab.splitlines() if not l.startswith(("#", "**")))
        wc = word_count(prose)
        if not 300 <= wc <= 500:
            raise SystemExit(f"VYTRON round-2 abstract has {wc} words (must be 300–500)")
        return {"files": [("abstract_round2.md", f"Round 2 abstract, {wc} words (prose only)"),
                          ("demo_talk_track.md", "Round 3: timed 5-minute online demo script + judge Q&A prep")],
                "body": f"""
## Round 1 — PPT (Unstop)

| Unstop field | What to enter / upload |
|---|---|
| Idea / project title | JalRakshak: agentic flood early warning and response for India |
| Presentation | `{deck_name}` (or `_render/{pdf}` if the form wants PDF) |
| Short description | Short description below |

## Round 2 — abstract + GitHub

| Unstop field | What to enter / upload |
|---|---|
| Abstract (300–500 words) | Paste the body of `abstract_round2.md` — **word count: {wc} words** (prose, excluding the title and link lines) |
| GitHub link | {C.GITHUB} |
| Demo link (if a field exists) | {C.DEMO_URL} |

## Round 3 — online demo

Follow `demo_talk_track.md` (≈5 minutes, with what to click, plus 10 likely judge questions with answers).
Before the call: open {C.DEMO_URL} in one tab and the local app (`docker compose up`) in another; have
`{C.VIDEO_FILE}` ready as a fallback if screen sharing or the network fails.
""", "wc": wc}
    if kit_id == "clash-of-commits":
        return {"body": f"""
## Devfolio project form (Clash of Commits)

The deck has **exactly {n} slides** (checked by the build): title, problem, who it's for, solution, ML + agents,
tech stack + architecture, execution & build plan, demo, impact, team.

| Devfolio field | What to enter / upload |
|---|---|
| Track | **AI & Machine Learning** |
| Project name | JalRakshak |
| Tagline | {TAGLINE} |
| The problem it solves | India's flood forecasts rarely become ward-level, local-language instructions in time. JalRakshak scores flood risk for every ward for the next 72 hours from open rainfall and river forecasts, and AI agents draft 5-language alerts, evacuation routes and a situation report for an officer to approve. Citizens get a light offline page with their risk and nearest shelter. |
| Challenges we ran into | Getting a 3B local model to call tools reliably (own ReAct loop with strict JSON and a rules fallback); stopping hallucinated numbers (guardrails compare every number with tool outputs); Indic SMS length and script checks; building honest flood labels from reanalysis and evaluating LightGBM with a time split instead of a random split. |
| Technologies used (tags) | Python, FastAPI, Pydantic, LightGBM, pandas, Ollama, Qwen2.5, React, TypeScript, Vite, Leaflet, Recharts, OpenStreetMap, OSRM, Open-Meteo, GloFAS, Docker, Playwright |
| Links | GitHub: {C.GITHUB} · Demo: {C.DEMO_URL} |
| Video demo | YouTube link: <paste after upload> (file: `{C.VIDEO_FILE}`) |
| Pictures | Upload `docs/img/screens/*.png` and `docs/img/architecture.png` |
| Presentation / deck | `{deck_name}` (or `_render/{pdf}` if Devfolio asks for PDF) |
| Abstract (if asked) | `abstract.pdf` |
"""}
    if kit_id == "hacktopia-pune-2026":
        return {"files": [("youtube_pitch.md", "YouTube title, description, tags and chapters for the pitch video")],
                "body": f"""
## Round 1 — Unstop submission (PPT + GitHub + YouTube pitch)

| Unstop field | What to enter / upload |
|---|---|
| Idea / project title | JalRakshak: agentic flood early warning and response for India |
| Presentation | `{deck_name}` (or `_render/{pdf}` if PDF only) |
| GitHub link | {C.GITHUB} |
| YouTube pitch link | YouTube link: <paste after upload> — upload `{C.VIDEO_FILE}` using `youtube_pitch.md` |
| Demo link (if a field exists) | {C.DEMO_URL} |
| Abstract (if asked) | `abstract.pdf` |

### Judging criteria → where the deck answers them

Each slide carries an orange criterion tag (top right); slide 12 is a one-page map.

| Criterion | Slides |
|---|---|
| Innovation | 3, 4 |
| Problem relevance | 2 |
| Technical implementation | 4, 5, 6 |
| Feasibility | 9 |
| Scalability | 6, 10 |
| User impact | 7, 8, 11 |
| Presentation | 12 + live demo + video |
"""}
    raise KeyError(kit_id)


def youtube_pitch() -> str:
    ch = chapters()
    chap = "\n".join(f"{t} {name}" for t, name in ch)
    return f"""# YouTube pitch — upload details

Video file: `{C.VIDEO_FILE}` · Visibility: unlisted or public as the rules require · Category: Science & Technology

## Title (≤100 chars)
JalRakshak: Agentic AI flood early warning for India | Hacktopia Pune 2026

## Description
JalRakshak turns free, open rainfall and river forecasts into flood warnings people can act on.

It watches 12 flood-prone Indian cities (Mumbai, Chennai, Guwahati, Patna, Kochi, Srinagar, Kolkata,
Bhubaneswar, Surat, Hyderabad, Pune, Dibrugarh), computes a transparent 0–100 flood-risk score for every ward for
the next 72 hours, and runs four AI agents on a local open LLM (Ollama + Qwen2.5 3B): a Monitor that decides when
to alert, an Alert drafter that writes SMS and WhatsApp alerts in English, Hindi, Marathi, Tamil and Bengali, an
Evacuation planner that routes people to the nearest shelter, and a SitRep agent for the district officer.
Guardrails check every message and nothing is sent without human approval.

Zero paid services, no API keys, runs on a laptop with `docker compose up`. The video shows a synthetic flood
replay inspired by Assam's monsoon.

Live demo: {C.DEMO_URL}
Code (MIT): {C.GITHUB}
Team: Madhav Zanwar, Divyani Papalkar · PCCoE Pune

Data and tools: Open-Meteo, GloFAS (Copernicus), OpenStreetMap, OSRM, Leaflet, Ollama, Qwen2.5, FastAPI, React,
Recharts, LightGBM, Piper TTS.

Chapters
{chap}

## Tags
JalRakshak, flood early warning, flood forecasting, disaster management, agentic AI, AI agents, Ollama, Qwen2.5,
LightGBM, GloFAS, Open-Meteo, OpenStreetMap, India floods, Assam floods, multilingual alerts, Hindi, Marathi,
Tamil, Bengali, FastAPI, React, PWA, hackathon, Hacktopia Pune 2026, PCCoE

## Chapters (paste into the description; YouTube needs the first at 0:00)
{chap}

Chapter starts follow the scenes in `docs/DEMO_SCRIPT.md`. They are computed from the final video's scene
timings when available, otherwise from the video duration (or narration length) proportional to each scene's
narration. Check them once against the uploaded video and nudge by a second or two if needed.

## Thumbnail
Use the architecture diagram (`docs/img/architecture.png`) or the dashboard screenshot
(`docs/img/screens/dashboard.png`) with the text "Flood alerts people can act on".
"""


def write_kit_docs(kit_id: str, kit: dict, deck: Path, n: int) -> None:
    kit_dir = deck.parent
    ab = abstract_md(kit)
    (kit_dir / "abstract.md").write_text(ab, encoding="utf-8")
    md_to_pdf(ab, kit_dir / "abstract.pdf")
    if kit_id == "hacktopia-pune-2026":
        (kit_dir / "youtube_pitch.md").write_text(youtube_pitch(), encoding="utf-8")
    extra = kit_extras(kit_id, kit, deck, n, kit_dir)
    (kit_dir / "README_SUBMIT.md").write_text(readme(kit_id, kit, deck, n, extra), encoding="utf-8")
    if "wc" in extra:
        print(f"  VYTRON round-2 abstract: {extra['wc']} words")


def write_sources() -> None:
    lines = ["# Sources for numbers used in the submission kits", "",
             "Every figure on a slide carries a short source label; full references are below. Our own projections "
             "are labelled **Estimate** on the slides, with the assumption shown.", "", "## External figures", ""]
    for i, (desc, url) in enumerate(SOURCES, 1):
        lines.append(f"{i}. {desc}  \n   <{url}>")
    lines += ["", "## Our estimates (assumptions)", ""]
    lines += [f"- {e}" for e in ESTIMATES]
    lines += ["", "## Product facts", "",
              "- Risk formula: `backend/RISK_FORMULA.md` and `backend/jalrakshak/risk/scoring.py`.",
              "- Model metrics: `backend/models/backtest.json`, method in `docs/MODEL.md`.",
              "- Ward, population and shelter seed data are synthetic and labelled as such in the app.", ""]
    (SUB / "SOURCES.md").write_text("\n".join(lines), encoding="utf-8")
