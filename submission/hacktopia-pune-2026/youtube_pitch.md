# YouTube pitch — upload details

Video file: `submission/JalRakshak_demo.mp4` · Visibility: unlisted or public as the rules require · Category: Science & Technology

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

Live demo: https://madhavzanwar.github.io/Jal-rakshak/
Code (MIT): https://github.com/madhavzanwar/Jal-rakshak
Team: Madhav Zanwar, Divyani Papalkar · PCCoE Pune

Data and tools: Open-Meteo, GloFAS (Copernicus), OpenStreetMap, OSRM, Leaflet, Ollama, Qwen2.5, FastAPI, React,
Recharts, LightGBM, Piper TTS.

Chapters
0:00 Title card
0:14 The problem
0:26 Command centre
0:42 Guwahati
1:01 Ward drill-down
1:10 The flood builds
1:17 Agents at work
1:45 Human approval
1:59 Situation report
2:05 Citizen view
2:18 How it's built
2:29 Close

## Tags
JalRakshak, flood early warning, flood forecasting, disaster management, agentic AI, AI agents, Ollama, Qwen2.5,
LightGBM, GloFAS, Open-Meteo, OpenStreetMap, India floods, Assam floods, multilingual alerts, Hindi, Marathi,
Tamil, Bengali, FastAPI, React, PWA, hackathon, Hacktopia Pune 2026, PCCoE

## Chapters (paste into the description; YouTube needs the first at 0:00)
0:00 Title card
0:14 The problem
0:26 Command centre
0:42 Guwahati
1:01 Ward drill-down
1:10 The flood builds
1:17 Agents at work
1:45 Human approval
1:59 Situation report
2:05 Citizen view
2:18 How it's built
2:29 Close

Chapter starts follow the scenes in `docs/DEMO_SCRIPT.md`. They are computed from the final video's scene
timings when available, otherwise from the video duration (or narration length) proportional to each scene's
narration. Check them once against the uploaded video and nudge by a second or two if needed.

## Thumbnail
Use the architecture diagram (`docs/img/architecture.png`) or the dashboard screenshot
(`docs/img/screens/dashboard.png`) with the text "Flood alerts people can act on".
