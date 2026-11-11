"""All deck / abstract / README content, as data. design.py renders it; build.py wires kits.

Rules: every external number carries a source label (full URLs in submission/SOURCES.md);
our own projections are marked estimate=True and state their assumption.
"""
from __future__ import annotations

import assets

GITHUB = "https://github.com/madhavzanwar/Jal-rakshak"
DEMO_URL = "https://madhavzanwar.github.io/Jal-rakshak/"
VIDEO_FILE = "submission/JalRakshak_demo.mp4"
TEAM = ["Madhav Zanwar", "Divyani Papalkar"]
COLLEGE = "Pimpri Chinchwad College of Engineering (PCCoE), Pune"

CITIES = ["Mumbai", "Chennai", "Guwahati", "Patna", "Kochi", "Srinagar", "Kolkata", "Bhubaneswar", "Surat",
          "Hyderabad", "Pune", "Dibrugarh"]

# ------------------------------------------------------------------ facts (sourced)
F = {
    "area": {"value": "≈40 Mha", "label": "of India is flood-prone, about 12% of its land area",
             "source": "Rashtriya Barh Ayog (1980), via PIB 2022"},
    "deaths": {"value": "1,09,374", "label": "deaths from floods and heavy rain, 1953–2018 (≈1,700 a year)",
               "source": "Parliament Standing Committee on Water Resources (17th Lok Sabha)"},
    "loss": {"value": "₹4.0 lakh cr", "label": "flood damage 1953–2018, ≈₹6,150 crore a year on average",
             "source": "Parliament Standing Committee on Water Resources (17th Lok Sabha)"},
    "assam": {"value": "22 lakh", "label": "people hit in 28 of 35 Assam districts on 26 June 2022; 2.17 lakh in relief camps",
              "source": "UNICEF Assam Floods SitRep, 27 Jun 2022 (state data)"},
    "ew": {"value": "30%", "label": "less damage when people get just 24 hours' warning of a hazard",
           "source": "Global Commission on Adaptation, cited by UN/WMO Early Warnings for All"},
    "lang": {"value": "≈64%", "label": "of Indians have Hindi, Bengali, Marathi or Tamil as mother tongue",
             "source": "Census of India 2011 (C-16), via Factly"},
    "est_value": {"value": "≈₹185 cr/yr", "estimate": True,
                  "label": "avoidable flood damage if warnings reach 10% of exposed households",
                  "source": "Estimate: 30% × 10% reach × ₹6,150 cr/yr average damage"},
    "est_cover": {"value": "5.5 crore", "estimate": True,
                  "label": "residents in the 12 pilot cities, scored ward by ward",
                  "source": "Estimate: sum of city populations in our seed data (96 synthetic wards)"},
    "zero": {"value": "₹0", "label": "recurring cost: no paid APIs, no keys, local LLM on a laptop",
             "source": "Project design (Open-Meteo, GloFAS, OSM, OSRM, Ollama)"},
}

SOURCES_SHORT = {
    "problem": "Sources: PIB 2022; Standing Committee on Water Resources, 17th Lok Sabha (via Down To Earth); "
               "UNICEF SitRep 27 Jun 2022. URLs: submission/SOURCES.md",
    "impact": "Sources: UN Early Warnings for All; Census 2011 via Factly; Standing Committee on Water Resources. "
              "Orange = our estimates. URLs: submission/SOURCES.md",
}


# ------------------------------------------------------------------ backtest → metric tiles
def ml_metrics() -> tuple[list[dict], str]:
    """Read backend/models/backtest.json if present; report what it says, honestly."""
    bt = assets.backtest()
    if not bt:
        return ([{"value": "pending", "label": "Backtest metrics (backend/models/backtest.json not yet generated)"}],
                "Metrics appear here automatically once the backtest has run.")
    from ml_summary import summarise  # local helper, tolerant to schema changes

    return summarise(bt)


# ------------------------------------------------------------------ shared slide blocks
def title(subtitle="Agentic flood early warning and response for India",
          tagline="Open forecasts → ward-level risk → AI agents draft 5-language alerts and evacuation plans → "
                  "an officer approves. Free data, local LLM, runs on a laptop."):
    return {"layout": "title", "subtitle": subtitle, "tagline": tagline, "image": "dashboard",
            "notes": "Introduce JalRakshak and the team in one breath, then go straight to the problem."}


