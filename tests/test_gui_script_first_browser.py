"""Script-first buildings in a real browser, on the dashboard demo (docs/design/script-first.md §5): the
steward's window says a building's work is code — no model, its ork wakes on an error or a 👎 — or what in it
thinks on its carts; Info's spend says *no model*; a 👎 wakes its ork, and the window says when.

Skipped where Playwright or Chromium is missing; `-m browser` runs these alone."""
from __future__ import annotations

import os
from pathlib import Path

import pytest

playwright = pytest.importorskip("playwright.sync_api")

from orkcraft import demo  # noqa: E402
from orkcraft.gui.host import Host  # noqa: E402
from orkcraft.gui.server import Server  # noqa: E402

pytestmark = pytest.mark.browser

CHROMIUM = [p for p in (os.environ.get("ORKCRAFT_CHROMIUM", ""), "/opt/pw-browsers/chromium") if p and Path(p).exists()]
WAIT_MS = 10_000


def _launch(p):
    return p.chromium.launch(executable_path=CHROMIUM[0]) if CHROMIUM else p.chromium.launch()


def _can_launch() -> bool:
    try:
        with playwright.sync_playwright() as p:
            _launch(p).close()
        return True
    except Exception:
        return False


if not _can_launch():
    pytest.skip("no Chromium for Playwright here", allow_module_level=True)


@pytest.fixture(scope="module")
def browser():
    """One Chromium for the module, launched before a test's fixtures move XDG_CACHE_HOME (conftest.py):
    Playwright finds its browsers under it."""
    pw = playwright.sync_playwright().start()
    chromium = _launch(pw)
    yield chromium
    chromium.close()
    pw.stop()


@pytest.fixture
def demo_page(tmp_path, browser):
    """The dashboard demo served and open in Chromium; every page error it logged fails the test."""
    root = demo.build(tmp_path / "demo", set_name="dashboard")
    server = Server(Host(root, False, root / ".orkcraft.json", demo=True))
    thread = server.start_thread()
    pg = browser.new_page(viewport={"width": 1440, "height": 900})
    errors: list[str] = []
    pg.on("pageerror", lambda e: errors.append(f"pageerror: {e}"))
    pg.on("console", lambda m: m.type == "error" and errors.append(f"console: {m.text}"))
    pg.goto(server.url)
    pg.wait_for_selector(".gui-warchief__face", timeout=WAIT_MS)
    try:
        yield pg
    finally:
        pg.close()
        server.stop()
        thread.join(10)
    assert not errors, "\n".join(errors)


def _call(pg, name: str, args: dict):
    return pg.evaluate("([n, a]) => import('/static/js/link.js').then(m => m.command(n, a))", [name, args])


def _open_info(pg, bid: str) -> None:
    hut = pg.locator(f'.gui-hut[data-id="{bid}"]')
    hut.wait_for(state="visible", timeout=WAIT_MS)
    hut.locator(".gui-hut__title").click()
    pg.locator(".gui-panel").wait_for(state="visible", timeout=WAIT_MS)
    pg.locator(".gui-panel__tabs .ok-tab", has_text="Info").click()
    pg.locator(".gui-panel .gui-info").first.wait_for(state="visible", timeout=WAIT_MS)


def test_a_script_first_building_says_so_and_a_thumbs_down_wakes_its_ork(demo_page):
    pg = demo_page
    _call(pg, "orkspace.select", {"id": "gates"})
    _open_info(pg, "gate_pit")
    line = pg.locator(".gui-steward__script-first")
    line.wait_for(state="visible", timeout=WAIT_MS)
    text = line.inner_text()
    assert "Script-first" in text and "no model" in text and "wakes on an error or a 👎" in text
    assert "is-on" in (line.get_attribute("class") or "")
    assert "no model" in pg.locator(".gui-panel .gui-info").first.inner_text()       # Info's spend line
    if os.environ.get("ORKCRAFT_SHOTS"):           # a look for a person: ORKCRAFT_SHOTS=<folder>
        pg.screenshot(path=str(Path(os.environ["ORKCRAFT_SHOTS"]) / "script-first-pit.png"))

    _call(pg, "building.dislike", {"id": "gate_pit", "kind": "logic", "note": "it took my JSON for text"})
    pg.wait_for_function("() => [...document.querySelectorAll('.gui-steward__script-first')]"
                         ".some(e => /woke \\d\\d:\\d\\d on a 👎/.test(e.textContent))", timeout=WAIT_MS * 2)
    pg.keyboard.press("Escape")
    pg.keyboard.press("Escape")

    _open_info(pg, "notes_mill")                 # the Release notes Transformer has an `agent:` step: it thinks
    line = pg.locator(".gui-steward__script-first")
    line.wait_for(state="visible", timeout=WAIT_MS)
    assert "Thinks on its carts" in line.inner_text() and "agent: step 3" in line.inner_text()
    assert "is-on" not in (line.get_attribute("class") or "")


