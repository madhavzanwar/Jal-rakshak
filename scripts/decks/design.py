"""JalRakshak deck design system (python-pptx).

One palette, one type scale, a handful of slide layouts. Every kit's content is plain data
(see content.py); this module turns a slide spec dict into a slide.
"""
from __future__ import annotations

import copy
from pathlib import Path

from lxml import etree
from PIL import Image
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_CONNECTOR, MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.oxml.ns import qn
from pptx.util import Emu, Inches, Pt

import assets

# ------------------------------------------------------------------ palette & type
NAVY = "0B1F3A"
NAVY2 = "14335A"
TEAL = "0E7C86"
TEAL_BRIGHT = "22B8C0"
TEAL_L = "E3F4F5"
SKY = "EEF4FA"
INK = "12263F"
MUTED = "4A5D73"
LINE = "C9D6E2"
WHITE = "FFFFFF"
ICE = "C7D6E6"
GREEN = "2E9E5B"
YELLOW = "E5B21E"
ORANGE = "F08A24"
RED = "D64545"
VIOLET = "5B4DB7"
AMBER_L = "FFF1E3"
RISK = {"green": GREEN, "yellow": YELLOW, "orange": ORANGE, "red": RED}

FONT = "Inter"
INDIC_FONTS = {"deva": "Noto Sans Devanagari", "taml": "Noto Sans Tamil", "beng": "Noto Sans Bengali"}

SW, SH = 13.333, 7.5
MX = 0.6  # side margin (in)
CONTENT_TOP = 1.55
CONTENT_BOTTOM = 6.55

ICONS: dict[str, Path] = {}


def rgb(h: str) -> RGBColor:
    return RGBColor.from_string(h)


# ------------------------------------------------------------------ low-level helpers
def _script_of(text: str) -> str | None:
    for ch in text:
        o = ord(ch)
        if 0x0900 <= o <= 0x097F:
            return "deva"
        if 0x0B80 <= o <= 0x0BFF:
            return "taml"
        if 0x0980 <= o <= 0x09FF:
            return "beng"
    return None


def _set_run_font(run, size, color, bold=False, italic=False, font=FONT):
    f = run.font
    f.size = Pt(size)
    f.bold = bold
    f.italic = italic
    f.color.rgb = rgb(color)
    script = _script_of(run.text)
    face = INDIC_FONTS[script] if script else font
    f.name = face
    rpr = run._r.get_or_add_rPr()
    for tag in ("a:ea", "a:cs"):
        el = rpr.find(qn(tag))
        if el is None:
            el = etree.SubElement(rpr, qn(tag))
        el.set("typeface", face)


def _no_shadow(shape):
    try:
        shape.shadow.inherit = False
    except Exception:  # noqa: BLE001 - connectors have no shadow
        pass


def soft_shadow(shape, alpha=16):
    """Subtle drop shadow (replaces any inherited effect)."""
    spPr = shape._element.spPr
    for el in spPr.findall(qn("a:effectLst")):
        spPr.remove(el)
    eff = etree.SubElement(spPr, qn("a:effectLst"))
    sh = etree.SubElement(eff, qn("a:outerShdw"), blurRad="114300", dist="28575", dir="5400000",
                          algn="t", rotWithShape="0")
    clr = etree.SubElement(sh, qn("a:srgbClr"), val=NAVY)
    etree.SubElement(clr, qn("a:alpha"), val=str(alpha * 1000))


def box(slide, x, y, w, h, fill=SKY, line=None, radius=0.12, shape=MSO_SHAPE.ROUNDED_RECTANGLE, line_w=1.25,
        name=None):
    shp = slide.shapes.add_shape(shape, Inches(x), Inches(y), Inches(w), Inches(h))
    if shape == MSO_SHAPE.ROUNDED_RECTANGLE:
        shp.adjustments[0] = min(0.5, radius / max(0.01, min(w, h)))
    if fill is None:
        shp.fill.background()
    else:
        shp.fill.solid()
        shp.fill.fore_color.rgb = rgb(fill)
    if line:
        shp.line.color.rgb = rgb(line)
        shp.line.width = Pt(line_w)
    else:
        shp.line.fill.background()
    _no_shadow(shp)
    if name:
        shp.name = name
    shp.text_frame.text = ""
    return shp


def text(slide, x, y, w, h, paras, size=16, color=INK, bold=False, align="left", anchor="top",
         italic=False, line_spacing=1.1, space_after=0, bullets=False, name=None, font=FONT):
    """Add a text box. `paras` = str | list[str | list[(text, opts)]]."""
    tb = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    if name:
        tb.name = name
    tf = tb.text_frame
    tf.word_wrap = True
    tf.auto_size = None
    for side in ("margin_left", "margin_right", "margin_top", "margin_bottom"):
        setattr(tf, side, 0)
    tf.vertical_anchor = {"top": MSO_ANCHOR.TOP, "middle": MSO_ANCHOR.MIDDLE, "bottom": MSO_ANCHOR.BOTTOM}[anchor]
    if isinstance(paras, str):
        paras = [paras]
    for i, para in enumerate(paras):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = {"left": PP_ALIGN.LEFT, "center": PP_ALIGN.CENTER, "right": PP_ALIGN.RIGHT}[align]
        p.line_spacing = line_spacing
        if space_after:
            p.space_after = Pt(space_after)
        runs = para if isinstance(para, list) else [(para, {})]
        for rtext, opts in runs:
            r = p.add_run()
            r.text = rtext
            _set_run_font(r, opts.get("size", size), opts.get("color", color), opts.get("bold", bold),
                          opts.get("italic", italic), opts.get("font", font))
        if bullets:
            _bulletize(p, size, opts_color=color)
    return tb


