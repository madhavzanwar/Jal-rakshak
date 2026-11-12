#!/usr/bin/env python3
"""Assemble the JalRakshak demo video from cards, screen recordings and narration.

Usage: assemble.py <repo_root> <work_dir>
Inputs  (work_dir): scenes.json, audio/sceneNN.wav (narrate.py), cards/*.png (cards.cjs),
                    rec/app.webm, rec/phone.webm, rec/timings.json (record.cjs)
Outputs: submission/JalRakshak_demo.mp4, submission/JalRakshak_demo.srt, work_dir/plan.json
"""
import json, re, subprocess, sys
from pathlib import Path

root, work = Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve()
scenes = json.loads((work / "scenes.json").read_text())
tim = json.loads((work / "rec" / "timings.json").read_text())
seg_dir = work / "seg"
seg_dir.mkdir(exist_ok=True)
out_mp4 = root / "submission" / "JalRakshak_demo.mp4"
out_srt = root / "submission" / "JalRakshak_demo.srt"
out_mp4.parent.mkdir(exist_ok=True)

FPS = 30
CARD = {1: "card01", 2: "card02", 11: "card11", 12: "card12"}
CARD_LEAD, CARD_TAIL = 0.7, 1.0
APP_LEAD = 0.5  # must match record.cjs LEAD
FADE = 0.5
MEZZ = ["-c:v", "libx264", "-preset", "veryfast", "-crf", "16", "-pix_fmt", "yuv420p", "-r", str(FPS)]


def run(cmd):
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)


def probe_dur(p):
    return float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                                          "-of", "csv=p=0", str(p)]).decode().strip())


plan, t = [], 0.0
for s in scenes:
    n = s["n"]
    if n in CARD:
        lead, dur = CARD_LEAD, s["dur"] + CARD_LEAD + CARD_TAIL
    elif str(n) in tim["app"]:
        a, b = tim["app"][str(n)]
        lead, dur = APP_LEAD, b - a
    else:
        a, b = tim["phone"][str(n)]
        lead, dur = APP_LEAD, b - a
    dur = round(round(dur * FPS) / FPS, 4)  # whole frames so audio and video stay in step
    plan.append({"n": n, "title": s["title"], "start": round(t, 3), "end": round(t + dur, 3), "dur": dur,
                 "lead": lead, "narr": s["dur"], "text": s["narration"], "wav": s["wav"]})
    t += dur
total = t
print(f"total {total:.2f}s")

# ---------------------------------------------------------------- video segments
for p in plan:
    n, dur, seg = p["n"], p["dur"], seg_dir / f"v{p['n']:02d}.mp4"
    fade_out = f"fade=t=out:st={dur - FADE:.3f}:d={FADE}"
    if n in CARD:
        png = work / "cards" / f"{CARD[n]}.png"
        run(["ffmpeg", "-y", "-loop", "1", "-framerate", str(FPS), "-i", str(png), "-t", f"{dur:.3f}",
             "-vf", f"format=yuv420p,fade=t=in:st=0:d={FADE},{fade_out}", *MEZZ, "-an", str(seg)])
    elif str(n) in tim["app"]:
        a, _ = tim["app"][str(n)]
        vf = "fps=30,tpad=stop_mode=clone:stop_duration=2,scale=1920:1080:flags=lanczos,format=yuv420p"
        if n == 3:
            vf += f",fade=t=in:st=0:d={FADE}"
        if n == 9:
            vf += "," + fade_out
        run(["ffmpeg", "-y", "-ss", f"{a:.3f}", "-i", str(work / "rec" / "app.webm"), "-t", f"{dur:.3f}",
             "-vf", vf, *MEZZ, "-an", str(seg)])
    else:
        a, _ = tim["phone"][str(n)]
        # 390x844 recording -> shown at 1.1x CSS size (429x928) in a phone frame on the backdrop.
        fc = (f"[1:v]fps=30,tpad=stop_mode=clone:stop_duration=2,scale=429:928:flags=lanczos,pad=453:952:12:12:color=0x1e293b,"
              f"pad=457:956:2:2:color=0x38bdf8@0.45[ph];"
              f"[0:v][ph]overlay=(W-w)/2:30,format=yuv420p,fade=t=in:st=0:d={FADE},{fade_out}[v]")
        run(["ffmpeg", "-y", "-loop", "1", "-framerate", str(FPS), "-i", str(work / "cards" / "phone_bg.png"),
             "-ss", f"{a:.3f}", "-i", str(work / "rec" / "phone.webm"), "-t", f"{dur:.3f}",
             "-filter_complex", fc, "-map", "[v]", *MEZZ, "-an", str(seg)])
    got = probe_dur(seg)
    if abs(got - dur) > 0.05:
        print(f"  warning: scene {n} segment {got:.3f}s vs planned {dur:.3f}s")
    print(f"  segment {n:2d}  {p['start']:7.2f}–{p['end']:7.2f}  ({dur:.2f}s, narration {p['narr']:.2f}s)")

