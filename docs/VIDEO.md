# Demo video

`submission/JalRakshak_demo.mp4` (2:55.7, 1920×1080, 30 fps, H.264 High + AAC 128k, 16.7 MB, `+faststart`)
with burned-in English subtitles. The same subtitles ship as `submission/JalRakshak_demo.srt` (38 cues).
It is fully automated: no human recording or editing.

## Regenerate (one command)

```bash
scripts/video/make_video.sh                 # ~5 min on 4 cores
WORK=/tmp/jr-video SKIP_BUILD=1 scripts/video/make_video.sh   # reuse frontend/dist
SKIP_RECORD=1 WORK=/tmp/jr-video scripts/video/make_video.sh  # only re-assemble an existing take
```

Requirements: Node + the `playwright` package with Chromium, ffmpeg with libx264 and libass, Piper at
`/opt/tools/bin/piper` with `/opt/piper-voices/en_US-lessac-medium.onnx` (override with `PIPER`, `PIPER_VOICE`,
`PIPER_LENGTH_SCALE`), Python 3 at `/opt/tools/bin/python` (override with `PYTHON`), and the Inter font.
Map tiles come from tile.openstreetmap.org. When `HTTPS_PROXY` is set, Chromium uses it. Tiles are cached in
`$WORK/tiles` and retried, so a tile that fails once does not show as a grey square.

The source of truth for scene content and narration is `docs/DEMO_SCRIPT.md`. To change what is said, edit it
and run the command again. Scene timings follow the new narration automatically.

## Pipeline (`scripts/video/`)

| Step | File | What it does |
|---|---|---|
| 0 | `make_video.sh` | Builds the demo frontend (`npm run build:demo`), serves it with `vite preview --base /Jal-rakshak/` on port 4173, runs steps 1–4 and stops the server. |
| 1 | `narrate.py` | Parses the 12 `## Scene` blocks of `DEMO_SCRIPT.md` and synthesises each narration with Piper (lessac voice, `length_scale` 1.0, 0.35 s between sentences). The spoken text gets a few pronunciation hints (JalRakshak → "Jal Rakshak", GloFAS, SMS, PDF, OSRM). Durations are measured with ffprobe and written to `$WORK/scenes.json`. |
| 2 | `cards.cjs` | Renders the 1920×1080 title cards for scenes 1, 2, 11 (architecture diagram `docs/img/architecture.png`) and 12 (GitHub and demo URLs, team), plus the backdrop for the phone scene. Each is an HTML page screenshotted by Playwright in the app's navy and teal palette. Content stays clear of the subtitle band. |
| 3 | `record.cjs` | Playwright drives the demo build at 1920×1080 with `recordVideo` in one desktop take (scenes 3–9), then a separate 390×844 mobile take (scene 10). An injected cursor and click ripple make the pointer visible. Mouse moves and scrolls are eased and time-bounded. Each scene is given its narration length + 1.3 s, with a minimum of 8 s for scenes 6 and 9. Actions are timed to the sentence that describes them (`sentAt()`, which uses the same character weighting as the subtitles). Scene start and end times are logged to `rec/timings.json`. The SitRep PDF download is captured to `rec/sitrep.pdf`. |
| 4 | `assemble.py` | Cuts each scene from the recordings by the logged timestamps. Cards are shown for narration + 1.7 s with 0.5 s fades. The phone take is scaled 1.1× and framed on the backdrop. Clips are concatenated, narration is laid in at a 0.5 s lead per scene (audio is loudness-normalised), and subtitles are generated: sentence-level cues, long sentences split at commas, timed in proportion to character count within each scene's narration. They are burned in as ASS (Inter 42 px, semi-opaque box, bottom centre). Final encode: `libx264 -preset veryfast -crf 23 -pix_fmt yuv420p -r 30`, AAC 128k, `-movflags +faststart`. |

### What the take shows (demo replay frames)

