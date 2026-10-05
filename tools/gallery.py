"""A gallery of every building three ways, from the GUI's demo: one HTML page to walk in the morning.

    python tools/gallery.py [--out DIR] [--demo DIR] [--chromium PATH]

It builds the demo afresh, starts `orkcraft gui --demo --browser` on a free port and walks it with
Playwright (Chromium), orkspace by orkspace. For each building it takes the three views of
docs/design/building-views.md — closed (its card close up, and the map with it outlined), command
(selected: Info, the garrison, the Command Card with its preview) and full (its window) — then the
Lake window with a document open, the Town Hall's chat and the Answers. It listens for page errors
and console errors all along and looks for plain problems: an empty card, an empty preview or
window, text cut off, "orc" where a person reads. Out come `index.html`, `report.json` and the
pictures in `shots/`.

Needs `pip install playwright` and a Chromium (`playwright install chromium`, or `--chromium`).
"""
from __future__ import annotations

import argparse
import dataclasses
import datetime as dt
import html
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VIEWPORT = (1440, 900)
WAIT_MS = 1200                # after a click, for the host's answer and the page to draw it
LAKE_DOCS = ("docs/meetings/design-sync.md", "docs/handbook/releases.md")
WORDING = re.compile(r"\b[Oo]rcs?\b|[Oo]rchestrat")

# What a view's text is cut at, and where it spills: run in the page on a container.
CUT_JS = """(args) => {
  const [sel, spills] = args, root = document.querySelector(sel);
  if (!root) return [];
  const out = [], box = root.getBoundingClientRect(), lines = [];
  for (const el of root.querySelectorAll('*')) {
    if (el.closest('.gui-hut__road, button')) continue;            // the road handle sits on the edge
    const own = [...el.childNodes].some(n => n.nodeType === 3 && n.textContent.trim());
    if (!own || !el.offsetParent) continue;
    const st = getComputedStyle(el), r = el.getBoundingClientRect();
    const text = el.innerText.trim().slice(0, 80);
    if (!text || !r.width) continue;
    const clips = /hidden|clip/.test(st.overflowX) || st.textOverflow === 'ellipsis';
    if (clips && el.scrollWidth > el.clientWidth + 1) out.push({kind: 'cut', text});
    else if (spills && (r.right > box.right + 1 || r.left < box.left - 1)) out.push({kind: 'spills out', text});
    if (st.display !== 'inline' && r.bottom > box.top && r.top < box.bottom) lines.push({r, text, el});
  }
  // rows drawn over each other: two blocks of text that overlap, neither inside the other
  for (let i = 0; i < lines.length; i++) for (let j = i + 1; j < lines.length; j++) {
    const a = lines[i], b = lines[j];
    if (a.el.contains(b.el) || b.el.contains(a.el)) continue;
    const w = Math.min(a.r.right, b.r.right) - Math.max(a.r.left, b.r.left);
    const h = Math.min(a.r.bottom, b.r.bottom) - Math.max(a.r.top, b.r.top);
    if (w > 4 && h > 4) { out.push({kind: 'overlaps', text: `${a.text.slice(0, 40)} / ${b.text.slice(0, 40)}`}); i = lines.length; break; }
  }
  return out.slice(0, 8);
}"""


@dataclasses.dataclass
class Shot:
    file: str
    caption: str


@dataclasses.dataclass
class Building:
    id: str
    title: str                 # as the page says it (Office)
    type: str
    orkspace: str
    closed: list[Shot] = dataclasses.field(default_factory=list)
    command: list[Shot] = dataclasses.field(default_factory=list)
    full: list[Shot] = dataclasses.field(default_factory=list)
    problems: list[dict] = dataclasses.field(default_factory=list)    # {level: error|warn, view, text}


@dataclasses.dataclass
class Gallery:
    made: str
    url: str = ""
    buildings: list[Building] = dataclasses.field(default_factory=list)
    extras: list[Building] = dataclasses.field(default_factory=list)  # Lake, the chat, the Answers
    maps: list[Shot] = dataclasses.field(default_factory=list)
    errors: list[dict] = dataclasses.field(default_factory=list)      # page and console errors: {at, kind, text}


# -- the GUI ------------------------------------------------------------------------------------------

