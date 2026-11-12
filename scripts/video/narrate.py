#!/usr/bin/env python3
"""Parse docs/DEMO_SCRIPT.md into scenes and synthesise each narration with Piper.

Writes <work>/scenes.json: [{n, title, visual, narration, wav, dur}] and <work>/audio/sceneNN.wav.
Usage: narrate.py <repo_root> <work_dir>
Env: PIPER (binary), PIPER_VOICE (onnx), PIPER_LENGTH_SCALE (default 1.0).
"""
import json, os, re, subprocess, sys
from pathlib import Path

root, work = Path(sys.argv[1]), Path(sys.argv[2])
piper = os.environ.get("PIPER", "/opt/tools/bin/piper")
voice = os.environ.get("PIPER_VOICE", "/opt/piper-voices/en_US-lessac-medium.onnx")
scale = os.environ.get("PIPER_LENGTH_SCALE", "1.0")
SENT_PAUSE = os.environ.get("PIPER_SENTENCE_SILENCE", "0.35")

text = (root / "docs" / "DEMO_SCRIPT.md").read_text(encoding="utf-8")
scenes = []
for m in re.finditer(r"^## Scene (\d+) — (.+?)\n(.*?)(?=^## Scene |\Z)", text, re.S | re.M):
    body = m.group(3)
    vis = re.search(r"\*\*Visual:\*\*\s*(.+)", body)
    nar = re.search(r"\*\*Narration:\*\*\s*(.+?)(?:\n\s*\n|\Z)", body, re.S)
    scenes.append({
        "n": int(m.group(1)),
        "title": m.group(2).strip(),
        "visual": vis.group(1).strip() if vis else "",
        "narration": " ".join(nar.group(1).split()) if nar else "",
    })
assert len(scenes) == 12, f"expected 12 scenes, got {len(scenes)}"

# Spoken text can differ from subtitle text (e.g. digits are spelled out already in the script).
def spoken(s: str) -> str:
    return s.replace("JalRakshak", "Jal Rakshak").replace("PCCoE", "P C C O E").replace("SitRep", "sit-rep") \
            .replace("GloFAS", "Glow-fass").replace("OSRM", "O S R M").replace("LightGBM", "Light G B M") \
            .replace("SMS", "S M S").replace("PDF", "P D F").replace("Ollama", "Oh-llama")

audio = work / "audio"
audio.mkdir(parents=True, exist_ok=True)
for s in scenes:
    wav = audio / f"scene{s['n']:02d}.wav"
    subprocess.run([piper, "--model", voice, "--length_scale", scale, "--sentence_silence", SENT_PAUSE,
                    "--output_file", str(wav)], input=spoken(s["narration"]).encode(), check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    dur = float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                                         "-of", "csv=p=0", str(wav)]).decode().strip())
    s["wav"], s["dur"] = str(wav), round(dur, 3)
    print(f"scene {s['n']:2d}  {dur:6.2f}s  {s['title']}")
(work / "scenes.json").write_text(json.dumps(scenes, indent=2), encoding="utf-8")
print("total narration", round(sum(s["dur"] for s in scenes), 2), "s")
