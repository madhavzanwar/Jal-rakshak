"""Build every submission kit: decks, abstracts, READMEs.

Usage: /opt/tools/bin/python scripts/decks/build.py [kit ...]
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import assets  # noqa: E402
import content  # noqa: E402
import design  # noqa: E402
import docs  # noqa: E402

ROOT = HERE.parents[1]
SUB = ROOT / "submission"

DECK_NAMES = {
    "khacks-4.0": "JalRakshak_KHacks4.pptx",
    "hacknova-2.0": "JalRakshak_HackNova2.pptx",
    "vytron-26": "JalRakshak_VYTRON26_Round1.pptx",
    "clash-of-commits": "JalRakshak_ClashOfCommits.pptx",
    "hacktopia-pune-2026": "JalRakshak_HacktopiaPune2026.pptx",
}


def build_kit(kit_id: str) -> dict:
    kit = content.KITS[kit_id]
    slides = content.slides_for(kit_id)
    out = SUB / kit_id / DECK_NAMES[kit_id]
    n = design.build_deck(kit, slides, out)
    if kit_id == "clash-of-commits" and n != 10:
        raise SystemExit(f"Clash of Commits deck must have exactly 10 slides, got {n}")
    docs.write_kit_docs(kit_id, kit, out, n)
    return {"kit": kit_id, "deck": out, "slides": n}


def main(argv: list[str]) -> None:
    kits = argv or list(content.KITS)
    missing = assets.missing_screens()
    if missing:
        print("WARNING: placeholder screenshots used for:", ", ".join(missing))
    if not assets.backtest():
        print("WARNING: backend/models/backtest.json missing; ML tiles show 'pending'")
    for k in kits:
        r = build_kit(k)
        print(f"{r['kit']}: {r['deck'].relative_to(ROOT)} ({r['slides']} slides)")
    docs.write_sources()


if __name__ == "__main__":
    main(sys.argv[1:])
