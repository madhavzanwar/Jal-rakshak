"""One-off helper: vendor a few Lucide icons (ISC licence) as plain SVG files.

Usage: python extract_icons.py <path-to-lucide-react/dist/esm/icons>
"""
import re
import sys
from pathlib import Path

NAMES = ["droplets", "cloud-rain", "waves", "bell-ring", "map-pin", "cpu", "shield-check",
         "user-check", "smartphone", "file-text", "chart-line", "route", "globe", "wifi-off",
         "layers", "users", "indian-rupee", "languages", "bot", "server", "laptop", "git-branch",
         "eye", "trending-up", "zap", "lock", "siren", "hospital", "house", "triangle-alert",
         "radio-tower", "scale", "rocket", "clock", "check", "award", "lightbulb", "target",
         "boxes", "heart-handshake", "satellite", "message-square-text", "brain-circuit"]

src = Path(sys.argv[1])
out = Path(__file__).parent / "icons"
out.mkdir(exist_ok=True)
for name in NAMES:
    f = src / f"{name}.js"
    if not f.exists():
        print("missing", name)
        continue
    text = f.read_text()
    elems = re.findall(r'\[\s*"(\w+)",\s*\{(.*?)\}\s*\]', text, re.S)
    parts = []
    for tag, attrs in elems:
        kv = re.findall(r'(\w+):\s*"([^"]*)"', attrs)
        a = " ".join(f'{k}="{v}"' for k, v in kv if k != "key")
        parts.append(f"<{tag} {a}/>")
    svg = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" '
           'stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
           + "".join(parts) + "</svg>\n")
    (out / f"{name}.svg").write_text(svg)
print("ok")
