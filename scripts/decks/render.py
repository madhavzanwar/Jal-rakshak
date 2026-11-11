"""Render a deck to PNGs for visual QA: pptx → pdf (LibreOffice) → png (PyMuPDF).

Usage: /opt/tools/bin/python scripts/decks/render.py submission/<kit>/<deck>.pptx [...]
Outputs into submission/<kit>/_render/ (gitignored).
"""
from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pymupdf
from pptx import Presentation


def render(pptx: Path, dpi: int = 110) -> list[Path]:
    out_dir = pptx.parent / "_render"
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True)
    with tempfile.TemporaryDirectory() as tmp:
        profile = Path(tmp) / "lo-profile"
        subprocess.run(["soffice", f"-env:UserInstallation=file://{profile}", "--headless", "--convert-to", "pdf",
                        "--outdir", tmp, str(pptx)], check=True, capture_output=True, timeout=240)
        pdf = Path(tmp) / (pptx.stem + ".pdf")
        doc = pymupdf.open(pdf)
        paths = []
        for i, page in enumerate(doc, start=1):
            p = out_dir / f"slide-{i:02d}.png"
            page.get_pixmap(dpi=dpi).save(p)
            paths.append(p)
        shutil.copy(pdf, out_dir / (pptx.stem + ".pdf"))
    n_pptx = len(Presentation(pptx).slides)
    if n_pptx != len(paths):
        raise SystemExit(f"{pptx}: pptx has {n_pptx} slides but PDF has {len(paths)} pages")
    return paths


if __name__ == "__main__":
    for arg in sys.argv[1:]:
        ps = render(Path(arg))
        print(f"{arg}: {len(ps)} slides → {ps[0].parent}")