def _bulletize(p, size, opts_color=TEAL):
    pPr = p._p.get_or_add_pPr()
    indent = int(Pt(size) * 1.1)
    pPr.set("marL", str(indent))
    pPr.set("indent", str(-indent))
    for tag in ("a:buClr", "a:buSzPct", "a:buFont", "a:buChar", "a:buNone"):
        for el in pPr.findall(qn(tag)):
            pPr.remove(el)
    clr = etree.SubElement(pPr, qn("a:buClr"))
    etree.SubElement(clr, qn("a:srgbClr"), val=TEAL)
    etree.SubElement(pPr, qn("a:buSzPct"), val="100000")
    etree.SubElement(pPr, qn("a:buFont"), typeface="Arial")
    etree.SubElement(pPr, qn("a:buChar"), char="•")


def icon(slide, name, x, y, size, color="white"):
    key = f"{name}:{color}"
    if key not in ICONS:
        raise KeyError(f"icon {key} not available")
    return slide.shapes.add_picture(str(ICONS[key]), Inches(x), Inches(y), Inches(size), Inches(size))


def icon_badge(slide, name, x, y, d=0.62, fill=TEAL, color="white"):
    c = box(slide, x, y, d, d, fill=fill, shape=MSO_SHAPE.OVAL)
    pad = d * 0.24
    icon(slide, name, x + pad, y + pad, d - 2 * pad, color)
    return c


def picture(slide, path: Path, x, y, w, h, mode="contain", frame=True, radius=0.1, align="center", valign="top",
            shadow=True):
    """Place an image inside a box. mode: contain | cover | width (fit width, crop bottom)."""
    with Image.open(path) as im:
        iw, ih = im.size
    box_ratio = w / h
    img_ratio = iw / ih
    crop = (0, 0, 0, 0)  # l, t, r, b fractions
    if mode == "contain":
        if img_ratio > box_ratio:
            pw, ph = w, w / img_ratio
        else:
            pw, ph = h * img_ratio, h
        px = x + (w - pw) / 2 if align == "center" else (x if align == "left" else x + w - pw)
        py = y + (h - ph) / 2 if valign == "middle" else (y if valign == "top" else y + h - ph)
    else:
        pw, ph, px, py = w, h, x, y
        if img_ratio > box_ratio:  # too wide → crop sides
            excess = 1 - box_ratio / img_ratio
            crop = (excess / 2, 0, excess / 2, 0) if mode == "cover" else (0, 0, excess, 0)
        else:  # too tall → crop bottom (keep the top of a screenshot)
            excess = 1 - img_ratio / box_ratio
            crop = (0, 0, 0, excess)
    pic = slide.shapes.add_picture(str(path), Inches(px), Inches(py), Inches(pw), Inches(ph))
    pic.crop_left, pic.crop_top, pic.crop_right, pic.crop_bottom = crop
    if frame:
        # rounded corners
        prst = pic._element.spPr.find(qn("a:prstGeom"))
        prst.set("prst", "roundRect")
        av = prst.find(qn("a:avLst"))
        if av is None:
            av = etree.SubElement(prst, qn("a:avLst"))
        gd = etree.SubElement(av, qn("a:gd"), name="adj", fmla=f"val {int(50000 * min(0.5, radius / min(pw, ph)) * 2)}")
        del gd
        pic.line.color.rgb = rgb(LINE)
        pic.line.width = Pt(1)
        if shadow:
            soft_shadow(pic, 18)
    return pic, (px, py, pw, ph)


def chip(slide, x, y, label, fill=TEAL, fg=WHITE, size=11, h=0.3, pad=0.16, bold=True, w=None):
    w = w or (len(label) * size * 0.0082 + 2 * pad)
    b = box(slide, x, y, w, h, fill=fill, radius=h / 2)
    text(slide, x, y, w, h, label, size=size, color=fg, bold=bold, align="center", anchor="middle")
    return w, b


def arrow(slide, x1, y1, x2, y2, color=TEAL, width=2.0):
    c = slide.shapes.add_connector(MSO_CONNECTOR.STRAIGHT, Inches(x1), Inches(y1), Inches(x2), Inches(y2))
    c.line.color.rgb = rgb(color)
    c.line.width = Pt(width)
    ln = c.line._get_or_add_ln()
    etree.SubElement(ln, qn("a:tailEnd"), type="triangle", w="med", len="med")
    return c


# ------------------------------------------------------------------ chrome
class Ctx:
    def __init__(self, kit: dict, total: int):
        self.kit = kit
        self.total = total
        self.n = 0