- **3:** All-India overview at frame 1. The replay plays at 1× (Guwahati goes yellow → orange), the cursor points out the national panel and the DEMO pill, then the replay is pinned at frame 6.
- **4:** Guwahati is picked from the city rail and the map flies in. The cursor covers the gauge (62.6 ORANGE), the factor tiles, the 72-h horizon and hourly rainfall charts, and the Brahmaputra GloFAS gauge card, then scrolls back to the plain-language explanation.
- **5:** Click on the Anil Nagar ward zone on the map, which opens the drill-down: 4 factor bars and the nearest shelters and hospitals.
- **6:** The replay slider is dragged from frame 6 to frame 11. The ward and city gauge turn RED (85.1, Brahmaputra 101 % of danger).
- **7:** "Run response agents". The 41 recorded steps stream on the Agents page. The camera follows the narration: the monitor decision, then the drafter lane, then "7/7 alert guards passed", then the evacuation planner, then the SitRep lane. At the end it scrolls back to the top and opens a step's "Tool input".
- **8:** "Review & approve in Admin". Clicks through the हिन्दी, मराठी, தமிழ், বাংলা tabs, types reviewer "Duty Officer R. Baruah", then Approve & send. Status SENT, review record and dispatch log are shown.
- **9:** Scrolls to the Situation report and clicks Export PDF (the download is handled).
- **10:** Phone view (same replay moment). Types "Pandu", which gives a single geocode hit with no chooser. The risk card shows "Severe risk — act now 75", then "What to do now", nearest safe shelter (Panchayat Bhawan Shelter), and emergency numbers (112, 1078, …).

## Scene timing (current render)

| # | Scene | Start – end | Length | Narration |
|---|---|---|---|---|
| 1 | Title card | 0:00.0 – 0:14.5 | 14.5 s | 12.8 s |
| 2 | The problem | 0:14.5 – 0:27.9 | 13.4 s | 11.7 s |
| 3 | Command centre | 0:27.9 – 0:45.8 | 17.9 s | 16.6 s |
| 4 | Guwahati | 0:45.8 – 1:07.0 | 21.2 s | 19.9 s |
| 5 | Ward drill-down | 1:07.0 – 1:17.7 | 10.8 s | 9.5 s |
| 6 | The flood builds | 1:17.7 – 1:25.7 | 8.0 s | 6.3 s |
| 7 | Agents at work | 1:25.7 – 1:54.0 | 28.3 s | 26.0 s |
| 8 | Human approval | 1:54.0 – 2:08.4 | 14.4 s | 13.1 s |
| 9 | Situation report | 2:08.4 – 2:17.3 | 8.9 s | 7.6 s |
| 10 | Citizen view | 2:17.3 – 2:29.3 | 11.9 s | 10.6 s |
| 11 | How it's built | 2:29.3 – 2:45.1 | 15.8 s | 14.1 s |
| 12 | Close | 2:45.1 – 2:55.7 | 10.6 s | 8.9 s |

Piper output varies slightly from run to run, so a re-render shifts these timings by a few tenths of a second.
The total stays at about 175 s, inside the 150–180 s target.

## Watch-check (current render)

I took a frame every 5 s (t = 2, 7, …, 172, 175) plus one in the middle of each scene, and looked at every one.
ffprobe reported: `h264 High 1920x1080 30/1 yuv420p`, `aac LC 48 kHz`, duration 175.67 s, 16.7 MB, and `moov` is placed before `mdat`.