def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def start_gui(demo_dir: Path, port: int, log: Path) -> tuple[subprocess.Popen, str]:
    """`orkcraft gui --demo` in the browser mode, on `port`; (the process, its address)."""
    env = {**os.environ, "BROWSER": "true", "PYTHONUNBUFFERED": "1"}       # no browser of its own opens
    proc = subprocess.Popen([sys.executable, "-m", "orkcraft", "--demo-reset", "gui", "--demo", str(demo_dir),
                             "--browser", "--port", str(port)], cwd=ROOT, env=env, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, text=True)
    end, seen = time.monotonic() + 180, []
    while time.monotonic() < end:
        line = proc.stdout.readline()
        if not line:
            if proc.poll() is not None:
                break
            continue
        seen.append(line)
        m = re.search(r"(http://127\.0\.0\.1:\d+/\?t=\S+)", line)
        if m:
            log.write_text("".join(seen), encoding="utf-8")
            return proc, m.group(1)
    proc.kill()
    raise RuntimeError("the GUI did not start:\n" + "".join(seen)[-2000:])


# -- walking it --------------------------------------------------------------------------------------

class Walk:
    def __init__(self, page, out: Path, gallery: Gallery) -> None:
        self.page, self.out, self.g = page, out, gallery
        self.step = "start"
        (out / "shots").mkdir(parents=True, exist_ok=True)
        page.on("pageerror", lambda e: self._error("pageerror", str(e)))
        page.on("console", lambda m: m.type == "error" and self._error("console", m.text))

    def _error(self, kind: str, text: str) -> None:
        self.g.errors.append({"at": self.step, "kind": kind, "text": text[:600]})

    def shot(self, name: str, caption: str, element=None, pad: int = 14) -> Shot:
        rel = f"shots/{name}"
        path = self.out / rel
        if element is not None:
            box = element.bounding_box()
            clip = {"x": max(box["x"] - pad, 0), "y": max(box["y"] - pad - 22, 0),          # the title above it
                    "width": box["width"] + 2 * pad, "height": box["height"] + 2 * pad + 22}
            self.page.screenshot(path=str(path), clip=clip)
        else:
            self.page.screenshot(path=str(path), type="jpeg", quality=82)
        return Shot(rel, caption)

    def wait(self, ms: int = WAIT_MS) -> None:
        self.page.wait_for_timeout(ms)

    def text(self, selector: str) -> str:
        loc = self.page.locator(selector)
        return loc.first.inner_text().strip() if loc.count() else ""

    def cut(self, selector: str, spills: bool = False) -> list[dict]:
        return self.page.evaluate(f"({CUT_JS})", [selector, spills])

    def snapshot(self) -> dict:
        return self.page.evaluate("import('/static/js/link.js').then(m => m.town.value)") or {}

    def deselect(self) -> None:
        for _ in range(3):
            if not self.page.locator(".gui-full, section.gui-card").count():
                return
            self.page.evaluate("document.activeElement && document.activeElement.blur()")  # a terminal keeps Esc
            self.page.keyboard.press("Escape")
            self.wait(300)

    # -- one building, three ways --------------------------------------------------------------------

    def building(self, b: Building, map_shot: Shot) -> None:
        page, hut = self.page, self.page.locator(f'.gui-hut[data-id="{b.id}"]')
        slug = re.sub(r"[^a-z0-9]+", "-", f"{b.orkspace}-{b.id}".lower())
        self.step = f"{b.title} · closed"
        body = self.text(f'.gui-hut[data-id="{b.id}"] .ok-hut__card')
        if not body:
            b.problems.append({"level": "warn", "view": "closed", "text": "the card is empty"})
        for c in self.cut(f'.gui-hut[data-id="{b.id}"] .ok-hut__card', spills=True):
            b.problems.append({"level": "warn", "view": "closed", "text": f"text {c['kind']}: “{c['text']}”"})
        b.closed.append(self.shot(f"{slug}-closed.png", "Closed: the card", hut))
        page.evaluate("id => document.querySelector(`.gui-hut[data-id=\"${id}\"]`).style.outline ="
                      " '2px solid #e8b94a'", b.id)
        b.closed.append(self.shot(f"{slug}-map.jpg", f"Closed: on the map of {b.orkspace}"))
        page.evaluate("id => document.querySelector(`.gui-hut[data-id=\"${id}\"]`).style.outline = ''", b.id)

        self.step = f"{b.title} · command"
        hut.locator(".gui-hut__title").click()
        try:
            page.wait_for_selector("section.gui-card", timeout=5000)
        except Exception:
            b.problems.append({"level": "error", "view": "command", "text": "the Command Card did not open"})
        self.wait()
        preview = self.text(".gui-card__preview")
        if not preview:
            b.problems.append({"level": "warn", "view": "command", "text": "no preview in the Command Card"})
        for c in self.cut(".gui-card__preview"):
            b.problems.append({"level": "warn", "view": "command", "text": f"preview: text {c['kind']}: “{c['text']}”"})
        b.command.append(self.shot(f"{slug}-command.jpg", "Command: selected — Info, garrison, Command Card"))

        self.step = f"{b.title} · full"
        hut.locator(".gui-hut__title").click()
        try:
            page.wait_for_selector(".gui-full", timeout=5000)
        except Exception:
            b.problems.append({"level": "error", "view": "full", "text": "the full window did not open"})
        self.wait(WAIT_MS + 600)
        full = self.text(".gui-full .gui-win__body")
        if len(full) < 20:
            b.problems.append({"level": "warn", "view": "full", "text": f"the window is (almost) empty: “{full[:60]}”"})
        for c in self.cut(".gui-full"):
            b.problems.append({"level": "warn", "view": "full", "text": f"text {c['kind']}: “{c['text']}”"})
        b.full.append(self.shot(f"{slug}-full.jpg", "Full: the window"))
        for view, text in (("command", preview), ("full", full), ("closed", body)):
            for m in sorted(set(WORDING.findall(text))):
                b.problems.append({"level": "warn", "view": view, "text": f"wording: “{m}” where a person reads"})
        self.deselect()

    # -- the town ------------------------------------------------------------------------------------

    def run(self, url: str) -> None:
        page = self.page
        page.goto(url)
        page.wait_for_selector(".gui-hut", timeout=30000)
        self.wait(2500)
        snap = self.snapshot()
        types = {b["id"]: b["type"] for b in snap.get("buildings", [])}
        names = [o["name"] for o in snap.get("orkspaces", [])]
        done: set[str] = set()
        for name in names:
            self.step = f"{name} · map"
            page.locator("nav.gui-warmap li.ok-item", has_text=name).first.click()
            self.wait()
            slug = re.sub(r"[^a-z0-9]+", "-", name.lower())
            self.g.maps.append(self.shot(f"map-{slug}.jpg", name))
            for hut in page.locator(".gui-hut").all():
                bid = hut.get_attribute("data-id")
                if bid in done:
                    continue
                done.add(bid)
                title = hut.locator(".gui-hut__title").inner_text().lstrip("0123456789 \n").strip()
                b = Building(bid, title, types.get(bid, "?"), name)
                self.g.buildings.append(b)
                self.building(b, self.g.maps[-1])
        self.lake()
        self.answers()

    def lake(self) -> None:
        page = self.page
        b = Building("lake", "Lake", "lake (window)", "the town")
        self.g.extras.append(b)
        for i, path in enumerate(LAKE_DOCS):
            self.step = f"Lake · {path}"
            page.evaluate("p => import('/static/js/lake.js').then(m => m.openInLake({path: p, title: p.split('/').pop()}))",
                          path)
            self.wait()
        try:
            page.wait_for_selector("section.gui-lake", timeout=5000)
        except Exception:
            b.problems.append({"level": "error", "view": "half", "text": "the Lake window did not open"})
            return
        if len(self.text("section.gui-lake")) < 20:
            b.problems.append({"level": "warn", "view": "half", "text": "the document is empty"})
        b.command.append(self.shot("lake-half.jpg", "Half: two documents in tabs"))
        full = page.locator("section.gui-lake .ok-win__bar button.ok-btn", has_text="Full")
        if full.count():
            full.first.click()
            self.wait()
            b.full.append(self.shot("lake-full.jpg", "Full"))
        close = page.locator("section.gui-lake .gui-win__close")
        if close.count():
            close.first.click()
            self.wait(400)

    def answers(self) -> None:
        page = self.page
        self.step = "Answers"
        b = Building("answers", "Answers", "the orks' questions", "the town")
        self.g.extras.append(b)
        page.locator(".gui-status__item", has_text="Answers").first.click()
        self.wait()
        if not re.search(r"\?", self.text("body")):
            b.problems.append({"level": "warn", "view": "dialog", "text": "no question shows"})
        b.full.append(self.shot("answers.jpg", "The questions that wait for the person"))
        page.keyboard.press("Escape")
        self.wait(300)