def bg(slide, color=WHITE):
    fill = slide.background.fill
    fill.solid()
    fill.fore_color.rgb = rgb(color)


def dark_bg(slide):
    bg(slide, NAVY)
    p = assets.wave_background()
    slide.shapes.add_picture(str(p), 0, 0, Inches(SW), Inches(SH))


def footer(slide, ctx: Ctx, dark=False):
    col = ICE if dark else MUTED
    text(slide, MX, 7.0, 8, 0.25, f"JalRakshak  ·  {ctx.kit['event_short']}", size=10, color=col, name="Footer")
    text(slide, SW - MX - 1.5, 7.0, 1.5, 0.25, f"{ctx.n} / {ctx.total}", size=10, color=col, align="right",
         name="Slide number")


def header(slide, spec, ctx: Ctx):
    kicker = spec.get("kicker")
    if kicker:
        text(slide, MX, 0.42, 9, 0.3, kicker.upper(), size=12, color=TEAL, bold=True, name="Kicker")
    text(slide, MX, 0.7, SW - 2 * MX - (2.6 if spec.get("tag") else 0), 0.7, spec["title"], size=30, bold=True,
         color=INK, name="Title")
    tags = spec.get("tag")
    if tags:
        tags = [tags] if isinstance(tags, str) else tags
        x = SW - MX
        for t in reversed(tags):
            w = len(t) * 11 * 0.0082 + 0.36
            x -= w
            chip(slide, x, 0.45, t, fill=ORANGE, size=11, w=w)
            x -= 0.08


def sources_line(slide, spec, y=6.62):
    src = spec.get("sources")
    if src:
        text(slide, MX, y, SW - 2 * MX, 0.3, src, size=10, color=MUTED, italic=True, name="Sources")


# ------------------------------------------------------------------ layouts
def s_title(slide, spec, ctx):
    dark_bg(slide)
    kit = ctx.kit
    x = MX + 0.1
    w, _ = chip(slide, x, 0.85, kit["event_long"], fill=TEAL, size=12, h=0.36)
    if kit.get("track"):
        chip(slide, x + w + 0.12, 0.85, kit["track"], fill=ORANGE, size=12, h=0.36)
    icon_badge(slide, "droplets", x, 1.62, d=0.9, fill=TEAL_BRIGHT)
    text(slide, x + 1.1, 1.55, 6.4, 1.0, "JalRakshak", size=54, bold=True, color=WHITE, anchor="middle")
    text(slide, x, 2.75, 6.3, 1.3, spec.get("subtitle", ""), size=24, color=WHITE, bold=True, line_spacing=1.05)
    text(slide, x, 4.05, 6.1, 1.2, spec.get("tagline", ""), size=15, color=ICE, line_spacing=1.2)
    text(slide, x, 5.55, 6.3, 0.35, "Madhav Zanwar  ·  Divyani Papalkar", size=16, color=WHITE, bold=True)
    text(slide, x, 5.92, 6.3, 0.3, "Pimpri Chinchwad College of Engineering (PCCoE), Pune", size=13, color=ICE)
    p, _ = assets.screen(spec.get("image", "dashboard"))
    picture(slide, p, 7.45, 1.45, 5.3, 4.6, mode="contain", radius=0.12, valign="middle")
    footer(slide, ctx, dark=True)


def s_section(slide, spec, ctx):
    dark_bg(slide)
    text(slide, MX + 0.1, 2.3, 11, 0.4, spec.get("kicker", "").upper(), size=14, color=TEAL_BRIGHT, bold=True)
    text(slide, MX + 0.1, 2.75, 11.5, 1.2, spec["title"], size=40, color=WHITE, bold=True)
    if spec.get("body"):
        text(slide, MX + 0.1, 3.95, 10.5, 1.4, spec["body"], size=18, color=ICE, line_spacing=1.2)
    footer(slide, ctx, dark=True)


def _stat_tile(slide, x, y, w, h, st):
    est = st.get("estimate", False)
    fill = AMBER_L if est else SKY
    box(slide, x, y, w, h, fill=fill, radius=0.14)
    tx = x + 0.25
    ty = y + 0.22
    if est:
        chip(slide, tx, ty, "ESTIMATE", fill=ORANGE, size=10, h=0.26)
        ty += 0.36
    vsize = st.get("size") or min(36, int((w - 0.5) * 72 / (len(st["value"]) * 0.62)))
    text(slide, tx, ty, w - 0.5, 0.68, st["value"], size=vsize, bold=True,
         color=ORANGE if est else st.get("color", TEAL), anchor="bottom")
    text(slide, tx, ty + 0.72, w - 0.5, h - (ty - y) - 1.2, st["label"], size=st.get("label_size", 14), color=INK,
         line_spacing=1.12)
    text(slide, tx, y + h - 0.5, w - 0.5, 0.4, st["source"], size=10, color=MUTED, italic=True, anchor="bottom",
         line_spacing=1.05)