| t (s) | Scene | What the frame shows | Subtitle on screen |
|---|---|---|---|
| 2–12 | 1 | Title card: logo, "Warnings people can act on.", team | "Every monsoon…", then "This is JalRakshak…", then "…open data and a local language model." |
| 17–27 | 2 | Problem card with three fact panels | "River and rainfall forecasts…", then "…multilingual instructions in time.", then "District officers are overloaded…" |
| 32–42 | 3 | All-India map, 12 cities ranked, replay advancing (frame 1 → 5/24, Guwahati yellow → orange) | "For each one we pull Open-Meteo…", then "…zero-to-one-hundred risk score…", then "This is a synthetic replay…" |
| 47–62 | 4 | Guwahati selected. The map flies in, then the gauge 62.6 ORANGE, then the horizon and rainfall charts, then the Brahmaputra gauge card | "Let's open Guwahati.", then "The score combines heavy-rain categories…", then "…forty years of river data,", then "soil wetness…" |
| 67 | 4 | Back at the top: risk explanation text | "Every factor is shown, so an officer can see exactly why." |
| 72–77 | 5 | Ward drill-down "Anil Nagar 62.6 ORANGE", factor bars, nearest shelters list | "Every ward has its own score…", then "…nearest shelters and hospitals already mapped." |
| 82 | 6 | Slider at frame 11. Wards are red, ward 85.1 RED · SEVERE, city gauge 85.1 RED | "As the replay moves forward… The risk turns red." |
| 87 | 7 | Cursor on "Run response agents" (still red) | "Now the agents take over." |
| 92 | 7 | Agent timeline streaming (14/41): Monitor lane, monitor decision "Alert warranted" | "A monitor agent, running on a small open model through Ollama," |
| 97–102 | 7 | Alert drafter lane: "7/7 alert guards passed" and the guard list | "The drafter writes SMS…", then "Guardrails check length, script…" |
| 107 | 7 | Evacuation planner lane (routes to shelters), SitRep panel on the right | "The evacuation planner routes people…" |
| 112 | 7 | Run completed. Top of the timeline with an expanded "Tool input", drafted alert, routes map | "Every step is logged with its reasoning and inputs." |
| 117–122 | 8 | Admin: alert editor with language tabs (हिन्दी … বাংলা shown in turn), reviewer name being typed | "Nothing goes out without a human.", then "The officer reviews the alert in English, Hindi…" |
| 127 | 8 | Status SENT, "Approved and sent by Duty Officer R. Baruah", dispatch log (10 rows) | "Only then is it dispatched, and that decision is logged too." |
| 132–137 | 9 | Situation report "Flood Situation Report – Guwahati, Assam", with the cursor on Export PDF | "The district officer exports it as a PDF…" |
| 142 | 10 | Phone frame: "Risk for Pandu, Guwahati: Severe risk — act now 75", "What to do now" | "Enter a place to see your risk, what to do now, your nearest shelter," |
| 147 | 10 | Phone: nearest safe shelter, Prepare/Avoid, scrolling to emergency numbers | "and emergency numbers like one-one-two." |
| 152–162 | 11 | Architecture card | "It runs on a laptop…", then "…Open-Meteo, OpenStreetMap, Leaflet, OSRM, Ollama, FastAPI, React and LightGBM." |
| 167–175 | 12 | Closing card: GitHub URL, demo URL, team, synthetic-data disclaimer | "JalRakshak turns open forecasts…", then "Built by Madhav Zanwar and Divyani Papalkar from PCCoE Pune." |

Every frame shows the page and state the narration describes. No grey or missing map tiles appear. Each frame
carries one subtitle cue, legible in its semi-opaque box at the bottom centre.

Issues found and fixed during the check:

- **Pacing.** The first take overran every scene by 2–8 s because each mouse step was slow while recording. Mouse moves and scrolls are now time-bounded.
- **Phone scene.** The page filled only a quarter of the frame because `recordVideo` ignores `deviceScaleFactor`. It is now recorded at 390×844 and scaled up.
- **Subtitles.** Two subtitle cues stacked briefly where they overlapped. Overlaps are removed now.
- **Narration sync.** Agent and admin actions now follow the narration sentences.
- **Map tiles.** One OSM tile failed and showed as a grey square. Tiles are now cached on disk and retried.

Narration edits made in `DEMO_SCRIPT.md` to match the UI:

- **Scene 5:** wards "climb first" instead of "turn red first", because at that point in the replay they are orange.
- **Scene 9:** says the agents write the report.
- **Scene 10:** the search is "Pandu", a single geocode hit, instead of "Beltola", which opens a 3-way chooser.