def test_a_yard_shows_no_ork_of_its_own_and_a_hut_does(demo_page):
    """docs/design/yards.md §2: a building whose work is code is a yard; its card has no ork head until one
    visits. The Task board's work is its orks', so its head stays."""
    pg = demo_page
    _call(pg, "orkspace.select", {"id": "my_day"})
    yard = pg.locator('.gui-hut[data-id="drop"]')
    hut = pg.locator('.gui-hut[data-id="todo"]')
    yard.wait_for(state="visible", timeout=WAIT_MS)
    assert "is-yard" in (yard.get_attribute("class") or "")
    assert yard.locator(".gui-hut__keeper").count() == 0
    assert "is-yard" not in (hut.get_attribute("class") or "")
    assert hut.locator(".gui-hut__keeper").count() == 1


def test_a_yard_is_fenced_and_the_ork_that_asks_stands_in_its_gate(demo_page):
    """docs/design/yards.md §3–§4 in Camp: a yard's name stands over its building, which stands on its title bar —
    a picket fence; a hut says what its orks do over its roof; the ork that asks comes out by the door, and a press
    on it opens its question."""
    pg = demo_page
    _call(pg, "orkspace.select", {"id": "my_day"})
    calendar = pg.locator('.gui-hut[data-id="days"]')
    calendar.wait_for(state="visible", timeout=WAIT_MS)
    assert calendar.locator(".gui-hut__yard-title").inner_text().strip().lower() == "calendar"
    assert calendar.locator(".gui-hut__caller").count() == 0                # nobody asks: nobody out by the door
    assert not calendar.locator(".gui-hut__name").is_visible()            # the name left the title bar
    assert pg.locator('.gui-hut[data-id="todo"] .gui-hut__doing').is_visible()   # a hut: Zz or a wheel on its roof
    assert calendar.locator(".gui-hut__doing").count() == 0               # a yard: nobody lives in it

    _call(pg, "orkspace.select", {"id": "agent_yard"})
    caller = pg.locator('.gui-hut[data-id="outputs"] .ok-head .gui-hut__caller')   # the Review gate's ork asks
    caller.wait_for(state="visible", timeout=WAIT_MS)
    caller.click()
    dialog = pg.locator(".ok-dialog", has_text="Awaiting an answer")
    dialog.wait_for(state="visible", timeout=WAIT_MS)
    assert "carts wait" in dialog.inner_text()
    if os.environ.get("ORKCRAFT_SHOTS"):
        pg.screenshot(path=str(Path(os.environ["ORKCRAFT_SHOTS"]) / "yards-caller.png"))


def test_the_road_gate_comes_where_the_mouse_nears_the_edge_and_the_corner_resizes(demo_page):
    """docs/design/yards.md §3g: near a card's edge the road handle — a small gate — stands under the mouse, a road is
    pulled out of it there; inside the card and at the corner, which resizes, it is gone."""
    pg = demo_page
    _call(pg, "orkspace.select", {"id": "my_day"})
    hut = pg.locator('.gui-hut[data-id="drop"]')
    hut.wait_for(state="visible", timeout=WAIT_MS)
    card = hut.locator(".ok-hut__card").bounding_box()
    gate = hut.locator(".gui-hut__road")
    y = card["y"] + card["height"] / 2
    pg.mouse.move(card["x"] + 3, y)
    pg.wait_for_function("() => document.querySelector('.gui-hut[data-id=\"drop\"] .gui-hut__road').classList.contains('is-at')",
                         timeout=WAIT_MS)
    g = gate.bounding_box()
    assert abs(g["x"] + g["width"] / 2 - card["x"]) < 4 and abs(g["y"] + g["height"] / 2 - y) < 4   # on the left edge, here
    pg.mouse.move(card["x"] + card["width"] / 2, y)                                              # inside: no gate
    assert "is-at" not in (gate.get_attribute("class") or "")
    pg.mouse.move(card["x"] + card["width"] - 4, card["y"] + card["height"] - 4)                  # the corner resizes
    assert "is-at" not in (gate.get_attribute("class") or "")
    assert hut.locator(".gui-hut__grip").count() == 1                                             # the corner alone