def _chain(slide, steps, y, bottom):
    """Horizontal cause→effect chain of icon steps."""
    n = len(steps)
    gap = 0.55
    w = (SW - 2 * MX - gap * (n - 1)) / n
    h = bottom - y
    for i, (ic, label) in enumerate(steps):
        x = MX + i * (w + gap)
        box(slide, x, y, w, h, fill=NAVY if i == n - 1 else TEAL_L, radius=0.12)
        icon_badge(slide, ic, x + 0.18, y + (h - 0.5) / 2, d=0.5, fill=TEAL if i < n - 1 else TEAL_BRIGHT)
        text(slide, x + 0.82, y, w - 0.95, h, label, size=13, bold=True, color=WHITE if i == n - 1 else INK,
             anchor="middle", line_spacing=1.05)
        if i < n - 1:
            arrow(slide, x + w + 0.08, y + h / 2, x + w + gap - 0.08, y + h / 2, color=TEAL, width=2.5)


def s_stats(slide, spec, ctx):
    bg(slide)
    header(slide, spec, ctx)
    stats = spec["stats"]
    points = spec.get("points")
    top = CONTENT_TOP
    if points:
        n = len(points)
        gap = 0.3
        pw = (SW - 2 * MX - gap * (n - 1)) / n
        for i, pt in enumerate(points):
            px = MX + i * (pw + gap)
            icon_badge(slide, pt["icon"], px, top + 0.05, d=0.56, fill=pt.get("color", NAVY))
            text(slide, px + 0.72, top, pw - 0.72, 0.36, pt["head"], size=16, bold=True)
            text(slide, px + 0.72, top + 0.38, pw - 0.72, 0.95, pt["body"], size=13, color=MUTED, line_spacing=1.12)
        top += 1.75
    n = len(stats)
    gap = 0.3
    tw = (SW - 2 * MX - gap * (n - 1)) / n
    th = spec.get("tile_h", CONTENT_BOTTOM - top - 0.1)
    for i, st in enumerate(stats):
        _stat_tile(slide, MX + i * (tw + gap), top, tw, th, st)
    if spec.get("chain"):
        _chain(slide, spec["chain"], top + th + 0.3, CONTENT_BOTTOM - 0.05)
    sources_line(slide, spec)
    footer(slide, ctx)


def _card(slide, x, y, w, h, c, size_head=17, size_body=13):
    fill = c.get("fill", SKY)
    box(slide, x, y, w, h, fill=fill, radius=0.14, line=c.get("line"))
    pad = 0.24
    cy = y + pad
    if c.get("icon"):
        icon_badge(slide, c["icon"], x + pad, cy, d=0.56, fill=c.get("color", TEAL))
        if c.get("label"):
            chip(slide, x + w - pad - (len(c["label"]) * 10 * 0.0082 + 0.3), cy + 0.13, c["label"],
                 fill=c.get("label_color", NAVY), size=10, h=0.28)
        cy += 0.72
    hs = c.get("head_size", size_head)
    per_line = (w - 2 * pad) * 72 / (hs * 0.6)
    lines = c.get("head_lines") or (1 if len(c["head"]) <= per_line else 2)
    text(slide, x + pad, cy, w - 2 * pad, 0.3 * lines + 0.12, c["head"], size=hs, bold=True, line_spacing=1.05)
    cy += hs / 72 * 1.3 * lines + 0.14
    body = c.get("body", "")
    if isinstance(body, list):
        text(slide, x + pad, cy, w - 2 * pad, y + h - cy - pad, body, size=size_body, color=MUTED, bullets=True,
             line_spacing=1.1, space_after=3)
    else:
        text(slide, x + pad, cy, w - 2 * pad, y + h - cy - pad, body, size=size_body, color=MUTED, line_spacing=1.15)


def s_cards(slide, spec, ctx):
    bg(slide)
    header(slide, spec, ctx)
    cards = spec["cards"]
    top = CONTENT_TOP
    if spec.get("lead"):
        text(slide, MX, top - 0.05, SW - 2 * MX, 0.5, spec["lead"], size=16, color=MUTED)
        top += 0.6
    cols = spec.get("cols", min(len(cards), 3 if len(cards) in (3, 5, 6) else 4))
    rows = (len(cards) + cols - 1) // cols
    gap = 0.3
    bottom = CONTENT_BOTTOM - (0.75 if spec.get("callout") else 0) - (1.6 if spec.get("formula") else 0)
    cw = (SW - 2 * MX - gap * (cols - 1)) / cols
    ch = (bottom - top - gap * (rows - 1)) / rows
    for i, c in enumerate(cards):
        r, k = divmod(i, cols)
        _card(slide, MX + k * (cw + gap), top + r * (ch + gap), cw, ch, c,
              size_head=spec.get("head_size", 17), size_body=spec.get("body_size", 13))
    if spec.get("callout"):
        _callout(slide, spec["callout"], CONTENT_BOTTOM - 0.5)
    if spec.get("formula"):
        _formula(slide, spec["formula"], CONTENT_BOTTOM - 1.3, CONTENT_BOTTOM)
    sources_line(slide, spec)
    footer(slide, ctx)