# -- the page ----------------------------------------------------------------------------------------

STYLE = """
/* The Office look of the GUI itself: its dark ground, amber for what to look at, red for what broke.
   Layout: a summary of the problems first, then one band per building, its three views side by side. */
:root {
  --ground: #1a1813; --panel: #221f18; --line: #3a3427; --text: #e8e0cc; --muted: #9a8f78;
  --accent: #e8b94a; --danger: #f5806e; --ok: #8fc46a;
  --display: "Titillium Web", "Segoe UI", system-ui, sans-serif; --mono: "JetBrains Mono", ui-monospace, monospace;
  color-scheme: dark;
}
* { box-sizing: border-box; }
body { background: var(--ground); color: var(--text); font: 15px/1.5 var(--display); margin: 0; }
.wrap { max-width: 1680px; margin: 0 auto; padding-inline: 24px; padding-block: 28px 64px; }
h1 { font-size: 30px; font-weight: 700; margin: 0; letter-spacing: .01em; text-wrap: balance; }
h2 { font-size: 21px; font-weight: 600; margin: 0; text-wrap: balance; }
h3 { font-size: 12px; text-transform: uppercase; letter-spacing: .1em; color: var(--muted); margin: 0; font-weight: 600; }
.lede { color: var(--muted); max-width: 70ch; margin: 6px 0 0; }
code, .mono { font-family: var(--mono); font-size: 12.5px; }
.summary { display: grid; grid-template-columns: repeat(auto-fit, minmax(min(100%, 420px), 1fr)); gap: 16px; margin-block: 24px 32px; }
.box { background: var(--panel); border: 1px solid var(--line); border-radius: 4px; padding: 14px 16px; min-width: 0; }
.box ul { margin: 8px 0 0; padding-left: 18px; }
.box li { margin-block: 3px; overflow-wrap: anywhere; }
.counts { display: flex; flex-wrap: wrap; gap: 8px 18px; margin-top: 8px; font-variant-numeric: tabular-nums; }
.counts b { font-size: 22px; }
.nav { display: flex; flex-wrap: wrap; gap: 6px; margin-block: 0 28px; }
.chip { font: 13px var(--display); color: var(--text); text-decoration: none; border: 1px solid var(--line);
        border-radius: 999px; padding: 2px 10px; background: var(--panel); }
.chip:hover, .chip:focus-visible { border-color: var(--accent); outline: none; }
.chip .n { color: var(--accent); font-family: var(--mono); font-size: 11.5px; margin-left: 4px; }
.chip.bad .n { color: var(--danger); }
.ork { margin-block: 36px 8px; padding-bottom: 6px; border-bottom: 1px solid var(--line); color: var(--accent); }
section.b { padding-block: 18px; border-bottom: 1px solid var(--line); scroll-margin-top: 12px; }
.head { display: flex; flex-wrap: wrap; align-items: baseline; gap: 4px 12px; }
.type { color: var(--muted); }
.views { display: grid; grid-template-columns: minmax(0, .8fr) minmax(0, 1fr) minmax(0, 1fr); gap: 16px; margin-top: 12px; }
@media (max-width: 1000px) { .views { grid-template-columns: minmax(0, 1fr); } }
figure { margin: 0; display: grid; gap: 6px; align-content: start; min-width: 0; }
figure + figure { margin-top: 10px; }
figure img { width: 100%; height: auto; border: 1px solid var(--line); border-radius: 3px; cursor: zoom-in; background: #000; }
figure img.card { width: auto; max-width: 100%; }
figcaption { color: var(--muted); font-size: 13px; }
.problems { margin: 10px 0 0; padding: 0; list-style: none; display: grid; gap: 4px; }
.problems li { font-size: 13.5px; padding-left: 10px; border-left: 3px solid var(--accent); overflow-wrap: anywhere; }
.problems li.error { border-color: var(--danger); }
.problems li.eye { border-color: var(--muted); }
.problems .v { font-family: var(--mono); font-size: 11.5px; color: var(--muted); margin-right: 6px; }
.clean { color: var(--ok); font-size: 13.5px; margin-top: 10px; }
.maps { display: grid; grid-template-columns: repeat(auto-fit, minmax(min(100%, 320px), 1fr)); gap: 12px; }
dialog { border: 0; padding: 0; background: transparent; max-width: 96vw; max-height: 96vh; }
dialog::backdrop { background: rgb(0 0 0 / .82); }
dialog img { max-width: 96vw; max-height: 92vh; display: block; cursor: zoom-out; }
"""

