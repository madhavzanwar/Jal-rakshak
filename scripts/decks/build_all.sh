#!/usr/bin/env bash
# Regenerate every hackathon submission kit: architecture diagram, decks, abstracts, READMEs,
# then render each deck to PNG/PDF in submission/<kit>/_render/ (gitignored) for review.
set -euo pipefail
cd "$(dirname "$0")/../.."
PY=${PY:-/opt/tools/bin/python}

"$PY" scripts/decks/architecture.py
"$PY" scripts/decks/build.py "$@"
for deck in submission/*/*.pptx; do
  "$PY" scripts/decks/render.py "$deck"
done
"$PY" - <<'PYEOF'
from pptx import Presentation
n = len(Presentation("submission/clash-of-commits/JalRakshak_ClashOfCommits.pptx").slides)
assert n == 10, f"Clash of Commits deck must have exactly 10 slides, has {n}"
print("Clash of Commits slide count OK:", n)
PYEOF