def problem(title_="Forecasts exist. Last-mile action doesn't", tag=None):
    return {
        "layout": "stats", "kicker": "The problem", "title": title_, "tag": tag,
        "points": [
            {"icon": "radio-tower", "head": "Warnings stop at the district",
             "body": "Rain and river forecasts exist (IMD, CWC, GloFAS) but rarely become ward-level, "
                     "local-language instructions in time."},
            {"icon": "users", "head": "Officers are overloaded",
             "body": "Control rooms juggle gauges, bulletins, shelters and translations by hand while the "
                     "water rises."},
            {"icon": "smartphone", "head": "Vague alerts don't help",
             "body": "\"Heavy rain likely\" doesn't say which ward, how bad, where to go or whom to call."},
        ],
        "stats": [F["area"], F["deaths"], F["loss"], F["assam"]],
        "sources": SOURCES_SHORT["problem"],
        "notes": "Numbers: 40 Mha flood-prone (1980 national flood commission), 1.09 lakh deaths and ₹4 lakh crore "
                 "damage 1953-2018 (Parliament standing committee), 22 lakh affected in Assam on 26 June 2022.",
    }


def solution(tag=None, title_="JalRakshak turns open forecasts into actions", agentic_first=False):
    cards = [
        {"icon": "cloud-rain", "head": "Sense", "color": TEAL_HEX(),
         "body": ["Open-Meteo rainfall + GloFAS river discharge", "12 flood-prone cities, 96 wards",
                  "Cached, works on last-known data"]},
        {"icon": "chart-line", "head": "Score", "color": TEAL_HEX(),
         "body": ["Transparent 0–100 ward risk, next 72 h", "IMD rain categories + GloFAS thresholds",
                  "Optional LightGBM probability"]},
        {"icon": "bot", "head": "Act — AI agents", "color": "F08A24", "fill": "FFF1E3",
         "body": ["Monitor decides when to alert", "Drafter writes SMS + WhatsApp in 5 languages",
                  "Evacuation routes + SitRep PDF"]},
        {"icon": "user-check", "head": "Approve & reach", "color": "0B1F3A",
         "body": ["Officer approves every alert", "Citizen page for low-end phones", "Offline-capable PWA"]},
    ]
    if agentic_first:
        cards[2]["label"] = "AGENTIC AI"
        cards[2]["label_color"] = "D64545"
    return {"layout": "cards", "kicker": "Our solution", "title": title_, "tag": tag, "cards": cards, "cols": 4,
            "body_size": 14,
            "lead": "From forecast to an approved, multilingual alert in minutes, with every step explained.",
            "callout": "Zero paid services · zero API keys · local open LLM · one command: docker compose up",
            "notes": "Four verbs: sense, score, act, approve. Stress the human approval gate."}


def TEAL_HEX():
    return "0E7C86"


def agents(tag=None, title_="Agentic AI on a local open LLM, with guardrails"):
    return {
        "layout": "agents", "kicker": "Agent layer", "title": title_, "tag": tag,
        "agents": [
            {"icon": "eye", "name": "Monitor", "does": "Reads ward risk and river gauges; decides if, where and how urgently "
             "to alert.", "tools": "get_city_risk, get_gauges, get_ward_risk"},
            {"icon": "message-square-text", "name": "Alert drafter", "does": "Writes SMS (≤160 chars) and "
             "WhatsApp alerts in EN, HI, MR, TA, BN.", "tools": "vetted templates, verified facts"},
            {"icon": "route", "name": "Evacuation planner", "does": "Finds the nearest safe shelters and "
             "hospitals for the riskiest wards.", "tools": "find_facilities, OSRM route (straight-line fallback)"},
            {"icon": "file-text", "name": "SitRep", "does": "Writes a district-officer situation report, "
             "exported as a PDF.", "tools": "risk summary, plans, alert status"},
        ],
        "guards": ["No invented numbers", "Script matches language", "SMS length", "Must include 112",
                   "Human approval before send"],
        "facts": [
            {"head": "Own ReAct tool-calling loop", "body": "Thought → tool call → observation, written from "
             "scratch (no agent framework). Every step is logged with reasoning and inputs."},
            {"head": "Ollama · Qwen2.5 3B, local", "body": "No cloud LLM and no API key. If the model is "
             "missing or slow, a deterministic rules engine takes over.", "dark": True},
            {"head": "Humans stay in charge", "body": "Agents draft; officers decide. Dispatch is simulated and "
             "logged, so the full flow can be demoed safely."},
        ],
        "notes": "Explain the ReAct loop and why a small local model is enough: the LLM reasons and chooses tools; "
                 "numbers always come from tools, and guardrails reject anything that doesn't match.",
    }