def _formula(slide, f, y, bottom):
    box(slide, MX, y, SW - 2 * MX, bottom - y, fill=NAVY, radius=0.14)
    text(slide, MX + 0.3, y + 0.16, 8.6, 0.45, f["line1"], size=17, bold=True, color=WHITE)
    text(slide, MX + 0.3, y + 0.66, 8.6, 0.45, f["line2"], size=14, color=ICE)
    x = SW - MX - 0.3
    for lab, col, fg in reversed([("Green <30", GREEN, WHITE), ("Yellow 30–55", YELLOW, INK),
                                  ("Orange 55–75", ORANGE, WHITE), ("Red ≥75", RED, WHITE)]):
        w = 1.25 if "Green" not in lab and "Red" not in lab else 1.0
        x -= w
        chip(slide, x, y + (bottom - y - 0.36) / 2, lab, fill=col, fg=fg, size=11, h=0.36, w=w)
        x -= 0.08


def _callout(slide, s, y, x=MX, w=SW - 2 * MX):
    box(slide, x, y, w, 0.55, fill=NAVY, radius=0.12)
    text(slide, x + 0.25, y, w - 0.5, 0.55, s, size=14, color=WHITE, bold=True, anchor="middle")


def _rows(slide, rows, x, y, w, h, size=14, gap=0.12):
    n = len(rows)
    rh = (h - gap * (n - 1)) / n
    for i, r in enumerate(rows):
        ry = y + i * (rh + gap)
        if r.get("icon"):
            icon_badge(slide, r["icon"], x, ry + 0.02, d=0.5, fill=r.get("color", TEAL))
        tx = x + (0.66 if r.get("icon") else 0)
        text(slide, tx, ry, w - (tx - x), 0.32, r["head"], size=size + 1, bold=True)
        text(slide, tx, ry + 0.33, w - (tx - x), rh - 0.33, r.get("body", ""), size=size - 1, color=MUTED,
             line_spacing=1.1)


def s_split(slide, spec, ctx):
    bg(slide)
    header(slide, spec, ctx)
    img_name = spec["image"]
    p = assets.ARCH_PNG if img_name == "architecture" else assets.screen(img_name)[0]
    left_w = spec.get("text_w", 4.6)
    gap = 0.4
    side = spec.get("image_side", "right")
    top = CONTENT_TOP
    bottom = CONTENT_BOTTOM - (0.65 if spec.get("callout") else 0)
    tx = MX if side == "right" else SW - MX - left_w
    ix = MX + left_w + gap if side == "right" else MX
    iw = SW - 2 * MX - left_w - gap
    if spec.get("rows"):
        _rows(slide, spec["rows"], tx, top, left_w, bottom - top, size=spec.get("size", 14))
    elif spec.get("bullets"):
        text(slide, tx, top, left_w, bottom - top, spec["bullets"], size=spec.get("size", 15), bullets=True,
             space_after=8, line_spacing=1.12)
    _, (px, py, pw, ph) = picture(slide, p, ix, top, iw, bottom - top - 0.35, mode=spec.get("mode", "contain"),
                                  valign="top")
    if spec.get("caption"):
        text(slide, px, py + ph + 0.08, pw, 0.3, spec["caption"], size=11, color=MUTED, italic=True,
             align="center")
    if spec.get("callout"):
        _callout(slide, spec["callout"], CONTENT_BOTTOM - 0.5)
    sources_line(slide, spec)
    footer(slide, ctx)


def s_gallery(slide, spec, ctx):
    bg(slide)
    header(slide, spec, ctx)
    items = spec["images"]
    top = CONTENT_TOP
    h = CONTENT_BOTTOM - top - 0.45
    # width weights: phone screenshots are narrow
    weights = [0.42 if it["image"] == "citizen-mobile" else 1.0 for it in items]
    gap = 0.3
    avail = SW - 2 * MX - gap * (len(items) - 1)
    x = MX
    for it, wt in zip(items, weights):
        w = avail * wt / sum(weights)
        p, _ = assets.screen(it["image"])
        _, (px, py, pw, ph) = picture(slide, p, x, top, w, h, mode=it.get("mode", "contain"), valign="top")
        text(slide, x, py + ph + 0.1, w, 0.32, [[(it["caption"], {"bold": True, "color": INK})]] if not it.get("sub") or w < 3.2
             else [[(it["caption"] + "  ", {"bold": True, "color": INK}), (it["sub"], {"color": MUTED})]],
             size=12, align="center")
        x += w + gap
    sources_line(slide, spec)
    footer(slide, ctx)


def s_image(slide, spec, ctx):
    bg(slide)
    header(slide, spec, ctx)
    p = assets.ARCH_PNG if spec["image"] == "architecture" else assets.screen(spec["image"])[0]
    bottom = CONTENT_BOTTOM + 0.3 - (0.6 if spec.get("caption") else 0)
    _, (px, py, pw, ph) = picture(slide, p, MX, CONTENT_TOP - 0.15, SW - 2 * MX, bottom - CONTENT_TOP + 0.15,
                                  mode="contain", shadow=False, radius=0.08)
    if spec.get("caption"):
        text(slide, MX, py + ph + 0.14, SW - 2 * MX, 0.4, spec["caption"], size=13, color=MUTED, align="center")
    footer(slide, ctx)


