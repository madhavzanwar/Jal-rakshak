#!/usr/bin/env bash
# One-command demo video: build demo frontend -> serve -> TTS -> cards -> record -> assemble.
# Output: submission/JalRakshak_demo.mp4 + submission/JalRakshak_demo.srt
# Env: WORK (scratch dir, default /tmp/jr-video), PORT (4173), PIPER_VOICE, PIPER_LENGTH_SCALE,
#      SKIP_BUILD=1 to reuse frontend/dist, SKIP_RECORD=1 to re-assemble from an existing recording.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
HERE="$ROOT/scripts/video"
WORK="${WORK:-/tmp/jr-video}"
PORT="${PORT:-4173}"
PY="${PYTHON:-/opt/tools/bin/python}"
BASE_URL="http://localhost:$PORT/Jal-rakshak/"
mkdir -p "$WORK"

if [[ "${SKIP_RECORD:-0}" != 1 ]]; then
  if [[ "${SKIP_BUILD:-0}" != 1 ]]; then
    echo "== build demo frontend"
    (cd "$ROOT/frontend" && npm run build:demo >/dev/null)
  fi
  echo "== serve $BASE_URL"
  (cd "$ROOT/frontend" && exec npx vite preview --port "$PORT" --strictPort --base /Jal-rakshak/) >"$WORK/preview.log" 2>&1 &
  PREVIEW_PID=$!
  trap 'kill $PREVIEW_PID 2>/dev/null || true' EXIT
  for _ in $(seq 1 60); do curl -sf -o /dev/null "$BASE_URL" && break; sleep 0.5; done
  curl -sf -o /dev/null "$BASE_URL" || { echo "preview server did not start"; cat "$WORK/preview.log"; exit 1; }

  echo "== narration (Piper)"
  "$PY" "$HERE/narrate.py" "$ROOT" "$WORK"
  echo "== title cards"
  node "$HERE/cards.cjs" "$ROOT" "$WORK/cards"
  echo "== record app scenes (Playwright)"
  node "$HERE/record.cjs" "$WORK" "$BASE_URL"
fi

echo "== assemble (ffmpeg)"
"$PY" "$HERE/assemble.py" "$ROOT" "$WORK"
ffprobe -v error -show_entries stream=codec_name,width,height,r_frame_rate -show_entries format=duration,size \
  -of compact "$ROOT/submission/JalRakshak_demo.mp4"
