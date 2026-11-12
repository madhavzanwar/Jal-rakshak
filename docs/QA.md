# QA report

Run on 2026-11-12 in a clean Linux container (4 vCPU, no GPU, Python 3.13, Node 22, Ollama 0.40 with `qwen2.5:3b`).
Re-run everything with the commands at the bottom.

## Summary

| Check | Command | Result |
|---|---|---|
| Backend lint | `make lint` (ruff check + ruff format --check) | ✅ All checks passed · 51 files formatted |
| Backend typecheck | `make typecheck` (mypy, `disallow_untyped_defs`) | ✅ no issues in 40 source files |
| Backend tests | `JR_LLM_PROVIDER=rules make test` | ✅ **137 passed** (33.5 s) |
| Frontend lint | `npm run lint` (ESLint + typescript-eslint) | ✅ 0 problems |
| Frontend typecheck | `npm run typecheck` (`tsc --noEmit`, strict) | ✅ |
| Frontend unit tests | `npm test` (Vitest) | ✅ **38 passed** in 7 files |
| Frontend builds | `npm run build`, `npm run build:demo` | ✅ |
| E2E | `npm run e2e` (Playwright, Chromium, demo build) | ✅ **4 passed** (32.9 s) |
| Docker image | `docker build .` (root multi-stage) | ✅ built; container serves PWA at `/` and API at `/api` |
| Compose file | `docker compose config` | ✅ valid |
| Live end-to-end with local LLM | container → host Ollama, `POST /api/agents/run {"city_id":"guwahati"}` | ✅ 36 logged steps, provider `ollama/qwen2.5:3b`, 2 min 26 s on CPU |

## Backend test breakdown (137)

| File | Tests | Covers |
|---|---|---|
| `tests/test_scoring.py` | 43 | IMD-anchored rain curve, river component, level cut-offs (29.99 / 30 / 54.99 / 55 / 74.99 / 75), hard river floors, monotonicity property grid, zero-rain / no-gauge edge cases, horizon windows, explanations |
| `tests/test_guards.py` | 57 | SMS length (160 GSM-7 / 134 Unicode), script check per language (Devanagari, Tamil, Bengali), hallucinated-number detection, must contain 112, level-word consistency, no URLs, all five languages present |
| `tests/test_agents.py` | 13 | ReAct loop with rules provider, malformed tool-call recovery, monitor policy (must alert ≥ orange, never on green), drafter fallback to vetted template, evacuation planner, sitrep |
| `tests/test_adapters.py` | 11 | Cache TTL and stale fallback, Open-Meteo parsing, **OSRM failure → straight-line fallback**, Nominatim caching / rate limit |
| `tests/test_api.py` | 5 | Endpoint smoke tests, **approval gate**: 409 on failed guards, reject, edit re-runs guards, approve → `sent` with simulated dispatch log |
| `tests/test_ml.py` | 8 | Predictor returns `None` when model absent, output ∈ [0,1], monotone in discharge ratio |

## E2E (Playwright)

```
✓ dashboard → Guwahati → run agents → drafted alert → admin approve → sent (6.9s)
✓ ward drill-down shows factor breakdown and nearest shelters (1.4s)
✓ admin SMS editor counts characters and segments (5.7s)
✓ citizen view is light: no map/chart/pdf chunks, emergency numbers are tel: links (1.1s)
4 passed (32.9s)
```

## Bundle (low-end phone budget)

| Chunk | Size | gzip |
|---|---|---|
| Citizen route | 17.4 kB | 6.4 kB |
| Shared entry (React, router, zod) | 317 kB | 101.8 kB |
| Map / charts / PDF | lazy-loaded only on dashboard, agents and admin pages | |

The PWA precaches the app shell and the demo scenario, and works offline after the first visit (checked for the Guwahati dashboard and the citizen page).

## Live verification against real services

- `GET /api/health` → `{"status":"ok","llm":{"provider":"ollama","model":"qwen2.5:3b","available":true}}`
- `GET /api/cities` → 12 cities with live Open-Meteo rainfall and GloFAS discharge, plus the LightGBM `ml_probability`. All cities were green on 12 Nov (post-monsoon), so the live runs correctly drafted no alert.
- `POST /api/agents/run` (Guwahati, Ollama): the monitor called `get_city_risk`, `get_gauge_status` and `get_ward_risks`, then passed the policy guard. Decision: no alert, green, score 14.1. Brahmaputra at 3,680 m³/s against a 32,960 m³/s warning level.
- Alert endpoints were tested with a synthetic flood run: tampered edit → 3 guards fail → approve returns 409; clean alert → `sent` with 10 simulated dispatch entries; sitrep PDF → 200.
- Demo scenario: 24 frames, 5 agent runs recorded with real `ollama/qwen2.5:3b`, all 7 guards pass on every alert. It validates against both the Pydantic models and the zod schemas.

## Known issues / notes

- The sandbox needed its proxy CA injected for `pip` and `npm` inside `docker build`. That was done with a throwaway Dockerfile variant; the committed Dockerfile is unchanged and builds normally on a regular network.
- Agent runs on Ollama take 40–150 s on a 4-core CPU. The UI streams steps, and the rules provider responds instantly.
- One recorded monitor reasoning included an unsupported phrase ("high population density"). The decision itself comes from a deterministic policy guard, and alert text is guard-checked, which is why the gate exists.
- Starlette warns that `httpx` in TestClient is deprecated. This is harmless.

## Reproduce

```bash
cd backend && make install && make lint typecheck && JR_LLM_PROVIDER=rules make test
cd frontend && npm ci && npm run lint && npm run typecheck && npm test && npm run build:demo && npm run e2e
docker compose up --build
```