def s_agents(slide, spec, ctx):
    bg(slide)
    header(slide, spec, ctx)
    agents = spec["agents"]
    top = CONTENT_TOP
    n = len(agents)
    gap = 0.42
    aw = (SW - 2 * MX - gap * (n - 1)) / n
    ah = 2.5
    for i, a in enumerate(agents):
        x = MX + i * (aw + gap)
        box(slide, x, top, aw, ah, fill=AMBER_L, radius=0.14)
        icon_badge(slide, a["icon"], x + 0.22, top + 0.22, d=0.56, fill=ORANGE)
        text(slide, x + 0.9, top + 0.22, aw - 1.05, 0.56, a["name"], size=16, bold=True, anchor="middle",
             line_spacing=1.0)
        text(slide, x + 0.22, top + 0.92, aw - 0.44, 0.9, a["does"], size=13, color=INK, line_spacing=1.12)
        text(slide, x + 0.22, top + ah - 0.68, aw - 0.44, 0.52, [[("Tools: ", {"bold": True, "color": MUTED}),
                                                                  (a["tools"], {"color": MUTED})]], size=11,
             line_spacing=1.1, anchor="bottom")
        if i < n - 1:
            arrow(slide, x + aw + 0.06, top + ah / 2, x + aw + gap - 0.06, top + ah / 2, color=ORANGE, width=2.5)
    y2 = top + ah + 0.2
    # guardrails row
    text(slide, MX, y2, 3, 0.3, "GUARDRAILS (every draft)", size=12, bold=True, color=TEAL)
    x = MX
    for g in spec["guards"]:
        w, _ = chip(slide, x, y2 + 0.38, g, fill=TEAL_L, fg=INK, size=12, h=0.36, bold=False)
        x += w + 0.12
    y3 = y2 + 0.9
    facts = spec["facts"]
    fw = (SW - 2 * MX - 0.3 * (len(facts) - 1)) / len(facts)
    for i, f in enumerate(facts):
        fx = MX + i * (fw + 0.3)
        fill = NAVY if f.get("dark") else SKY
        box(slide, fx, y3, fw, CONTENT_BOTTOM - y3, fill=fill, radius=0.12)
        col_h, col_b = (WHITE, ICE) if f.get("dark") else (INK, MUTED)
        text(slide, fx + 0.22, y3 + 0.16, fw - 0.44, 0.32, f["head"], size=15, bold=True, color=col_h)
        text(slide, fx + 0.22, y3 + 0.52, fw - 0.44, CONTENT_BOTTOM - y3 - 0.6, f["body"], size=12, color=col_b,
             line_spacing=1.12)
    sources_line(slide, spec)
    footer(slide, ctx)


def s_alerts(slide, spec, ctx):
    """Five-language alert samples beside the admin screenshot."""
    bg(slide)
    header(slide, spec, ctx)
    top = CONTENT_TOP
    lw = spec.get("text_w", 6.3)
    samples = spec["samples"]
    gap = 0.12
    rh = (CONTENT_BOTTOM - top - gap * (len(samples) - 1)) / len(samples)
    for i, s in enumerate(samples):
        y = top + i * (rh + gap)
        box(slide, MX, y, lw, rh, fill=SKY, radius=0.1)
        chip(slide, MX + 0.16, y + 0.14, s["lang"], fill=NAVY, size=10, h=0.27, w=0.95)
        text(slide, MX + 1.25, y + 0.08, lw - 1.4, rh - 0.16, s["text"], size=s.get("size", 12), color=INK,
             anchor="middle", line_spacing=1.08)
    p, _ = assets.screen(spec.get("image", "admin"))
    ix = MX + lw + 0.4
    _, (px, py, pw, ph) = picture(slide, p, ix, top, SW - MX - ix, CONTENT_BOTTOM - top - 0.4, valign="top")
    if spec.get("caption"):
        text(slide, px, py + ph + 0.08, pw, 0.3, spec["caption"], size=11, color=MUTED, italic=True, align="center")
    sources_line(slide, spec)
    footer(slide, ctx)


