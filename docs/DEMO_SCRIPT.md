# JalRakshak — demo video script (2:30–3:00)

The automated recorder (`scripts/video/`) drives the app in **demo mode** through these scenes.
Each scene's `Narration` is spoken by Piper TTS and burned in as English subtitles.
Target: ~400 words of narration ≈ 2 min 45 s.

---

## Scene 1 — Title card
**Visual:** Title card: "JalRakshak · Agentic flood early warning for India" · team names.
**Narration:** Every monsoon, floods in India take lives that a few hours of warning could have saved. This is JalRakshak, an agentic early-warning and response platform built only on free, open data and a local language model.

## Scene 2 — The problem
**Visual:** Title card: "Warnings exist. Last-mile action doesn't." with three short facts.
**Narration:** River and rainfall forecasts already exist, but they rarely become clear, local, multilingual instructions in time. District officers are overloaded, and citizens get warnings they cannot act on.

## Scene 3 — Command centre
**Visual:** Dashboard, India map, twelve cities ranked by risk, demo replay bar.
**Narration:** The command centre watches twelve flood-prone cities. For each one we pull Open-Meteo rainfall forecasts and GloFAS river discharge, and compute a transparent zero-to-one-hundred risk score for the next seventy-two hours. This is a synthetic replay inspired by Assam's monsoon floods.

## Scene 4 — Guwahati
**Visual:** Select Guwahati; map flies in; risk gauge, horizon chart, rainfall chart, Brahmaputra gauge card.
**Narration:** Let's open Guwahati. The score combines heavy-rain categories from the India Meteorological Department, the forecast Brahmaputra discharge against danger thresholds derived from forty years of river data, soil wetness from recent rain, and ward vulnerability. Every factor is shown, so an officer can see exactly why.

## Scene 5 — Ward drill-down
**Visual:** Click a red ward zone; side panel with factor bars and nearest shelters.
**Narration:** We drill down to ward level. Low-lying wards near the river turn red first, with the nearest shelters and hospitals already mapped.

## Scene 6 — The flood builds
**Visual:** Replay advances; markers and wards shift from yellow to orange to red.
**Narration:** As the replay moves forward, rain intensifies and the river crosses its danger mark. The risk turns red.

## Scene 7 — Agents at work
**Visual:** Click "Run response agents"; agent timeline streams Monitor, Alert drafter, Evacuation planner and SitRep steps with tool calls and guard checks.
**Narration:** Now the agents take over. A monitor agent, running on a small open model through Ollama, reasons over the data and decides an alert is needed. The drafter writes SMS and WhatsApp messages. Guardrails check length, script, and that every number matches verified data. The evacuation planner routes people to safe shelters, and a situation report is drafted. Every step is logged with its reasoning and inputs.

## Scene 8 — Human approval
**Visual:** Admin view; switch language tabs English, Hindi, Marathi, Tamil, Bengali; SMS counter; type reviewer name; Approve & send; status "sent".
**Narration:** Nothing goes out without a human. The officer reviews the alert in English, Hindi, Marathi, Tamil and Bengali, edits if needed, and approves. Only then is it dispatched, and that decision is logged too.

## Scene 9 — Situation report
**Visual:** Situation report panel; Export PDF.
**Narration:** The district officer gets a one-click situation report as a PDF, ready for the control room.

## Scene 10 — Citizen view
**Visual:** Phone-sized citizen page; search "Beltola"; personal risk, what to do now, nearest shelter, emergency numbers.
**Narration:** Citizens get a light page that works on low-end phones and offline. Enter a place to see your risk, what to do now, your nearest shelter, and emergency numbers like one-one-two.

## Scene 11 — How it's built
**Visual:** Title card with the architecture diagram.
**Narration:** It runs on a laptop with one command, needs no paid services or keys, and uses open source throughout: Open-Meteo, OpenStreetMap, Leaflet, OSRM, Ollama, FastAPI, React and LightGBM.

## Scene 12 — Close
**Visual:** Closing card: "JalRakshak — warnings people can act on." GitHub URL and team.
**Narration:** JalRakshak turns open forecasts into warnings people can act on. Built by Madhav Zanwar and Divyani Papalkar from PCCoE Pune.