SCRIPT = """
const d = document.getElementById('zoom'), big = d.querySelector('img');
document.addEventListener('click', (e) => {
  const img = e.target.closest('figure img');
  if (img) { big.src = img.src; big.alt = img.alt; d.showModal(); }
  else if (e.target.closest('dialog')) d.close();
});
"""


def _esc(text: str) -> str:
    return html.escape(str(text), quote=True)


def _figure(s: Shot, card: bool = False) -> str:
    cls = ' class="card"' if card else ""
    return (f'<figure><img{cls} src="{_esc(s.file)}" alt="{_esc(s.caption)}" loading="lazy">'
            f'<figcaption>{_esc(s.caption)}</figcaption></figure>')


def _anchor(b: Building) -> str:
    return re.sub(r"[^a-z0-9]+", "-", f"{b.orkspace}-{b.id}".lower()).strip("-")


def _section(b: Building) -> str:
    cols = []
    for label, shots in (("closed", b.closed), ("command", b.command), ("full", b.full)):
        if shots:
            figs = "".join(_figure(s, card=label == "closed" and i == 0 and s.file.endswith(".png"))
                           for i, s in enumerate(shots))
            cols.append(f'<div><h3>{label}</h3>{figs}</div>')
    probs = "".join(f'<li class="{_esc(p["level"])}"><span class="v">{_esc(p["view"])}</span>{_esc(p["text"])}</li>'
                    for p in b.problems)
    tail = f'<ul class="problems">{probs}</ul>' if probs else '<p class="clean">Nothing found by the checks.</p>'
    return (f'<section class="b" id="{_anchor(b)}"><div class="head"><h2>{_esc(b.title)}</h2>'
            f'<span class="type mono">{_esc(b.type)} · <code>{_esc(b.id)}</code></span></div>'
            f'<div class="views">{"".join(cols)}</div>{tail}</section>')