def s_ml(slide, spec, ctx):
    bg(slide)
    header(slide, spec, ctx)
    top = CONTENT_TOP
    metrics = spec["metrics"]
    cols = spec.get("metric_cols", 2)
    mw = spec.get("metrics_w", 5.6)
    gap = 0.25
    rows = (len(metrics) + cols - 1) // cols
    tw = (mw - gap * (cols - 1)) / cols
    th = min(1.45, (CONTENT_BOTTOM - top - 0.9 - gap * (rows - 1)) / rows)
    for i, m in enumerate(metrics):
        r, k = divmod(i, cols)
        x = MX + k * (tw + gap)
        y = top + r * (th + gap)
        box(slide, x, y, tw, th, fill=m.get("fill", SKY), radius=0.12)
        vs = min(28, int((tw - 0.4) * 72 / (len(m["value"]) * 0.6)))
        text(slide, x + 0.2, y + 0.12, tw - 0.4, 0.55, m["value"], size=vs, bold=True, color=m.get("color", VIOLET),
             anchor="bottom")
        text(slide, x + 0.2, y + 0.72, tw - 0.4, th - 0.8, m["label"], size=12, color=INK, line_spacing=1.08)
    if spec.get("metrics_note"):
        y = top + rows * (th + gap)
        text(slide, MX, y, mw, CONTENT_BOTTOM - y, spec["metrics_note"], size=11, color=MUTED, italic=True,
             line_spacing=1.12)
    rx = MX + mw + 0.45
    rw = SW - MX - rx
    _rows(slide, spec["rows"], rx, top, rw, CONTENT_BOTTOM - top, size=spec.get("size", 14), gap=0.14)
    sources_line(slide, spec)
    footer(slide, ctx)


def s_table(slide, spec, ctx):
    bg(slide)
    header(slide, spec, ctx)
    rows = spec["rows"]
    cols = spec["columns"]
    widths = spec.get("widths", [2.4, 4.6, SW - 2 * MX - 7.0])
    top = CONTENT_TOP
    rh = min(0.62, (CONTENT_BOTTOM - top - 0.45 - (0.7 if spec.get("callout") else 0)) / len(rows))
    # header row
    x = MX
    box(slide, MX, top, SW - 2 * MX, 0.42, fill=NAVY, radius=0.08)
    for c, w in zip(cols, widths):
        text(slide, x + 0.2, top, w - 0.3, 0.42, c, size=12, bold=True, color=WHITE, anchor="middle")
        x += w
    y = top + 0.5
    for i, r in enumerate(rows):
        if i % 2 == 0:
            box(slide, MX, y, SW - 2 * MX, rh - 0.04, fill=SKY, radius=0.06)
        x = MX
        for j, (cell, w) in enumerate(zip(r, widths)):
            text(slide, x + 0.2, y, w - 0.3, rh - 0.04, cell, size=13 if j else 13, bold=(j == 0),
                 color=INK if j < 2 else MUTED, anchor="middle", line_spacing=1.05)
            x += w
        y += rh
    if spec.get("callout"):
        _callout(slide, spec["callout"], CONTENT_BOTTOM - 0.5)
    sources_line(slide, spec)
    footer(slide, ctx)


def s_plan(slide, spec, ctx):
    bg(slide)
    header(slide, spec, ctx)
    phases = spec["phases"]
    top = CONTENT_TOP + 0.05
    n = len(phases)
    gap = 0.3
    pw = (SW - 2 * MX - gap * (n - 1)) / n
    # timeline spine
    line_y = top + 0.32
    conn = slide.shapes.add_connector(MSO_CONNECTOR.STRAIGHT, Inches(MX + 0.3), Inches(line_y),
                                      Inches(SW - MX - 0.3), Inches(line_y))
    conn.line.color.rgb = rgb(LINE)
    conn.line.width = Pt(2)
    for i, ph in enumerate(phases):
        x = MX + i * (pw + gap)
        done = ph.get("status") == "done"
        col = GREEN if done else (ORANGE if ph.get("status") == "now" else NAVY2)
        box(slide, x + 0.1, top + 0.08, 0.48, 0.48, fill=col, shape=MSO_SHAPE.OVAL)
        if done:
            icon(slide, "check", x + 0.2, top + 0.18, 0.28)
        else:
            text(slide, x + 0.1, top + 0.08, 0.48, 0.48, str(i + 1), size=14, bold=True, color=WHITE,
                 align="center", anchor="middle")
        lab = {"done": "BUILT", "now": "IN PROGRESS", "next": "NEXT"}.get(ph.get("status"), "")
        if lab:
            chip(slide, x + 0.72, top + 0.18, lab, fill=col, size=10, h=0.28)
        y = top + 0.8
        box(slide, x, y, pw, CONTENT_BOTTOM - y - (0.7 if spec.get("callout") else 0), fill=SKY, radius=0.12)
        text(slide, x + 0.2, y + 0.16, pw - 0.4, 0.62, ph["head"], size=15, bold=True, line_spacing=1.05)
        text(slide, x + 0.2, y + 0.8, pw - 0.4, CONTENT_BOTTOM - y - 1.0, ph["items"], size=12, color=MUTED,
             bullets=True, space_after=4, line_spacing=1.08)
    if spec.get("callout"):
        _callout(slide, spec["callout"], CONTENT_BOTTOM - 0.5)
    sources_line(slide, spec)
    footer(slide, ctx)


