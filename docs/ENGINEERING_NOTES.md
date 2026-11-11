# Engineering notes (for contributors and agents)

- Repo layout: `backend/` (Python 3.13, FastAPI, package `jalrakshak`), `frontend/` (React+Vite+TS),
  `docs/`, `scripts/` (repo-level tooling: demo video, decks), `submission/` (hackathon kits).
- Contract: `docs/CONTRACT.md` is the source of truth for every JSON shape.
- Local LLM: Ollama at `http://127.0.0.1:11434`, default model `qwen2.5:3b` (env `JR_LLM_MODEL`).
  Binary at `/usr/local/bin/ollama`; start with `ollama serve` if not running.
- Git identity is preconfigured in the repo (author Madhav Zanwar); do not change git config.
- Commits: small, conventional (`feat(backend): ...`). Only `git add` your own paths, never `git add -A`.
  If `.git/index.lock` exists, wait a few seconds and retry. Commit trailer:
  `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>` and
  `Claude-Session: https://claude.ai/code/session_01Jtz5fFPYQbeSDczZShHmBq`.
- Reference repos (study only, credit in CREDITS.md):
  `/home/user/abdulmunafz/hyperlocal-intelligence-for-flash-flood-prediction-risk--response` (FloodGuard, Apache-2.0),
  `/home/user/jaidevxr/aidisastermanagement` (PredictAid, MIT),
  `/home/user/m-bilal-ahmed/rescuemap-ai` (RescueMap-AI, no licence → ideas only, no code copying).