SAMPLES = [
    {"lang": "English", "text": "JalRakshak RED flood alert, Anil Nagar (Guwahati): Brahmaputra above danger "
                                "level. Move to the nearest shelter now. Help: 112"},
    {"lang": "हिन्दी", "text": "जलरक्षक लाल बाढ़ चेतावनी, अनिल नगर: ब्रह्मपुत्र खतरे के निशान से ऊपर। "
                               "अभी नज़दीकी आश्रय में जाएँ। मदद: 112"},
    {"lang": "मराठी", "text": "जलरक्षक लाल पूर इशारा, अनिल नगर: ब्रह्मपुत्रा धोक्याच्या पातळीवर. "
                             "त्वरित जवळच्या निवाऱ्यात जा. मदत: 112"},
    {"lang": "தமிழ்", "text": "ஜலரக்ஷக் சிவப்பு வெள்ள எச்சரிக்கை, அனில் நகர்: பிரம்மபுத்திரா அபாய "
                             "அளவைத் தாண்டியது. உடனே பாதுகாப்பான இடத்திற்குச் செல்லவும். உதவி: 112"},
    {"lang": "বাংলা", "text": "জলরক্ষক লাল বন্যা সতর্কতা, অনিল নগর: ব্রহ্মপুত্র বিপদসীমার উপরে। "
                            "এখনই নিকটতম আশ্রয়ে যান। সাহায্য: 112"},
]


def alerts(tag=None, title_="Five languages, one approval click"):
    return {"layout": "alerts", "kicker": "Multilingual alerts + human approval gate", "title": title_, "tag": tag,
            "samples": SAMPLES, "image": "admin",
            "caption": "Admin view: review, edit, approve. Dispatch is simulated and logged.",
            "sources": "Sample SMS from the synthetic Guwahati demo scenario. Indic alerts use vetted templates; "
                       "guards check script, length, numbers and 112.",
            "notes": "Show the language tabs. Point at the guard results and the SMS counter."}


def demo(tag=None, title_="See it working"):
    return {"layout": "gallery", "kicker": "Live demo · " + DEMO_URL, "title": title_, "tag": tag,
            "images": [{"image": "dashboard-guwahati", "caption": "City risk", "sub": "72 h horizon, gauges"},
                       {"image": "ward-drilldown", "caption": "Ward drill-down", "sub": "factors, shelters"},
                       {"image": "citizen-mobile", "caption": "Citizen view", "sub": "low-end phones"}],
            "notes": "Real screenshots from the demo replay build."}


def demo_agents(tag=None, title_="Agents at work, officer in control"):
    return {"layout": "gallery", "kicker": "Live demo · agent timeline and approval", "title": title_, "tag": tag,
            "images": [{"image": "agents", "caption": "Agent timeline", "sub": "reasoning, tool calls, guards"},
                       {"image": "admin", "caption": "Admin approval", "sub": "5 languages, edit, approve"}]}


def architecture(tag=None, title_="Architecture: open data in, approved action out"):
    return {"layout": "image", "kicker": "Architecture", "title": title_, "tag": tag, "image": "architecture",
            "notes": "Walk left to right: sources, adapters + cache, risk engine, agents, API, PWA."}


