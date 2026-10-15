"""Every ork is drawn crisp (the owner, 15 October: the small orks looked smoothed): each ork image — a steward, the
Prospector pacing, the ork out of its door, the Task board's walkers, the Workchief's face in the HUD — has
`image-rendering: pixelated`, a box of whole device pixels, and no transform that scales it or moves it across a
device pixel, at every zoom step, on a 1× and a 2× screen. On a 2× screen an ork with a high-density cut
(tools/camp_hd.py) is drawn from it at one image pixel per device pixel: its box × the density is the image's own frame,
and it is smooth (`image-rendering: auto`), as nothing is resampled."""
from __future__ import annotations

import pytest

pytest.importorskip("playwright.sync_api")

from tests.test_gui_browser import WAIT_MS, gui  # noqa: E402,F401  (fixtures)

# the ork images on the page, and what in each would draw it across a device pixel
CHECK = r"""async () => {
  const d = devicePixelRatio, off = (v) => Math.abs(v * d - Math.round(v * d)) > 0.01, bad = [];
  const natural = (url) => new Promise((ok) => { const i = new Image(); i.onload = () => ok([i.naturalWidth, i.naturalHeight]);
    i.onerror = () => ok(null); i.src = url; });
  let n = 0, hd = 0;
  for (const e of document.querySelectorAll('img, span, i')) {
    const cs = getComputedStyle(e);
    const src = (e.tagName === 'IMG' ? e.currentSrc || e.src : '') + ' ' + cs.backgroundImage;
    if (!/\/orks\/|\/faces\//.test(src) || !e.offsetWidth) continue;
    n += 1;
    const what = `${e.className} ${(src.match(/[\w@-]+\.png/) || [''])[0]}`;
    const w = parseFloat(cs.width), h = parseFloat(cs.height);
    if (off(w) || off(h)) bad.push(`${what}: ${w} x ${h}`);
    if (/@hd/.test(src)) {                                 // one image px on one device px
      hd += 1;
      if (d < 2) bad.push(`${what}: a high-density cut on a ${d}x screen`);
      if (cs.imageRendering !== 'auto') bad.push(`${what}: image-rendering ${cs.imageRendering}`);
      const nat = await natural(src.match(/url\("?([^")]+)"?\)/)[1]);
      const frames = nat ? Math.round(nat[0] / (w * d)) : 0;
      if (!nat || Math.abs(nat[1] - h * d) > 0.01 || Math.abs(nat[0] - frames * w * d) > 0.01)
        bad.push(`${what}: box ${w} x ${h} at ${d}x, image ${nat}`);
    } else if (cs.imageRendering !== 'pixelated') bad.push(`${what}: image-rendering ${cs.imageRendering}`);
    for (let a = e; a; a = a.parentElement) {
      const t = getComputedStyle(a).transform;
      if (t === 'none') continue;
      const m = new DOMMatrixReadOnly(t);
      if (Math.abs(Math.abs(m.a) - 1) > 1e-6 || Math.abs(Math.abs(m.d) - 1) > 1e-6 || m.b || m.c || off(m.e) || off(m.f))
        bad.push(`${what}: ${a.className} ${t}`);
    }
  }
  return { n, hd, bad };
}"""


def _camp(pg, server):
    pg.goto(server.url)
    pg.wait_for_selector(".gui-warchief__face", timeout=WAIT_MS)
    pg.evaluate("() => import('/static/js/link.js').then(m => m.command('you.look', { look: 'camp' }))")
    pg.wait_for_function("() => document.documentElement.dataset.look === 'camp'", timeout=WAIT_MS)


@pytest.mark.parametrize("dpr", [1, 2])
def test_every_ork_lands_on_whole_device_pixels_at_every_zoom_step(gui, dpr):
    server, browser = gui
    pg = browser.new_page(viewport={"width": 1440, "height": 900}, device_scale_factor=dpr)
    call = lambda name, args: pg.evaluate("([n, a]) => import('/static/js/link.js').then(m => m.command(n, a))", [name, args])
    built = []
    try:
        _camp(pg, server)
        built += [call("town.build", {"type": t}) for t in ("fields", "mine")]   # a steward waiting; the Prospector pacing
        pg.keyboard.press("Escape")
        pg.wait_for_selector(".gui-camp__ork.is-pacing", timeout=WAIT_MS)
        for level in ("b", "bc", "c", "a"):
            pg.evaluate("l => import('/static/js/zoom.js').then(z => { z.zoomLevel.value = l; })", level)
            pg.wait_for_timeout(400)
            house = pg.locator(f'.gui-camp__building[data-id="{built[0]}"]')
            if level != "a" and house.is_visible():
                house.hover()                                                     # its steward out of the door
                pg.wait_for_timeout(700)
            for _ in range(3):                                                    # mid-move as well as at rest
                got = pg.evaluate(CHECK)
                assert got["n"] >= 3, (level, got)
                assert not got["bad"], (dpr, level, got["bad"])
                if dpr == 2 and level != "a":                                     # ×1, ×1.5, ×2: from the cut
                    assert got["hd"] >= 2, (level, got)
                pg.wait_for_timeout(230)
            pg.mouse.move(2, 450)
        pg.evaluate("l => import('/static/js/zoom.js').then(z => { z.zoomLevel.value = l; })", "b")
        board = pg.locator(f'.gui-camp__building[data-id="{built[0]}"]')
        board.click()                                                             # selected, then entered: its walkers
        pg.locator(f'.gui-camp__scroll.is-grown[data-id="{built[0]}"]').wait_for(state="visible", timeout=WAIT_MS)
        board.click()
        pg.wait_for_selector(".fields-in__ork .fields-in__body", timeout=WAIT_MS)
        pg.wait_for_timeout(500)
        got = pg.evaluate(CHECK)
        assert not got["bad"], (dpr, "inside", got["bad"])
        assert (got["hd"] > 0) == (dpr == 2), (dpr, "inside", got)
    finally:
        for bid in built:
            call("town.demolish", {"id": bid})
        pg.evaluate("() => import('/static/js/link.js').then(m => m.command('you.look', { look: 'office' }))")
        pg.wait_for_function("() => document.documentElement.dataset.look === 'office'", timeout=WAIT_MS)   # the module's look again
        pg.close()
