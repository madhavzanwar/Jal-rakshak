# JalRakshak: agentic flood early warning and response for India

**Team:** Madhav Zanwar, Divyani Papalkar, Pimpri Chinchwad College of Engineering (PCCoE), Pune  
**GitHub:** https://github.com/madhavzanwar/Jal-rakshak  
**Live demo:** https://madhavzanwar.github.io/Jal-rakshak/

Floods are India's most frequent large disaster. Roughly 40 million hectares, about 12% of the country, is
flood-prone, and floods and heavy rain killed 1,09,374 people between 1953 and 2018 according to Parliament's
Standing Committee on Water Resources. In June 2022 alone, about 22 lakh people in 28 Assam districts were
affected. Forecasts already exist; what is missing is the last mile: turning rainfall and river forecasts into
ward-level, local-language instructions that a district officer can trust and a citizen can act on in time.

JalRakshak is an agentic early-warning and response platform built only on free, open data and open-source
software. It pulls Open-Meteo rainfall forecasts and GloFAS river-discharge forecasts for 12
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