def risk_formula(tag=None, title_="A risk score an officer can audit"):
    return {
        "layout": "cards", "kicker": "Methodology · deterministic risk engine", "title": title_, "tag": tag,
        "cols": 4, "body_size": 13,
        "cards": [
            {"icon": "cloud-rain", "head": "Rain  R", "color": "2A7FC1",
             "body": ["24 h rain on IMD anchors: 64.5 / 115.6 / 204.4 mm", "Peak hourly intensity",
                      "72 h total"]},
            {"icon": "waves", "head": "River  D", "color": TEAL_HEX(),
             "body": ["GloFAS forecast peak ÷ danger level", "Thresholds = percentiles of GloFAS reanalysis",
                      "Hard floors when danger is crossed"]},
            {"icon": "droplets", "head": "Antecedent  A", "color": "4A5D73",
             "body": ["Observed rain of the past 7 days", "Wet soil → faster runoff"]},
            {"icon": "house", "head": "Vulnerability  V", "color": "5B4DB7",
             "body": ["Low-lying, poor drainage, informal housing", "Synthetic per-ward values (labelled)"]},
        ],
        "formula": {"line1": "Score = 100 × (0.75 H + 0.10 A + 0.15 V) × (0.6 + 0.4 V)",
                    "line2": "Hazard H = 1 − (1 − R)(1 − D): rain or river alone can make it severe"},
        "sources": "Formula: backend/RISK_FORMULA.md. Monotone in every input; unit-tested. IMD = India "
                   "Meteorological Department heavy-rain categories.",
        "notes": "Either rain or river alone can make hazard severe. Vulnerability scales the result. "
                 "Every ward shows its factor breakdown.",
    }


def ml(tag=None, title_="ML that reports its real accuracy"):
    metrics, note = ml_metrics()
    return {
        "layout": "ml", "kicker": "Optional LightGBM model · honest backtest", "title": title_, "tag": tag,
        "metrics": metrics, "metrics_note": note,
        "rows": [
            {"icon": "layers", "head": "Training data", "color": "5B4DB7",
             "body": "GloFAS v4 river discharge + ERA5 rainfall reanalysis, 1991–2024, for the 12 cities."},
            {"icon": "clock", "head": "Time-split, no leakage", "color": "5B4DB7",
             "body": "Train on earlier years, test on later years; thresholds use the training period only."},
            {"icon": "scale", "head": "Compared to a baseline", "color": "5B4DB7",
             "body": "Reported next to the rule-based score, so judges can see what ML adds (or doesn't)."},
            {"icon": "shield-check", "head": "Advisory, not in charge", "color": "0B1F3A",
             "body": "The deterministic score drives alerts; the model adds P(flood-day) as context."},
        ],
        "sources": "Metrics read from backend/models/backtest.json; method in docs/MODEL.md.",
        "notes": "Be upfront: labels are proxies built from reanalysis, not official flood records.",
    }


def tech_stack(tag=None, title_="Tech stack: open source end to end"):
    return {
        "layout": "table", "kicker": "Tech stack", "title": title_, "tag": tag,
        "columns": ["Layer", "What we use", "Why"],
        "widths": [2.2, 5.6, 4.333],
        "rows": [
            ["Data", "Open-Meteo Forecast + Flood API (GloFAS v4), ERA5 archive, OpenStreetMap, Nominatim, OSRM",
             "Free, global, no API keys"],
            ["Backend", "Python 3.13, FastAPI, Pydantic v2, httpx, JSON disk cache", "Typed contract, async I/O"],
            ["Risk + ML", "Deterministic scoring (IMD + GloFAS percentiles), LightGBM, pandas, NumPy",
             "Explainable first, ML second"],
            ["Agents", "Ollama + Qwen2.5 3B, own ReAct tool-calling loop, guardrails, rules fallback",
             "Private, offline, no vendor lock-in"],
            ["Frontend", "React 18, Vite, TypeScript, Leaflet, Recharts, zod, PWA service worker",
             "Fast on low-end phones, offline"],
            ["Reports + media", "ReportLab SitRep PDF, Piper TTS + Playwright demo video, python-pptx decks",
             "Reproducible, scripted"],
            ["Deploy", "docker compose (API + web + Ollama); static demo on GitHub Pages", "Runs on one laptop"],
        ],
        "notes": "Everything is open source; credits in CREDITS.md (inspired by FloodGuard and PredictAid).",
    }


def impact(tag=None, title_="Expected impact"):
    return {"layout": "stats", "kicker": "Impact", "title": title_, "tag": tag,
            "stats": [F["ew"], F["lang"], F["est_cover"], F["est_value"]],
            "tile_h": 2.95,
            "chain": [("bell-ring", "Ward-level warning, 3 days ahead"),
                      ("languages", "In the citizen's own language"),
                      ("route", "Clear action: nearest shelter + route"),
                      ("heart-handshake", "Earlier evacuation, fewer deaths, lower losses")],
            "sources": SOURCES_SHORT["impact"],
            "notes": "Separate what is sourced (30%, 64%) from our own estimates (orange tiles)."}


