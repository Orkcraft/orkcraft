"""✅ The Alchemist's look check (docs/design/check.md §12): every building's window in the dashboard demo, as the person
would see it, kept as a picture and held against the last check's — a window that changed is shown to a judge (the
cheap AI tool, reading both pictures) that says whether it is broken: cut text, things on top of each other, an empty
or unreadable window. It needs Playwright and a Chromium (`pip install "orkcraft[browser]"`, `playwright install
chromium`); without them it says so and checks nothing.

    look_check.capture(folder)                         {"windows": [ids], "error": ""}: <folder>/<id>.png each
    look_check.compare(before, after)                  {id: share of its pixels that changed} (1.0: new, or resized)
"""
from __future__ import annotations

import base64
import contextlib
import os
import tempfile
from pathlib import Path

CHROMIUM = ("/opt/pw-browsers/chromium",)          # a Chromium this machine has (else Playwright's own)
VIEW = {"width": 1440, "height": 900}
WAIT_MS = 10_000
CHANGED = 0.02                                     # a window whose pixels moved more than this share is changed
STILL = "*, *::before, *::after { animation: none !important; transition: none !important; caret-color: transparent !important; }"
_ENV = {"ORKCRAFT_ONBOARDING": "0", "ORKCRAFT_LIMITS": "0", "ORKCRAFT_COUNCIL_LLM": "0", "ORKCRAFT_WIKI_AUTO": "0",
        "ORKCRAFT_NIGHT_ROUND": "0", "ORKCRAFT_LOOK": "camp"}


def available() -> str:
    """"" when windows can be pictured here, else what is missing."""
    try:
        import playwright.sync_api  # noqa: F401
    except ImportError:
        return 'it needs Playwright: pip install "orkcraft[browser]", then playwright install chromium'
    return ""


def _launch(p):
    exe = os.environ.get("ORKCRAFT_CHROMIUM") or next((c for c in CHROMIUM if Path(c).exists()), "")
    return p.chromium.launch(executable_path=exe) if exe else p.chromium.launch()


@contextlib.contextmanager
def _demo_env(tmp: Path):
    """The demo town's own home, settings and layout, never the person's; put back after."""
    values = {**_ENV, "ORKCRAFT_HOME": str(tmp / "home"), "ORKCRAFT_LAYOUT_FILE": str(tmp / "layout.json"),
              "ORKCRAFT_SETTINGS_FILE": str(tmp / "settings.json"), "ORKCRAFT_CALENDARS_FILE": str(tmp / "calendars.json")}
    old = {k: os.environ.get(k) for k in values}
    os.environ.update(values)
    try:
        yield
    finally:
        for k, v in old.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def capture(folder: Path) -> dict:
    """The dashboard demo opened in a headless Chromium, each building's window (its Work) pictured in `folder`."""
    missing = available()
    if missing:
        return {"windows": [], "error": missing}
    from playwright.sync_api import sync_playwright
    folder.mkdir(parents=True, exist_ok=True)
    shot: list[str] = []
    with tempfile.TemporaryDirectory(prefix="orkcraft-looks-") as tmp, _demo_env(Path(tmp)):
        from orkcraft import demo
        from orkcraft.gui.host import Host
        from orkcraft.gui.server import Server
        root = demo.build(Path(tmp) / "town", set_name="dashboard")
        server = Server(Host(root, auto_commit=False))
        thread = server.start_thread()
        try:
            with sync_playwright() as p:
                browser = _launch(p)
                page = browser.new_page(viewport=VIEW)
                page.goto(server.url)
                page.wait_for_selector(".gui-hut", timeout=WAIT_MS)
                page.add_style_tag(content=STILL)
                ids = page.evaluate("() => [...document.querySelectorAll('.gui-hut[data-id]')].map(h => h.dataset.id)")
                for bid in dict.fromkeys(ids):
                    try:
                        page.evaluate("id => import('/static/js/windows.js').then(m => m.openBuilding(id, 'work'))", bid)
                        panel = page.locator(".gui-panel")
                        panel.wait_for(state="visible", timeout=WAIT_MS)
                        page.wait_for_timeout(500)                   # what it fetched, drawn
                        panel.screenshot(path=str(folder / f"{bid}.png"), animations="disabled")
                        shot.append(bid)
                        page.keyboard.press("Escape")
                        panel.wait_for(state="hidden", timeout=WAIT_MS)
                    except Exception:  # one window that does not open is left out, the others still pictured
                        page.keyboard.press("Escape")
                browser.close()
        finally:
            server.stop()
            thread.join(10)
    return {"windows": shot, "error": ""}


def compare(before: Path, after: Path) -> dict[str, float]:
    """Each window pictured in `after`: the share of its pixels that differ from `before`'s (1.0 when it is new or its
    size changed, 0.0 when the files are the same); measured in a headless Chromium, which reads the pictures."""
    out: dict[str, float] = {}
    pairs = []
    for img in sorted(after.glob("*.png")):
        old = before / img.name
        if not old.is_file():
            out[img.stem] = 1.0
        elif old.read_bytes() == img.read_bytes():
            out[img.stem] = 0.0
        else:
            pairs.append(img)
    if not pairs or available():
        for img in pairs:
            out[img.stem] = 1.0
        return out
    from playwright.sync_api import sync_playwright
    url = lambda p: "data:image/png;base64," + base64.b64encode(p.read_bytes()).decode()  # noqa: E731
    js = """async ([a, b]) => {
      const load = (src) => new Promise((ok) => { const i = new Image(); i.onload = () => ok(i); i.src = src; });
      const [x, y] = [await load(a), await load(b)];
      if (x.width !== y.width || x.height !== y.height) return 1;
      const px = (img) => { const c = document.createElement('canvas'); c.width = img.width; c.height = img.height;
        const g = c.getContext('2d'); g.drawImage(img, 0, 0); return g.getImageData(0, 0, img.width, img.height).data; };
      const [p, q] = [px(x), px(y)];
      let moved = 0;
      for (let k = 0; k < p.length; k += 4) {
        if (Math.abs(p[k] - q[k]) + Math.abs(p[k + 1] - q[k + 1]) + Math.abs(p[k + 2] - q[k + 2]) > 48) moved++;
      }
      return moved / (p.length / 4);
    }"""
    with sync_playwright() as p:
        browser = _launch(p)
        page = browser.new_page()
        for img in pairs:
            out[img.stem] = round(float(page.evaluate(js, [url(before / img.name), url(img)])), 4)
        browser.close()
    return out


def judge_prompt(window: str) -> str:
    return f"""Two pictures of the window of the building `{window}` in an app are in this folder: `before.png` (as it
was) and `after.png` (as it is now, after a change in the code). Look at `after.png`, with `before.png` to compare.
Is it broken: text cut off or overflowing, things drawn on top of each other, a part gone that was there, an empty or
unreadable window, colours that make text hard to read? A deliberate change that reads well is not broken.
Answer with JSON only: {{"broken": true|false, "score": 0-10 (10: reads as well as or better than before), "notes": "what you see"}}"""

