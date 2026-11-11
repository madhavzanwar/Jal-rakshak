# K! Hacks 4.0 — what to upload where

Platform: **Unstop** · Prize: ₹6 lakh prize pool · Track/theme: **Disaster Management · Agentic AI**

All files are in `submission/khacks-4.0/`. Regenerate everything with `scripts/decks/build_all.sh`.

## Files in this kit

| File | What it is |
|---|---|
| `JalRakshak_KHacks4.pptx` | Pitch deck, 10 slides, 16:9 |
| `_render/JalRakshak_KHacks4.pdf` | PDF export of the deck (generated locally by build_all.sh, gitignored; upload this where a PDF is required) |
| `abstract.md` / `abstract.pdf` | One-page abstract |

## IMPORTANT: move the content into the official K! Hacks idea template

`templates/khacks_template.pptx` was **not** available when this kit was built, so `JalRakshak_KHacks4.pptx` is a clean
10-slide deck in our own design. **Before uploading**, download the official K! Hacks 4.0 idea-submission
template from the Unstop event page and copy the content in, slide by slide, **without changing the template's
structure** (keep its slide order, titles and logos). Suggested mapping:

| Template section (typical) | Take content from our slide |
|---|---|
| Title / team details | 1 (title) and 10 (team) |
| Problem statement | 2 |
| Proposed solution / idea | 3 |
| Agentic AI / innovation / uniqueness | 4 and 5 |
| Prototype / screenshots / demo | 6 |
| Architecture / technical approach | 7 |
| Feasibility, ML, validation | 8 |
| Impact / benefits | 9 |
| Team | 10 |

If the official template is later saved as `templates/khacks_template.pptx`, re-run the build and fill it in
place instead.

## Unstop submission form (K! Hacks 4.0)

| Unstop field | What to enter / upload |
|---|---|
| Track / theme | **Disaster Management** (mention *Agentic AI* in the title/description) |
| Idea title | JalRakshak: Agentic AI for flood early warning and response |
| Idea description | Short description below + first paragraph of `abstract.md` |
| Presentation (PPT/PDF) | The official template filled with our content (export to PDF if the form asks for PDF) |
| Abstract / supporting document (if asked) | `abstract.pdf` |
| GitHub / prototype link | https://github.com/madhavzanwar/Jal-rakshak |
| Demo link | https://madhavzanwar.github.io/Jal-rakshak/ |
| Video link (if asked) | YouTube link: <paste after upload> |

## Links (paste exactly)

| Field | Value |
|---|---|
| GitHub repository | https://github.com/madhavzanwar/Jal-rakshak |
| Live demo (static replay, no install) | https://madhavzanwar.github.io/Jal-rakshak/ |
| Demo video file | `submission/JalRakshak_demo.mp4` |
| YouTube link | <paste after upload> |

## Team details

| Field | Value |
|---|---|
| Team name | JalRakshak |
| Members | Madhav Zanwar, Divyani Papalkar |
| Institute | Pimpri Chinchwad College of Engineering (PCCoE), Pune |
| Project title | JalRakshak: agentic flood early warning and response for India |
| Tagline | Agentic AI flood early warning for India: open data, local LLM, 5 languages |
| Short description (≈300 chars) | JalRakshak turns free rainfall and river forecasts into ward-level flood risk for 12 Indian cities, then local-LLM agents draft 5-language SMS/WhatsApp alerts, evacuation routes and a situation report for an officer to approve. Zero paid services; runs on a laptop. |

## Before you press submit

- [ ] Open the deck in PowerPoint / Google Slides once and check fonts (Inter; Noto Sans for Indic text). If
      Inter is missing, install it or export the PDF from `_render/` instead.
- [ ] Upload `submission/JalRakshak_demo.mp4` to YouTube (unlisted is fine unless the rules say public) and paste the link above
      and into every "video" field.
- [ ] Check the live demo link opens on a phone.
- [ ] Keep the GitHub repository public until results are announced.