def render(g: Gallery) -> str:
    everyone = g.buildings + g.extras
    n_warn = sum(1 for b in everyone for p in b.problems if p["level"] == "warn")
    n_eye = sum(1 for b in everyone for p in b.problems if p["level"] == "eye")
    n_err = sum(1 for b in everyone for p in b.problems if p["level"] == "error") + len(g.errors)
    chips = "".join(
        f'<a class="chip{" bad" if any(p["level"] == "error" for p in b.problems) else ""}" href="#{_anchor(b)}">'
        f'{_esc(b.title)}{f"<span class=n>{len(b.problems)}</span>" if b.problems else ""}</a>' for b in everyone)
    errs = "".join(f'<li><span class="mono">{_esc(e["kind"])}</span> at <b>{_esc(e["at"])}</b>: '
                   f'<code>{_esc(e["text"])}</code></li>' for e in g.errors) or "<li>None.</li>"
    found = [(b, p) for b in everyone for p in b.problems]
    probs = "".join(f'<li><a class="chip" href="#{_anchor(b)}">{_esc(b.title)}</a> <span class="mono">{_esc(p["view"])}</span>'
                    f' {_esc(p["text"])}</li>' for b, p in found) or "<li>None.</li>"
    body, last = [], None
    for b in g.buildings:
        if b.orkspace != last:
            body.append(f'<h3 class="ork">{_esc(b.orkspace)}</h3>')
            last = b.orkspace
        body.append(_section(b))
    body.append('<h3 class="ork">The town’s windows</h3>')
    body += [_section(b) for b in g.extras]
    maps = "".join(_figure(s) for s in g.maps)
    return f"""<title>Orkcraft Building Gallery</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;700&family=Titillium+Web:wght@400;600;700&display=swap">
<style>{STYLE}</style>
<div class="wrap">
<h1>Orkcraft Building Gallery</h1>
<p class="lede">Every building of <code>orkcraft gui --demo</code> three ways — closed, command, full
(<code>docs/design/building-views.md</code>) — taken {_esc(g.made)} in the Office look at {VIEWPORT[0]}×{VIEWPORT[1]}.
Click a picture to see it full size.</p>
<div class="summary">
  <div class="box"><h3>Found</h3><div class="counts"><span><b>{len(g.buildings)}</b> buildings</span>
    <span><b>{n_err}</b> errors</span><span><b>{n_warn}</b> found by the checks</span>
    <span><b>{n_eye}</b> seen by eye</span></div>
    <ul>{probs}</ul></div>
  <div class="box"><h3>Page and console errors</h3><ul>{errs}</ul></div>
</div>
<nav class="nav" aria-label="Buildings">{chips}</nav>
<h3>Workspaces (orkspaces)</h3>
<div class="maps">{maps}</div>
{"".join(body)}
</div>
<dialog id="zoom" aria-label="Picture at full size"><img alt=""></dialog>
<script>{SCRIPT}</script>
"""