def methodology(tag=None, title_="How it works, every 3 hours"):
    return {
        "layout": "split", "kicker": "Methodology", "title": title_, "tag": tag, "image": "dashboard-guwahati",
        "text_w": 4.9, "size": 14,
        "rows": [
            {"icon": "satellite", "head": "1  Ingest open forecasts",
             "body": "Hourly rain (72 h) and GloFAS discharge per city; cached with stale fallback."},
            {"icon": "chart-line", "head": "2  Score every ward",
             "body": "Rain + river + soil wetness + vulnerability → 0–100, 3-hourly horizon."},
            {"icon": "bot", "head": "3  Agents decide and draft",
             "body": "Monitor → Alert drafter → Evacuation planner → SitRep, all logged."},
            {"icon": "shield-check", "head": "4  Guard and approve",
             "body": "Guardrails check every draft; an officer approves before any send."},
            {"icon": "smartphone", "head": "5  Reach citizens",
             "body": "SMS / WhatsApp (simulated) + an offline citizen page with the nearest shelter."},
        ],
        "caption": "Guwahati in the demo replay: 72 h risk horizon, rainfall and Brahmaputra gauge.",
    }


def who(tag=None, title_="Who it's for"):
    return {
        "layout": "cards", "kicker": "Users", "title": title_, "tag": tag, "cols": 4, "body_size": 13,
        "cards": [
            {"icon": "user-check", "head": "District officers (DDMA)", "color": "0B1F3A",
             "body": ["See which wards turn red, and why", "Approve alerts in 5 languages", "One-click SitRep PDF"]},
            {"icon": "smartphone", "head": "Citizens in flood-prone wards", "color": TEAL_HEX(),
             "body": ["Personal risk + what to do now", "Nearest shelter and route", "Works on low-end, offline phones"]},
            {"icon": "siren", "head": "Responders + NGOs", "color": "D64545",
             "body": ["Shelters and hospitals near hotspots", "Shared situation picture", "Agent log for handovers"]},
            {"icon": "globe", "head": "SDMAs and smaller cities", "color": "5B4DB7",
             "body": ["No licence or API cost", "Runs on a laptop or one server", "Add a city by configuration"]},
        ],
        "callout": "Primary user: the district officer who must decide fast. Everyone else benefits from that decision.",
        "notes": "Primary user: district officer. Secondary: citizens.",
    }


def plan(tag=None, title_="Execution and build plan"):
    return {
        "layout": "plan", "kicker": "Execution", "title": title_, "tag": tag,
        "phases": [
            {"head": "Data + risk engine", "status": "done",
             "items": ["Open-Meteo + GloFAS adapters, cache", "12 cities, 96 wards, shelters", "Monotone score, unit tests"]},
            {"head": "Agents + guardrails", "status": "done",
             "items": ["Own ReAct loop on Ollama", "4 agents, rules fallback", "Approval gate, step log"]},
            {"head": "PWA + demo replay", "status": "done",
             "items": ["Dashboard, ward drill-down", "Admin + citizen views", "Offline, GitHub Pages demo"]},
            {"head": "Validate with a district", "status": "next",
             "items": ["Real ward boundaries", "Officer feedback on alerts", "Backtest on recorded floods"]},
            {"head": "Scale", "status": "next",
             "items": ["SMS gateway / CAP feed", "More languages", "More cities by config"]},
        ],
        "callout": "Built and demoable today: one command (docker compose up) or the static demo link.",
    }


def team(note=None):
    return {
        "layout": "team", "kicker": "Team", "title": "Team JalRakshak",
        "members": [
            {"initials": "MZ", "name": "Madhav Zanwar", "role": "Backend, risk engine, AI agents",
             "owns": ["FastAPI + data adapters", "Risk formula + LightGBM backtest", "ReAct agents on Ollama"]},
            {"initials": "DP", "name": "Divyani Papalkar", "role": "Frontend, UX, multilingual content",
             "owns": ["React PWA: dashboard, admin, citizen", "Alert templates in 5 languages", "Demo + pitch"]},
        ],
        "org": COLLEGE,
        "note": note or f"Code: {GITHUB}   ·   Live demo: {DEMO_URL}",
    }


