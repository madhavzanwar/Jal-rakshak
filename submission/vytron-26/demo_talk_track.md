# VYTRON'26 Round 3: online demo talk track (about 5 minutes)

**Presenters:** Madhav Zanwar (drives the screen), Divyani Papalkar (narrates; takes over for Admin and Citizen).
**Setup (10 minutes before the call):**

- Tab 1: live demo, https://madhavzanwar.github.io/Jal-rakshak/ (demo replay mode; needs no backend).
- Tab 2 (optional): local full stack with `docker compose up` → http://localhost:8080, to show the real Ollama
  agents. If Ollama is slow on the call, stay on Tab 1, because the replay shows the same flow.
- Tab 3: `docs/img/architecture.png`.
- Fallback: `submission/JalRakshak_demo.mp4` open in a player, in case screen share or network fails.
- Browser zoom 110%, notifications off, close other tabs. Share the **browser tab only**.

| Time | Screen / click | What we say |
|---|---|---|
| 0:00–0:30 | Dashboard (`/`), India map visible | "Every monsoon, floods take lives that a few hours of clear warning could save. Forecasts already exist; what is missing is the last mile: ward-level, local-language instructions that an officer approves and a citizen can act on. JalRakshak does that with free data and a local LLM." |
| 0:30–1:10 | Point at the city list ranked by risk; point at the **demo replay bar** | "We watch 12 flood-prone cities. For each we pull Open-Meteo rainfall and GloFAS river-discharge forecasts and compute a 0–100 risk score for the next 72 hours. This is a replay of a synthetic flood inspired by Assam's monsoon, so you can see the whole flow in five minutes." |
| 1:10–1:50 | Click **Guwahati**: map flies in; show the risk gauge, 72 h horizon chart, rainfall chart, Brahmaputra gauge card | "The score is transparent: IMD heavy-rain categories, forecast Brahmaputra discharge against danger levels from 40 years of GloFAS reanalysis, last week's rain, and ward vulnerability. Every factor is on screen, so nothing is a black box." |
| 1:50–2:15 | Click a **red ward circle**: ward panel with factor bars and nearest shelters | "Low-lying wards near the river turn red first. The officer sees why, and the nearest shelters and hospitals are already mapped." |
| 2:15–2:30 | Press **play / step** on the replay bar until wards go orange → red | "As the replay advances, rain intensifies and the river crosses danger. Risk turns red." |
| 2:30–3:20 | Click **Run response agents** → Agents page timeline streams | "Now the agents take over: the Monitor decides an alert is needed; the Alert drafter writes SMS and WhatsApp in five languages; the Evacuation planner routes people to shelters; SitRep writes the officer's report. Every step shows its reasoning, tool call and inputs. Guardrails check length, script, that every number matches the data, and that 112 is included. It runs on Qwen2.5 3B through Ollama on a laptop, with a rules fallback." Expand one **tool_call** and one **guard** step. |
| 3:20–4:00 | **Admin** page: switch tabs English → हिन्दी → मराठी → தமிழ் → বাংলা; show SMS counter; type reviewer name; **Approve & send** → status *sent* | (Divyani) "Nothing goes out without a human. I review each language, can edit, and approve. Dispatch is simulated in the prototype and logged with who approved it and when." |
| 4:00–4:15 | Situation report panel → **Export PDF** | "The district officer gets a one-click situation report for the control room." |
| 4:15–4:40 | **Citizen** page at phone width (DevTools device mode, ~390 px); search **Beltola** | (Divyani) "Citizens get a light page that works on low-end phones and offline: your risk, what to do now, nearest shelter and route, emergency numbers like 112." |
| 4:40–5:00 | Architecture diagram tab | "All open source, zero paid services or keys, `docker compose up`. Code and live demo links are in our submission. Thank you; happy to take questions." |

If time runs short, skip the SitRep PDF (4:00–4:15) and the replay stepping (2:15–2:30).

---

## Q&A prep: 10 likely judge questions

1. **Why a local 3B model instead of GPT-4 or Gemini?**
   Privacy, zero cost and offline resilience: district control rooms can't depend on a paid cloud API during a
   flood. The LLM only reasons and picks tools; all numbers come from tools, and guardrails reject anything that
   doesn't match. A bigger Ollama model can be swapped in by changing one setting.

2. **What happens if the LLM hallucinates or is unavailable?**
   Guardrails check every draft: numbers must match tool outputs, the script must match the language, the SMS
   must fit, and 112 must be present. Failing drafts are replaced by vetted templates. If Ollama is down or
   slow, a deterministic rules engine runs the same pipeline. And a human approves before anything is sent.

3. **How accurate is the risk score? Did you validate it?**
   The score is deterministic and explainable, built on IMD rainfall categories and GloFAS danger thresholds.
   We also trained an optional LightGBM flood-day model on 1991–2024 GloFAS + ERA5 reanalysis and evaluated it
   with a time split (train on earlier years, test on later ones). We report those numbers as they are, in
   `docs/MODEL.md`. The labels are proxies from reanalysis, not official flood records, and we say so.

4. **Are the ward data and shelters real?**
   Ward names and approximate locations are real neighbourhoods; population, elevation, vulnerability and
   shelters are synthetic and clearly labelled. A pilot would load municipal ward boundaries and the district's
   shelter list, which is a data change, not a code change.

5. **How is this different from IMD / CWC warnings or Sachet?**
   Those publish forecasts and broadcast alerts. We sit on top of open forecasts and do the last mile: ward-level
   scoring, local-language drafts, nearest shelters, a situation report, and an approval workflow with an audit
   trail. JalRakshak could feed an official channel such as a CAP/Sachet-style system rather than replace it.

6. **Why these five languages?**
   English, Hindi, Marathi, Tamil and Bengali cover our pilot cities and about 64% of Indians by mother tongue
   (Census 2011). Adding a language means adding a vetted template set and a script check; guardrails and
   approval stay the same.

7. **Does it really work offline?**
   The PWA caches the app shell and last data; the citizen page loads offline after the first visit. The backend
   caches every source and serves last-known data with a visible "stale" flag when a source fails.

8. **How does it scale to more cities?**
   A city is configuration: centre, wards, a GloFAS grid cell and shelters. Open-Meteo and GloFAS already cover
   all of India. The API is light (file cache, no heavy database), so one small server per state is enough; the
   LLM is optional.

9. **Are SMS / WhatsApp messages actually sent?**
   Not in the prototype: dispatch is simulated and logged (channel, language, recipients estimate) to avoid
   spamming real numbers. Dispatch is one interface; production would plug in an SMS gateway or an official
   alerting channel after approval.

10. **What did you build yourselves versus reuse?**
    We built the adapters and cache, the risk engine, the ReAct agent loop and guardrails, the FastAPI service,
    the React PWA and the demo replay. We reuse open data (Open-Meteo, GloFAS, OSM) and open-source tools (Ollama,
    Qwen2.5, Leaflet, OSRM, LightGBM). Projects that inspired us, FloodGuard (SIH 2026) and PredictAid, are
    credited in the repository.

**If the demo breaks:** say "let me show the recorded run" and play `submission/JalRakshak_demo.mp4` from the
matching scene; keep talking over it using the table above.
