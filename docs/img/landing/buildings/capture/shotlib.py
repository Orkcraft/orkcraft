"""Crop a running Textual app's real render to one region and save it as SVG + PNG (no chrome)."""
from __future__ import annotations
import io, subprocess
from pathlib import Path
from rich.console import Console
from rich.segment import Segment
from rich.style import Style

CW, LH = 12.2, 24.4          # Rich SVG cell size (CSS px)
MARGIN = 3.56                # CSS px; ×4.5 → 16 device px
SCALE = 4.5

TEMPLATE = """<svg class="rich-terminal" viewBox="0 0 @@W@@ @@H@@" width="@@W@@" height="@@H@@" xmlns="http://www.w3.org/2000/svg">
<style>
.{unique_id}-matrix {{ font-family: "DejaVu Sans Mono", monospace; font-size: {char_height}px; line-height: {line_height}px; font-variant-east-asian: full-width; }}
{styles}
</style>
<defs>
<clipPath id="{unique_id}-clip-terminal"><rect x="0" y="0" width="@@CW@@" height="@@CH@@" /></clipPath>
{lines}
</defs>
<rect x="0" y="0" width="@@W@@" height="@@H@@" fill="@@BG@@"/>
<g transform="translate(@@M@@, @@M@@)" clip-path="url(#{unique_id}-clip-terminal)">
{backgrounds}
<g class="{unique_id}-matrix">
{matrix}
</g>
</g>
</svg>
"""


def screen_lines(app):
    w, h = app.size
    con = Console(width=w, height=h, file=io.StringIO(), force_terminal=True, color_system="truecolor",
                  record=True, legacy_windows=False, safe_box=False)
    con.print(app.screen._compositor.render_update(full=True, screen_stack=app._background_screens))
    segs = [x for x in con._record_buffer if not x.control]
    return list(Segment.split_and_crop_lines(segs, w, pad=True, include_new_lines=False))


def crop(lines, x0, y0, x1, y1):
    out = []
    for line in lines[y0:y1]:
        cuts = list(Segment.divide(line, [x0, x1]))
        out.append(cuts[1])
    return out


def text_of(lines):
    return "\n".join("".join(s.text for s in l) for l in lines)



from html import escape
from rich.cells import cell_len
from rich.color import blend_rgb, ColorTriplet
FONT = "DejaVu Sans Mono"


def _rgb(c, default):
    return c.get_truecolor() if c is not None else default


def render_svg(lines, bg_hex):
    rows = len(lines)
    cols = max(Segment.get_line_length(l) for l in lines)
    W, H = cols * CW + 2 * MARGIN, rows * LH + 2 * MARGIN
    dbg = ColorTriplet(*bytes.fromhex(bg_hex[1:]))
    dfg = ColorTriplet(0xe0, 0xe0, 0xe0)
    rects, texts = [], []
    for y, line in enumerate(lines):
        x = 0
        for seg in line:
            st = seg.style or Style()
            fg, bgc = _rgb(st.color, dfg), _rgb(st.bgcolor, dbg)
            if st.reverse:
                fg, bgc = bgc, fg
            if st.dim:
                fg = blend_rgb(fg, bgc, 0.4)
            n = cell_len(seg.text)
            px, py = MARGIN + x * CW, MARGIN + y * LH
            rects.append(f'<rect x="{px:.2f}" y="{py:.2f}" width="{n*CW+0.6:.2f}" height="{LH+0.6:.2f}" fill="{bgc.hex}"/>')
            attrs = f'fill="{fg.hex}"' + (' font-weight="bold"' if st.bold else '') + (' font-style="italic"' if st.italic else '') \
                    + (' text-decoration="underline"' if st.underline else '')
            cx = x
            txt = seg.text
            for i, ch in enumerate(txt):
                w = cell_len(ch)
                if w == 1 and txt[i + 1:i + 2] == "\ufe0f" and cell_len(ch + "\ufe0f") == 2:
                    w = 2
                if w == 0:
                    if texts and ch.strip():
                        texts[-1] = texts[-1].replace("</text>", escape(ch) + "</text>")
                    continue
                if ch.strip():
                    texts.append(f'<text x="{MARGIN + (cx + w/2)*CW:.2f}" y="{py + LH*0.76:.2f}" text-anchor="middle" {attrs}>{escape(ch)}</text>')
                cx += w
            x += n
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{W:.1f}" height="{H:.1f}" viewBox="0 0 {W:.1f} {H:.1f}">'
           f'<rect width="100%" height="100%" fill="{bg_hex}"/>' + "".join(rects) +
           f'<g font-family="{FONT}, monospace" font-size="20px" xml:space="preserve">' + "".join(texts) + '</g></svg>')
    return svg, W, H


def save(lines, out: Path, bg: str | None = None) -> Path:
    import math
    if bg is None:
        st = lines[0][0].style or Style()
        bg = st.bgcolor.get_truecolor().hex if st.bgcolor else "#000000"
    svg, w, h = render_svg(lines, bg)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.with_suffix(".svg").write_text(svg, encoding="utf-8")
    html = out.with_suffix(".html")
    html.write_text(f"<!doctype html><html><head><meta charset='utf-8'></head><body style='margin:0;background:{bg}'>{svg}</body></html>", encoding="utf-8")
    subprocess.run(["/opt/pw-browsers/chromium", "--headless", "--no-sandbox", "--disable-gpu", "--hide-scrollbars",
                    f"--force-device-scale-factor={SCALE}", f"--screenshot={out}",
                    f"--window-size={max(800, math.ceil(w)) + 100},{max(600, math.ceil(h)) + 300}", html.resolve().as_uri()],
                   capture_output=True, timeout=60, check=False)
    from PIL import Image
    im = Image.open(out); im.crop((0, 0, round(w * SCALE), round(h * SCALE))).save(out)
    return out


def trim_right(rows, keep=1):
    """Cut the blank columns on the right shared by every row (keep `keep` of them)."""
    def last_ink(line):
        x, last = 0, 0
        for s in line:
            for ch in s.text:
                w = cell_len(ch)
                x += w
                if ch.strip():
                    last = x
        return last
    edge = max(last_ink(l) for l in rows) + keep
    return [list(Segment.divide(l, [edge]))[0] for l in rows]