def closing(body="Open data, a transparent score, AI agents that draft, and a human who decides."):
    return {"layout": "closing", "kicker": "Thank you", "title": "JalRakshak: warnings people can act on",
            "body": body,
            "links": [("git-branch", "GitHub", GITHUB), ("globe", "Live demo", DEMO_URL),
                      ("rocket", "Run locally", "git clone … && docker compose up")]}


# ------------------------------------------------------------------ kits
KITS = {
    "khacks-4.0": {
        "event_short": "K! Hacks 4.0", "event_long": "K! Hacks 4.0", "track": "Disaster Management · Agentic AI",
        "platform": "Unstop", "prize": "₹6 lakh prize pool",
    },
    "hacknova-2.0": {
        "event_short": "HackNova'27 2.0", "event_long": "HackNova'27 2.0", "track": "ResQTech · Disaster Resilience",
        "platform": "Unstop", "prize": "₹1.45 lakh",
    },
    "vytron-26": {
        "event_short": "VYTRON'26", "event_long": "VYTRON'26 · Round 1", "track": "Online hackathon",
        "platform": "Unstop", "prize": "₹1 lakh",
    },
    "clash-of-commits": {
        "event_short": "Clash of Commits", "event_long": "Clash of Commits", "track": "AI & Machine Learning",
        "platform": "Devfolio", "prize": "₹1 lakh",
    },
    "hacktopia-pune-2026": {
        "event_short": "Hacktopia Pune 2026", "event_long": "Hacktopia Pune 2026", "track": "Round 1 · Idea + prototype",
        "platform": "Unstop", "prize": "₹1 lakh+",
    },
}


def slides_for(kit_id: str) -> list[dict]:
    if kit_id == "khacks-4.0":
        return [
            title(subtitle="Agentic AI for flood early warning and response in India"),
            problem(),
            solution(agentic_first=True),
            agents(title_="Agentic AI: four agents, one local open LLM"),
            alerts(),
            demo(),
            architecture(),
            ml(title_="Transparent score first, honest ML second"),
            impact(title_="Impact and feasibility"),
            team(note=f"Code: {GITHUB}  ·  Live demo: {DEMO_URL}  ·  Next: pilot with one district control room"),
        ]
    if kit_id == "hacknova-2.0":
        return [
            title(subtitle="ResQTech: agentic flood early warning and response for India"),
            problem(),
            solution(),
            methodology(),
            risk_formula(),
            agents(),
            demo(),
            alerts(),
            architecture(),
            impact(),
            tech_stack(),
            team(),
            closing(),
        ]
    if kit_id == "vytron-26":
        return [
            title(),
            problem(),
            solution(),
            agents(),
            demo(),
            alerts(),
            architecture(),
            ml(),
            impact(),
            tech_stack(),
            team(),
            closing(),
        ]
    if kit_id == "clash-of-commits":
        ts = tech_stack()
        stack_split = {
            "layout": "split", "kicker": "Tech stack + architecture", "title": "Tech stack: open source end to end",
            "image": "architecture", "text_w": 4.3, "size": 13,
            "rows": [
                {"icon": "satellite", "head": "Data", "body": "Open-Meteo, GloFAS v4, ERA5, OSM, OSRM (no keys)"},
                {"icon": "server", "head": "Backend", "body": "Python 3.13, FastAPI, Pydantic v2, httpx, cache"},
                {"icon": "brain-circuit", "head": "ML + agents", "body": "LightGBM · Ollama Qwen2.5 3B · own ReAct loop"},
                {"icon": "laptop", "head": "Frontend", "body": "React 18, Vite, TS, Leaflet, Recharts, PWA"},
                {"icon": "boxes", "head": "Deploy", "body": "docker compose; static demo on GitHub Pages"},
            ],
            "caption": "Data → adapters + cache → risk engine (+LightGBM) → agents → FastAPI → React PWA",
            "notes": ts["notes"],
        }
        return [
            title(subtitle="ML + agentic LLM for flood early warning in India"),
            problem(),
            who(),
            solution(agentic_first=True),
            ml(title_="ML + agents: what the models do, and how well"),
            stack_split,
            plan(),
            demo(),
            impact(),
            team(),
        ]
    if kit_id == "hacktopia-pune-2026":
        return [
            title(),
            problem(tag="Problem relevance"),
            solution(tag="Innovation"),
            agents(tag=["Innovation", "Technical"]),
            ml(tag="Technical implementation", title_="Transparent score + honest ML backtest"),
            architecture(tag=["Technical", "Scalability"]),
            demo(tag="User impact"),
            alerts(tag="User impact"),
            feasibility(),
            scalability(),
            impact(tag="User impact"),
            criteria(),
            team(),
            closing(),
        ]
    raise KeyError(kit_id)