def add_notes(g: Gallery, notes: dict[str, list[str]]) -> None:
    """What a person saw in the pictures, with each building's problems (`view: text` or text)."""
    for b in g.buildings + g.extras:
        for note in notes.get(b.id, []):
            view, sep, text = note.partition(": ")
            b.problems.append({"level": "eye", "view": view if sep else "seen", "text": text if sep else note})


def report(g: Gallery) -> dict:
    return dataclasses.asdict(g)


def launch(p, chromium: str = ""):
    """Chromium: the one asked for, Playwright's own, else any under PLAYWRIGHT_BROWSERS_PATH (an older
    build than this Playwright wants still drives a page)."""
    if chromium:
        return p.chromium.launch(executable_path=chromium)
    try:
        return p.chromium.launch()
    except Exception:
        found = sorted(Path(os.environ.get("PLAYWRIGHT_BROWSERS_PATH") or "/opt/pw-browsers").glob(
            "chromium-*/chrome-linux*/chrome"))
        if not found:
            raise
        return p.chromium.launch(executable_path=str(found[-1]))


# -- main --------------------------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--out", type=Path, default=ROOT / "gallery", help="where the page and its pictures go")
    ap.add_argument("--demo", type=Path, default=None, help="the demo's folder (default: a temporary one)")
    ap.add_argument("--notes", type=Path, default=None,
                    help="JSON {building id: [what a person saw]}: findings by eye, shown with the checks'")
    ap.add_argument("--chromium", default=os.environ.get("ORKCRAFT_CHROMIUM", ""),
                    help="a Chromium to drive (default: Playwright's own)")
    args = ap.parse_args(argv)
    from playwright.sync_api import sync_playwright

    out = args.out.resolve()
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    demo_dir = args.demo or Path(tempfile.mkdtemp(prefix="orkcraft-gallery-")) / "demo"
    g = Gallery(dt.datetime.now().strftime("%Y-%m-%d %H:%M"))
    proc, url = start_gui(demo_dir, free_port(), out / "gui.log")
    g.url = url.split("?")[0]
    try:
        with sync_playwright() as p:
            browser = launch(p, args.chromium)
            page = browser.new_page(viewport={"width": VIEWPORT[0], "height": VIEWPORT[1]})
            Walk(page, out, g).run(url)
            browser.close()
    finally:
        proc.terminate()
        try:
            proc.wait(10)
        except subprocess.TimeoutExpired:
            proc.kill()
    if args.notes:
        add_notes(g, json.loads(args.notes.read_text(encoding="utf-8")))
    (out / "index.html").write_text(render(g), encoding="utf-8")
    (out / "report.json").write_text(json.dumps(report(g), ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    problems = sum(len(b.problems) for b in g.buildings + g.extras)
    print(f"{out / 'index.html'}: {len(g.buildings)} buildings, {len(g.errors)} page errors, {problems} problems")
    return 0


if __name__ == "__main__":
    sys.exit(main())
