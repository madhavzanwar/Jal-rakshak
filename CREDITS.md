# Credits

JalRakshak is original code (MIT) built on the shoulders of these open projects and open data.

## Prior work we studied (ideas and patterns; **no code copied**)

| Project | Licence | What we learned |
|---|---|---|
| [FloodGuard — Hyperlocal Intelligence for Flash Flood Prediction](https://github.com/ABDULMUNAFZ/Hyperlocal-Intelligence-for-Flash-Flood-Prediction-Risk--Response) (SIH 2026) | Apache-2.0 | splitting the citizen app from the responder console, the digital-twin framing, ward-level risk |
| [PredictAid — AIDisasterManagement](https://github.com/jaidevxr/AIDisasterManagement) ([live](https://predictaid.vercel.app)) | MIT | India-wide early-warning dashboard layout, map legends, alert cards |
| [RescueMap-AI](https://github.com/m-bilal-ahmed/RescueMap-AI) ([site](https://rescuemap-ai.org/)) | no licence published, so ideas only | shelters and rescue routing on a map |

## Data and services (free, no keys)

- **Open-Meteo**: [Forecast](https://open-meteo.com/en/docs), [Flood (GloFAS)](https://open-meteo.com/en/docs/flood-api) and [Historical/ERA5](https://open-meteo.com/en/docs/historical-weather-api) APIs. Data is CC BY 4.0. Source code: [open-meteo/open-meteo](https://github.com/open-meteo/open-meteo) (AGPL-3.0, used as a service).
- **Copernicus Emergency Management Service, GloFAS** river discharge (via Open-Meteo).
- **ECMWF ERA5** reanalysis (via Open-Meteo), used for ML training.
- **OpenStreetMap** map tiles and data, © OpenStreetMap contributors (ODbL).
- **Nominatim** geocoding (usage policy respected: cached, 1 request/s, identifying User-Agent).
- **OSRM** ([Project-OSRM/osrm-backend](https://github.com/Project-OSRM/osrm-backend), BSD-2) public demo routing server.
- IMD rainfall intensity categories and NDMA flood do's and don'ts, used as public guidance for thresholds and advice text.

## AI and ML

- [Ollama](https://github.com/ollama/ollama) (MIT), the local LLM runtime.
- [Qwen2.5-3B-Instruct](https://huggingface.co/Qwen/Qwen2.5-3B-Instruct) (Qwen Research licence), the default local model.
- [LightGBM](https://github.com/microsoft/LightGBM) (MIT), [scikit-learn](https://scikit-learn.org) (BSD-3), [pandas](https://pandas.pydata.org) (BSD-3), [NumPy](https://numpy.org) (BSD-3), [matplotlib](https://matplotlib.org) (PSF-style).

## Backend

[FastAPI](https://github.com/fastapi/fastapi) (MIT), [Uvicorn](https://www.uvicorn.org) (BSD-3), [Pydantic](https://github.com/pydantic/pydantic) (MIT), [httpx](https://github.com/encode/httpx) (BSD-3), [ReportLab](https://www.reportlab.com/opensource/) (BSD), [pytest](https://pytest.org) (MIT), [respx](https://github.com/lundberg/respx) (BSD-3), [Ruff](https://github.com/astral-sh/ruff) (MIT), [mypy](https://github.com/python/mypy) (MIT).

## Frontend

[React](https://react.dev) (MIT), [Vite](https://vitejs.dev) (MIT), [TypeScript](https://www.typescriptlang.org) (Apache-2.0), [Tailwind CSS](https://tailwindcss.com) (MIT), [Leaflet](https://github.com/Leaflet/Leaflet) (BSD-2), [react-leaflet](https://github.com/PaulLeCam/react-leaflet) (Hippocratic-2.1), [Recharts](https://recharts.org) (MIT), [zod](https://zod.dev) (MIT), [React Router](https://reactrouter.com) (MIT), [vite-plugin-pwa / Workbox](https://vite-pwa-org.netlify.app) (MIT), [lucide-react](https://lucide.dev) (ISC), [jsPDF](https://github.com/parallax/jsPDF) (MIT), [Vitest](https://vitest.dev) (MIT), [Testing Library](https://testing-library.com) (MIT), [ESLint](https://eslint.org) (MIT). Further details: [frontend/CREDITS_FRONTEND.md](frontend/CREDITS_FRONTEND.md).

## Tooling for the video and decks

[Playwright](https://github.com/microsoft/playwright) (Apache-2.0), [Piper TTS — OHF-Voice/piper1-gpl](https://github.com/OHF-Voice/piper1-gpl) (GPL-3.0, used as an offline tool; not linked into the app), voice `en_US-lessac-medium` from [rhasspy/piper-voices](https://huggingface.co/rhasspy/piper-voices), [FFmpeg](https://ffmpeg.org) (LGPL/GPL, tool), [python-pptx](https://github.com/scanny/python-pptx) (MIT), [PyMuPDF](https://github.com/pymupdf/PyMuPDF) (AGPL, tool), LibreOffice (MPL-2.0, rendering), [Inter](https://rsms.me/inter/) and [Noto](https://fonts.google.com/noto) fonts (OFL).