def s_team(slide, spec, ctx):
    bg(slide)
    header(slide, spec, ctx)
    members = spec["members"]
    top = CONTENT_TOP + 0.1
    gap = 0.4
    mw = (SW - 2 * MX - gap) / 2
    mh = 2.9
    for i, m in enumerate(members):
        x = MX + i * (mw + gap)
        box(slide, x, top, mw, mh, fill=SKY, radius=0.16)
        circ = box(slide, x + 0.35, top + 0.4, 1.3, 1.3, fill=TEAL if i == 0 else NAVY2, shape=MSO_SHAPE.OVAL)
        del circ
        text(slide, x + 0.35, top + 0.4, 1.3, 1.3, m["initials"], size=34, bold=True, color=WHITE, align="center",
             anchor="middle")
        text(slide, x + 1.95, top + 0.4, mw - 2.2, 0.45, m["name"], size=22, bold=True)
        text(slide, x + 1.95, top + 0.88, mw - 2.2, 0.35, m["role"], size=14, bold=True, color=TEAL)
        text(slide, x + 1.95, top + 1.3, mw - 2.2, mh - 1.45, m["owns"], size=13, color=MUTED, bullets=True,
             space_after=3, line_spacing=1.08)
    y = top + mh + 0.35
    box(slide, MX, y, SW - 2 * MX, CONTENT_BOTTOM - y, fill=NAVY, radius=0.14)
    icon_badge(slide, "award", MX + 0.3, y + 0.3, d=0.62, fill=TEAL_BRIGHT)
    text(slide, MX + 1.15, y + 0.22, SW - 2 * MX - 1.5, 0.4, spec.get("org", ""), size=17, bold=True, color=WHITE)
    text(slide, MX + 1.15, y + 0.62, SW - 2 * MX - 1.5, CONTENT_BOTTOM - y - 0.7, spec.get("note", ""), size=13,
         color=ICE, line_spacing=1.12)
    footer(slide, ctx)


def s_criteria(slide, spec, ctx):
    bg(slide)
    header(slide, spec, ctx)
    items = spec["items"]
    cols = 2
    rows = (len(items) + 1) // 2
    gap = 0.22
    top = CONTENT_TOP
    cw = (SW - 2 * MX - gap) / cols
    ch = (CONTENT_BOTTOM - top - gap * (rows - 1)) / rows
    for i, it in enumerate(items):
        r, k = divmod(i, cols)
        x = MX + k * (cw + gap)
        y = top + r * (ch + gap)
        box(slide, x, y, cw, ch, fill=SKY, radius=0.1)
        icon_badge(slide, it["icon"], x + 0.18, y + (ch - 0.5) / 2, d=0.5, fill=ORANGE)
        text(slide, x + 0.85, y + 0.08, 2.3, ch - 0.16, it["criterion"], size=14, bold=True, anchor="middle")
        text(slide, x + 3.1, y + 0.06, cw - 3.3, ch - 0.12, it["evidence"], size=12, color=MUTED, anchor="middle",
             line_spacing=1.08)
    footer(slide, ctx)


def s_closing(slide, spec, ctx):
    dark_bg(slide)
    x = MX + 0.1
    text(slide, x, 1.0, 11, 0.4, spec.get("kicker", "THANK YOU").upper(), size=14, bold=True, color=TEAL_BRIGHT)
    text(slide, x, 1.45, 11.8, 1.0, spec["title"], size=38, bold=True, color=WHITE)
    if spec.get("body"):
        text(slide, x, 2.45, 11.5, 0.9, spec["body"], size=17, color=ICE, line_spacing=1.2)
    links = spec.get("links", [])
    y = 3.5
    for ic, lab, val in links:
        icon_badge(slide, ic, x, y, d=0.5, fill=TEAL)
        text(slide, x + 0.7, y - 0.02, 2.6, 0.54, lab, size=14, bold=True, color=ICE, anchor="middle")
        text(slide, x + 3.0, y - 0.02, 8.5, 0.54, val, size=16, bold=True, color=WHITE, anchor="middle")
        y += 0.68
    text(slide, x, 6.25, 11, 0.35, "Madhav Zanwar  ·  Divyani Papalkar  ·  PCCoE Pune", size=14, color=WHITE,
         bold=True)
    footer(slide, ctx, dark=True)


LAYOUTS = {
    "title": s_title, "section": s_section, "stats": s_stats, "cards": s_cards, "split": s_split,
    "gallery": s_gallery, "image": s_image, "agents": s_agents, "alerts": s_alerts, "ml": s_ml,
    "table": s_table, "plan": s_plan, "team": s_team, "criteria": s_criteria, "closing": s_closing,
}


def build_deck(kit: dict, slides: list[dict], out: Path) -> int:
    ICONS.update(assets.render_icons())
    prs = Presentation()
    prs.slide_width = Inches(SW)
    prs.slide_height = Inches(SH)
    blank = prs.slide_layouts[6]
    ctx = Ctx(kit, len(slides))
    for spec in slides:
        ctx.n += 1
        slide = prs.slides.add_slide(blank)
        LAYOUTS[spec["layout"]](slide, spec, ctx)
        if spec.get("notes"):
            slide.notes_slide.notes_text_frame.text = spec["notes"]
    prs.core_properties.title = f"JalRakshak — {kit['event_long']}"
    prs.core_properties.author = "Madhav Zanwar, Divyani Papalkar"
    prs.core_properties.subject = "Agentic flood early-warning and response platform for India"
    out.parent.mkdir(parents=True, exist_ok=True)
    prs.save(out)
    return len(slides)


_ = (copy, Emu)
