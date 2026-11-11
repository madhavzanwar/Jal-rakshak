# Clash of Commits — what to upload where

Platform: **Devfolio** · Prize: ₹1 lakh · Track/theme: **AI & Machine Learning**

All files are in `submission/clash-of-commits/`. Regenerate everything with `scripts/decks/build_all.sh`.

## Files in this kit

| File | What it is |
|---|---|
| `JalRakshak_ClashOfCommits.pptx` | Pitch deck, 10 slides, 16:9 |
| `_render/JalRakshak_ClashOfCommits.pdf` | PDF export of the deck (generated locally by build_all.sh, gitignored; upload this where a PDF is required) |
| `abstract.md` / `abstract.pdf` | One-page abstract |

## Devfolio project form (Clash of Commits)

The deck has **exactly 10 slides** (checked by the build): title, problem, who it's for, solution, ML + agents,
tech stack + architecture, execution & build plan, demo, impact, team.

| Devfolio field | What to enter / upload |
|---|---|
| Track | **AI & Machine Learning** |
| Project name | JalRakshak |
| Tagline | Agentic AI flood early warning for India: open data, local LLM, 5 languages |
| The problem it solves | India's flood forecasts rarely become ward-level, local-language instructions in time. JalRakshak scores flood risk for every ward for the next 72 hours from open rainfall and river forecasts, and AI agents draft 5-language alerts, evacuation routes and a situation report for an officer to approve. Citizens get a light offline page with their risk and nearest shelter. |
| Challenges we ran into | Getting a 3B local model to call tools reliably (own ReAct loop with strict JSON and a rules fallback); stopping hallucinated numbers (guardrails compare every number with tool outputs); Indic SMS length and script checks; building honest flood labels from reanalysis and evaluating LightGBM with a time split instead of a random split. |
| Technologies used (tags) | Python, FastAPI, Pydantic, LightGBM, pandas, Ollama, Qwen2.5, React, TypeScript, Vite, Leaflet, Recharts, OpenStreetMap, OSRM, Open-Meteo, GloFAS, Docker, Playwright |
| Links | GitHub: https://github.com/madhavzanwar/Jal-rakshak · Demo: https://madhavzanwar.github.io/Jal-rakshak/ |
| Video demo | YouTube link: <paste after upload> (file: `submission/JalRakshak_demo.mp4`) |
| Pictures | Upload `docs/img/screens/*.png` and `docs/img/architecture.png` |
| Presentation / deck | `JalRakshak_ClashOfCommits.pptx` (or `_render/JalRakshak_ClashOfCommits.pdf` if Devfolio asks for PDF) |
| Abstract (if asked) | `abstract.pdf` |

## Links (paste exactly)

| Field | Value |
|---|---|
| GitHub repository | https://github.com/madhavzanwar/Jal-rakshak |
| Live demo (static replay, no install) | https://madhavzanwar.github.io/Jal-rakshak/ |
| Demo video file | `submission/JalRakshak_demo.mp4` |
| YouTube link | <paste after upload> |

## Team details

| Field | Value |
|---|---|
| Team name | JalRakshak |
| Members | Madhav Zanwar, Divyani Papalkar |
| Institute | Pimpri Chinchwad College of Engineering (PCCoE), Pune |
| Project title | JalRakshak: agentic flood early warning and response for India |
| Tagline | Agentic AI flood early warning for India: open data, local LLM, 5 languages |
| Short description (≈300 chars) | JalRakshak turns free rainfall and river forecasts into ward-level flood risk for 12 Indian cities, then local-LLM agents draft 5-language SMS/WhatsApp alerts, evacuation routes and a situation report for an officer to approve. Zero paid services; runs on a laptop. |

## Before you press submit

- [ ] Open the deck in PowerPoint / Google Slides once and check fonts (Inter; Noto Sans for Indic text). If
      Inter is missing, install it or export the PDF from `_render/` instead.
- [ ] Upload `submission/JalRakshak_demo.mp4` to YouTube (unlisted is fine unless the rules say public) and paste the link above
      and into every "video" field.
- [ ] Check the live demo link opens on a phone.
- [ ] Keep the GitHub repository public until results are announced.