def feasibility():
    return {
        "layout": "cards", "kicker": "Feasibility", "title": "Feasible today, on a laptop", "tag": "Feasibility",
        "cols": 3, "body_size": 13,
        "cards": [
            {"icon": "indian-rupee", "head": "₹0 to run", "body": "Free open data and open-source software. "
             "No paid API, no key, no cloud LLM bill."},
            {"icon": "laptop", "head": "Runs on one laptop", "body": "docker compose up starts API, web app and "
             "Ollama. A 3B model runs on CPU."},
            {"icon": "wifi-off", "head": "Works when networks fail", "body": "Cached data with a visible stale "
             "flag; the PWA works offline; rules fallback without the LLM."},
            {"icon": "shield-check", "head": "Safe by design", "body": "Human approval before any send, "
             "guardrails on every draft, dispatch simulated in the prototype."},
            {"icon": "triangle-alert", "head": "Known limits", "body": "Synthetic ward data and proxy flood "
             "labels; a pilot needs real ward maps and an SMS gateway."},
            {"icon": "check", "head": "Already built", "body": "Working prototype, tests, demo replay, video and "
             "a public demo link."},
        ],
    }


def scalability():
    return {
        "layout": "cards", "kicker": "Scalability", "title": "From 12 cities to every flood-prone district",
        "tag": "Scalability", "cols": 3, "body_size": 13,
        "cards": [
            {"icon": "globe", "head": "Add a city by config", "body": "City, wards, gauge cell and shelters are "
             "data. GloFAS and Open-Meteo already cover all of India."},
            {"icon": "languages", "head": "Add a language", "body": "New template set + script check. Same "
             "guardrails, same approval flow."},
            {"icon": "radio-tower", "head": "Plug into real channels", "body": "Dispatch is one interface: swap the "
             "simulator for an SMS gateway or a CAP alert feed."},
            {"icon": "server", "head": "Light infrastructure", "body": "Stateless API plus a file cache; one small "
             "server per state, LLM optional."},
            {"icon": "brain-circuit", "head": "Swap the model", "body": "Any Ollama model works; a bigger model "
             "improves drafting without changing code."},
            {"icon": "git-branch", "head": "Open source (MIT)", "body": "SDMAs, NGOs and students can audit, fork "
             "and extend it."},
        ],
    }


def criteria():
    return {
        "layout": "criteria", "kicker": "Judging criteria", "title": "Where each judging criterion is addressed",
        "tag": "Presentation",
        "items": [
            {"icon": "lightbulb", "criterion": "Innovation", "evidence": "Agents on a local open LLM that draft "
             "5-language alerts with guardrails and a human gate (slides 3–4)"},
            {"icon": "target", "criterion": "Problem relevance", "evidence": "Floods: 1.09 lakh deaths since 1953; "
             "22 lakh affected in Assam on one day in 2022 (slide 2)"},
            {"icon": "cpu", "criterion": "Technical implementation", "evidence": "Monotone tested risk score, "
             "LightGBM time-split backtest, own ReAct loop (slides 4–6)"},
            {"icon": "check", "criterion": "Feasibility", "evidence": "₹0 run cost, one laptop, offline, "
             "working prototype today (slide 9)"},
            {"icon": "trending-up", "criterion": "Scalability", "evidence": "Cities, languages and channels are "
             "configuration (slides 6, 10)"},
            {"icon": "heart-handshake", "criterion": "User impact", "evidence": "Ward-level local-language "
             "alerts, nearest shelter, low-end phones (slides 7, 8, 11)"},
            {"icon": "award", "criterion": "Presentation", "evidence": "Clear story, live demo link, "
             "3-minute video, open repository with docs"},
            {"icon": "globe", "criterion": "Try it yourself", "evidence": DEMO_URL + " (no install, works "
             "offline after first load)"},
        ],
    }