(seg_dir / "list.txt").write_text("".join(f"file 'v{p['n']:02d}.mp4'\n" for p in plan))
run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(seg_dir / "list.txt"), "-c", "copy",
     str(seg_dir / "video.mp4")])

# ---------------------------------------------------------------- narration track
for p in plan:
    ms = int(p["lead"] * 1000)
    run(["ffmpeg", "-y", "-i", p["wav"], "-af", f"aresample=48000,adelay={ms}:all=1,apad",
         "-t", f"{p['dur']:.3f}", "-ac", "1", "-ar", "48000", str(seg_dir / f"a{p['n']:02d}.wav")])
(seg_dir / "alist.txt").write_text("".join(f"file 'a{p['n']:02d}.wav'\n" for p in plan))
run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(seg_dir / "alist.txt"),
     "-af", "loudnorm=I=-16:TP=-1.5:LRA=11", "-ar", "48000", str(seg_dir / "narration.wav")])

# ---------------------------------------------------------------- subtitles
def chunks(text, limit=96):
    out = []
    for sent in re.split(r"(?<=[.!?])\s+", text.strip()):
        if len(sent) <= limit:
            out.append(sent)
            continue
        parts, cur = re.split(r"(?<=,)\s+", sent), ""
        for part in parts:
            if cur and len(cur) + 1 + len(part) > limit:
                out.append(cur)
                cur = part
            else:
                cur = f"{cur} {part}".strip()
        if cur:
            out.append(cur)
    # never leave a tiny dangling cue
    merged = []
    for c in out:
        if merged and len(c) < 22 and len(merged[-1]) + len(c) < limit + 20:
            merged[-1] += " " + c
        else:
            merged.append(c)
    return merged


cues = []
for p in plan:
    parts = chunks(p["text"])
    weights = [len(c) + 12 for c in parts]  # +12 ~ the pause Piper leaves between sentences
    t0, span = p["start"] + p["lead"], p["narr"]
    acc = 0
    for c, w in zip(parts, weights):
        a = t0 + span * acc / sum(weights)
        acc += w
        b = t0 + span * acc / sum(weights)
        cues.append((a, b, c))
    # hold the scene's last cue a little longer (never into the next scene)
    a, b, c = cues[-1]
    cues[-1] = (a, min(b + 0.4, p["end"] - 0.05), c)


def ts(x, sep=","):
    h, rem = divmod(x, 3600)
    m, s = divmod(rem, 60)
    return f"{int(h):02d}:{int(m):02d}:{int(s):02d}{sep}{int(round((s - int(s)) * 1000)):03d}" if sep == "," else \
        f"{int(h)}:{int(m):02d}:{s:05.2f}"


out_srt.write_text("".join(f"{i}\n{ts(a)} --> {ts(b)}\n{c}\n\n" for i, (a, b, c) in enumerate(cues, 1)),
                   encoding="utf-8")
ass = work / "subs.ass"
ass.write_text(f"""[Script Info]
ScriptType: v4.00+
PlayResX: 1920
PlayResY: 1080
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Inter,42,&H00FFFFFF,&H00FFFFFF,&H50000000,&H50000000,0,0,0,0,100,100,0,0,3,10,0,2,300,300,34,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
""" + "".join(f"Dialogue: 0,{ts(a, '.')},{ts(b, '.')},Default,,0,0,0,,{c}\n" for a, b, c in cues), encoding="utf-8")

# ---------------------------------------------------------------- final encode
run(["ffmpeg", "-y", "-i", str(seg_dir / "video.mp4"), "-i", str(seg_dir / "narration.wav"),
     "-vf", f"ass={ass}", "-map", "0:v", "-map", "1:a",
     "-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-pix_fmt", "yuv420p", "-r", str(FPS),
     "-c:a", "aac", "-b:a", "128k", "-ar", "48000", "-movflags", "+faststart", "-shortest", str(out_mp4)])
(work / "plan.json").write_text(json.dumps({"total": total, "scenes": plan, "cues": cues}, indent=2))
print(f"wrote {out_mp4} ({out_mp4.stat().st_size / 1e6:.1f} MB, {probe_dur(out_mp4):.2f}s) and {out_srt}")
