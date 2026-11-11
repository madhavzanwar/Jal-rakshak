# JalRakshak: agentic flood early warning and response for India

**Team:** Madhav Zanwar, Divyani Papalkar (Pimpri Chinchwad College of Engineering (PCCoE), Pune)  
**Event:** Hacktopia Pune 2026 · **Track:** Round 1 · Idea + prototype  
**Code:** https://github.com/madhavzanwar/Jal-rakshak · **Live demo:** https://madhavzanwar.github.io/Jal-rakshak/

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
