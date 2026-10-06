"""The GUI in a real browser (Chromium through Playwright): the town on a fresh project, every type of the
catalog raised through Build and looked at three ways — closed (its card on the town), command (selected:
Info, the garrison and the Commands window) and full (its whole window) — plus the Lake window and the
Town Hall (docs/design/building-views.md). Each must draw, and the page must log no error.

Skipped where Playwright or Chromium is missing; `-m browser` runs these alone, `-m "not browser"` leaves
them out."""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

playwright = pytest.importorskip("playwright.sync_api")

from orkcraft.gui import builder  # noqa: E402
from orkcraft.gui.host import Host  # noqa: E402
from orkcraft.gui.server import Server  # noqa: E402
from orkcraft.realm import checkpoint  # noqa: E402
from orkcraft.realm.buildings import TOWN_HALL  # noqa: E402

pytestmark = pytest.mark.browser

CHROMIUM = [p for p in (os.environ.get("ORKCRAFT_CHROMIUM", ""), "/opt/pw-browsers/chromium") if p and Path(p).exists()]
TYPES = [t["id"] for t in builder.catalog_types()]
WAIT_MS = 10_000


def _launch(p):
    """Chromium as this machine has it: the preinstalled one, else Playwright's own."""
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
def gui(tmp_path_factory):
    """One project, its host and server, one browser for the module (the same settings as `isolated_layout_file`)."""
    tmp = tmp_path_factory.mktemp("gui")
    pw = playwright.sync_playwright().start()
    browser = _launch(pw)                       # before XDG_CACHE_HOME moves: Playwright finds its Chromium under it
    mp = pytest.MonkeyPatch()
    for key, value in {"ORKCRAFT_LAYOUT_FILE": tmp / "layout.json", "ORKCRAFT_SETTINGS_FILE": tmp / "settings.json",
                       "ORKCRAFT_CALENDARS_FILE": tmp / "calendars.json", "XDG_CACHE_HOME": tmp / "cache",
                       "ORKCRAFT_ONBOARDING": "0", "ORKCRAFT_LIMITS": "0", "ORKCRAFT_COUNCIL_LLM": "0",
                       "ORKCRAFT_WIKI_AUTO": "0"}.items():
        mp.setenv(key, str(value))
    repo = tmp / "project"
    (repo / "src").mkdir(parents=True)
    (repo / "README.md").write_text("# Demo project\n\nA small project for the browser check.\n", encoding="utf-8")
    (repo / "src" / "app.py").write_text("print('hello')\n", encoding="utf-8")
    git = ["git", "-c", "user.email=test@orkcraft.local", "-c", "user.name=Test Runner"]
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run([*git, "add", "-A"], cwd=repo, check=True)
    subprocess.run([*git, "commit", "-qm", "init"], cwd=repo, check=True)
    checkpoint.ensure(repo)
    server = Server(Host(repo, auto_commit=False))
    thread = server.start_thread()
    yield server, browser
    browser.close()
    pw.stop()
    server.stop()
    thread.join(10)
    mp.undo()


@pytest.fixture
def page(gui):
    """The town in a fresh tab; after the test, every page error and console error it logged fails it."""
    server, browser = gui
    pg = browser.new_page(viewport={"width": 1440, "height": 900})
    errors: list[str] = []
    pg.on("pageerror", lambda e: errors.append(f"pageerror: {e}"))
    pg.on("console", lambda m: m.type == "error" and errors.append(f"console: {m.text}"))
    pg.goto(server.url)
    pg.wait_for_selector(".gui-advisor__face", timeout=WAIT_MS)   # Office: the Control panel is the advisor
    yield pg
    pg.wait_for_timeout(300)                    # what a refresh after the last step draws
    pg.close()
    assert not errors, "\n".join(errors)


def server_building(pg, bid: str) -> dict:
    """What the host's `info` says of a building now."""
    return pg.evaluate("id => import('/static/js/link.js').then(m => m.command('info', { id }))", bid)


def _hut(pg, bid: str):
    return pg.locator(f'.gui-hut[data-id="{bid}"]')


def _closed(pg, bid: str) -> None:
    hut = _hut(pg, bid)
    hut.wait_for(state="visible", timeout=WAIT_MS)
    assert hut.locator(".gui-hut__title").inner_text().strip()
    card = hut.locator(".ok-hut__card")
    assert card.is_visible() and card.bounding_box()["height"] > 0


def _command(pg) -> None:
    for c in (".gui-console", ".gui-roster", ".gui-card"):
        pg.locator(c).wait_for(state="visible", timeout=WAIT_MS)
    pg.locator(".gui-card .ok-act").first.wait_for(state="visible", timeout=WAIT_MS)
    pg.locator(".gui-console .gui-info").first.wait_for(state="visible", timeout=WAIT_MS)


def _full(pg, has_view: bool) -> None:
    full = pg.locator(".gui-full")
    full.wait_for(state="visible", timeout=WAIT_MS)
    assert full.locator(".ok-win__title").inner_text().strip()
    if has_view:                                # its detail came and its panes are laid out
        full.locator(".gui-win__body.is-view").wait_for(state="visible", timeout=WAIT_MS)
    assert full.locator(".gui-win__body").bounding_box()["height"] > 0


def _three_ways(pg, bid: str, has_view: bool = True) -> None:
    _closed(pg, bid)
    _hut(pg, bid).locator(".gui-hut__title").click()   # selected: Info, the garrison, Commands
    _command(pg)
    if has_view:
        pg.locator(".gui-card__preview").wait_for(state="visible", timeout=WAIT_MS)
    _hut(pg, bid).locator(".gui-hut__title").click()   # a click on the selected hut opens it
    _full(pg, has_view)
    pg.keyboard.press("Escape")                 # back to selected
    _command(pg)
    pg.locator(".gui-card").get_by_role("button", name="Open", exact=True).click()
    _full(pg, has_view)
    pg.keyboard.press("Escape")
    pg.keyboard.press("Escape")
    pg.locator(".gui-console").wait_for(state="hidden", timeout=WAIT_MS)


@pytest.mark.parametrize("type_id", TYPES)
def test_every_type_built_draws_three_ways(page, type_id):
    pg = page
    before = set(pg.locator(".gui-hut").evaluate_all("els => els.map(e => e.dataset.id)"))
    pg.locator(".gui-advisor__bubble").get_by_role("button", name="Build", exact=True).click()
    items = pg.locator(".gui-catalog__item")
    items.first.wait_for(state="visible", timeout=WAIT_MS)
    assert items.count() == len(TYPES)
    items.nth(TYPES.index(type_id)).click()
    pg.locator(".gui-modal").wait_for(state="hidden", timeout=WAIT_MS)
    pg.wait_for_function("n => document.querySelectorAll('.gui-hut').length > n", arg=len(before), timeout=WAIT_MS)
    bid = next(i for i in pg.locator(".gui-hut").evaluate_all("els => els.map(e => e.dataset.id)") if i not in before)
    _command(pg)                                # Build leaves the new building selected
    pg.keyboard.press("Escape")
    pg.locator(".gui-console").wait_for(state="hidden", timeout=WAIT_MS)
    _three_ways(pg, bid)
    pg.evaluate("id => import('/static/js/link.js').then(m => m.command('town.demolish', { id }))", bid)
    _hut(pg, bid).wait_for(state="detached", timeout=WAIT_MS)     # the next one stands where this one stood


def test_the_town_hall_is_the_pinned_advisor_in_office(page):
    pg = page
    assert _hut(pg, TOWN_HALL).count() == 0                     # no hut of it on the town
    bubble = pg.locator(".gui-advisor__bubble")
    assert bubble.is_visible() and not bubble.locator(".gui-hut__title").count()   # its card, no name
    face = pg.locator(".gui-advisor__face")
    face.click()                                                # selected: Info, the garrison, Commands
    _command(pg)
    pg.locator(".gui-card").get_by_role("button", name="Open", exact=True).click()   # the card stands over the advisor
    _full(pg, True)
    pg.keyboard.press("Escape")
    pg.keyboard.press("Escape")
    pg.locator(".gui-console").wait_for(state="hidden", timeout=WAIT_MS)


def test_huts_stand_pinned_until_unpinned(page):
    pg = page
    bid = pg.evaluate("() => import('/static/js/link.js').then(m => m.command('town.build', { type: 'pit' }))")
    hut = _hut(pg, bid)
    hut.wait_for(state="visible", timeout=WAIT_MS)
    pg.keyboard.press("Escape")
    assert hut.locator(".gui-pit__icon").is_visible()           # the Pit's card: only its tray
    title = hut.locator(".gui-hut__title")
    assert title.locator(".gui-type-icon").count() == 1          # Office: the type's icon before the name
    pin, name = title.locator(".gui-hut__pin").bounding_box(), title.locator(".gui-hut__name").bounding_box()
    assert pin["x"] >= name["x"] + name["width"]                  # the pin at the right
    start = hut.bounding_box()
    pg.mouse.move(start["x"] + 30, start["y"] + start["height"] - 10)
    pg.mouse.down()
    pg.mouse.move(start["x"] + 130, start["y"] + start["height"] + 40, steps=5)
    pg.mouse.up()
    assert hut.bounding_box()["x"] == start["x"]                 # pinned: a drag does nothing
    assert "is-warn" in hut.locator(".gui-hut__pin").get_attribute("class")    # …and its pin says why, in red
    pg.wait_for_function("id => !document.querySelector(`.gui-hut[data-id=\"${id}\"] .gui-hut__pin`).classList.contains('is-warn')",
                         arg=bid, timeout=4_000)                 # for a moment
    pg.keyboard.press("Escape")
    hut.locator(".gui-hut__pin").click()
    assert "is-free" in hut.get_attribute("class")
    pg.wait_for_function("id => !document.querySelector(`.gui-hut[data-id=\"${id}\"]`).classList.contains('is-free')",
                         arg=bid, timeout=8_000)                 # five seconds alone pin it again
    pg.evaluate("id => import('/static/js/link.js').then(m => m.command('town.demolish', { id }))", bid)


def test_the_lake_window_shows_text_markdown_and_code(page):
    pg = page
    pg.evaluate("""async () => {
        const { openInLake } = await import('/static/js/lake.js');
        await openInLake({ text: '# Notes\\n\\n- first', title: 'Notes' });
        await openInLake({ path: 'README.md', title: 'README.md' });
        await openInLake({ path: 'src/app.py', title: 'app.py' });
    }""")
    lake = pg.locator(".gui-lake")
    lake.wait_for(state="visible", timeout=WAIT_MS)
    pg.wait_for_function("() => document.querySelectorAll('.gui-lake__tabtitle').length >= 3", timeout=WAIT_MS)
    for n in range(lake.locator(".gui-lake__tabtitle").count()):
        lake.locator(".gui-lake__tabtitle").nth(n).click()
        pg.wait_for_function("() => !document.querySelector('.gui-lake__win')?.textContent.includes('Opening…')",
                             timeout=WAIT_MS)
        assert lake.locator(".gui-lake__win").bounding_box()["height"] > 0
    lake.locator("button", has_text="Full").click()
    pg.locator(".gui-lake.is-full").wait_for(state="visible", timeout=WAIT_MS)
    lake.locator("button", has_text="Half").click()
    lake.locator(".gui-win__close").click()                     # hidden: its handle stays
    pg.locator(".gui-lake__handle").wait_for(state="visible", timeout=WAIT_MS)
    pg.locator(".gui-lake__handle").click()
    lake.wait_for(state="visible", timeout=WAIT_MS)


def test_the_console_and_the_window_keep_their_commands_where_they_belong(page):
    """Pin is in Info, nothing recruits, the steward's Redesign window is under it in the garrison, the
    Barracks takes a New task in place (its first words its title), Demolish is at the window's bottom."""
    pg = page
    bid = pg.evaluate("() => import('/static/js/link.js').then(m => m.command('town.build', { type: 'barracks' }))")
    _hut(pg, bid).wait_for(state="visible", timeout=WAIT_MS)
    pg.keyboard.press("Escape")
    _hut(pg, bid).locator(".gui-hut__title").click()
    _command(pg)
    info, roster, card = pg.locator(".gui-console"), pg.locator(".gui-roster"), pg.locator(".gui-card")
    box, face = card.bounding_box(), pg.locator(".gui-advisor__face").bounding_box()
    assert box["x"] + box["width"] >= pg.viewport_size["width"] - 1          # at the right edge…
    assert box["x"] <= face["x"] and box["y"] + box["height"] >= face["y"] + face["height"]   # …over the advisor
    mid = (face["x"] + face["width"] / 2, face["y"] + face["height"] / 2)
    top = pg.evaluate("([x, y]) => document.elementsFromPoint(x, y).map((e) => e.closest('.gui-card, .gui-advisor'))"
                      ".find(Boolean).className", list(mid))           # under the toasts, the card before the advisor
    assert "gui-card" in top
    info.get_by_role("button", name="Pin", exact=True).or_(info.get_by_role("button", name="Unpin", exact=True)).wait_for()
    assert card.get_by_role("button", name="Pin", exact=True).count() == 0
    assert pg.get_by_role("button", name="Recruit", exact=True).count() == 0
    assert pg.get_by_role("button", name="Add agent", exact=True).count() == 0
    roster.get_by_text("Redesign window").wait_for(state="visible", timeout=WAIT_MS)
    assert info.get_by_role("button", name="Balance", exact=True).count() == 0     # the goal is the steward's now
    roster.get_by_text("Goal: Balance").click()
    roster.get_by_text("Goal: Quality").wait_for(state="visible", timeout=WAIT_MS)
    roster.get_by_text("as the project").wait_for(state="visible", timeout=WAIT_MS)
    clock = roster.locator(".gui-freedom__step").nth(1)
    clock.click()                                                  # 🕰 lit, no longer as the town
    pg.wait_for_function("() => document.querySelectorAll('.gui-freedom__step')[1].classList.contains('is-on')",
                         timeout=WAIT_MS)
    assert roster.get_by_text("as the project").count() == 0
    assert server_building(pg, bid)["autonomy"] == "clock"
    clock.click()                                                  # the lit one again: as the town
    roster.get_by_text("as the project").wait_for(state="visible", timeout=WAIT_MS)
    assert card.get_by_text("Redesign window").count() == 0 and card.get_by_text("Revert").count() == 0
    brief = card.locator(".gui-newtask textarea")
    brief.wait_for(state="visible", timeout=WAIT_MS)
    card.get_by_role("button", name="Pause", exact=True).click()
    brief.fill("tidy the readme headings and nothing else")
    card.locator(".gui-newtask").get_by_role("button", name="Send it").click()
    pg.wait_for_function("() => document.querySelector('.gui-newtask textarea').value === ''", timeout=WAIT_MS)
    assert pg.locator(".gui-modal").count() == 0                  # no window opened for it
    card.get_by_text("Tidy the readme headings").wait_for(state="visible", timeout=WAIT_MS)
    card.get_by_role("button", name="Open", exact=True).click()
    _full(pg, True)
    full = pg.locator(".gui-full")
    assert full.locator(".ok-win__bar .gui-win__demolish").count() == 0
    foot = full.locator(".gui-win__foot")
    demolish, about = foot.locator(".gui-win__demolish").bounding_box(), foot.locator(".gui-about").bounding_box()
    assert demolish["x"] > about["x"] and abs(demolish["y"] - about["y"]) < 20     # one row, Demolish at its right
    pg.keyboard.press("Escape")
    pg.keyboard.press("Escape")
    pg.evaluate("id => import('/static/js/link.js').then(m => m.command('town.demolish', { id }))", bid)


def test_a_closed_cards_parts_hide_and_the_huts_under_it_move_up(page):
    pg = page
    link = "import('/static/js/link.js')"
    ids = {}
    for t, x, y in (("fields", 0.0, 0.0), ("pit", 0.02, 0.8), ("war_drum", 0.6, 0.0), ("mill", 0.65, 0.8)):
        ids[t] = pg.evaluate(f"t => {link}.then(m => m.command('town.build', {{ type: t }}))", t)
        pg.evaluate(f"a => {link}.then(m => m.command('hut.move', {{ id: a[0], x: a[1], y: a[2] }}))", [ids[t], x, y])
    pg.keyboard.press("Escape")
    def box(t):
        return _hut(pg, ids[t]).bounding_box()

    def words(hut):
        return ["".join(s.replace("✓", "").split()) for s in hut.locator(".gui-parts__one").all_inner_texts()]

    for bid in ids.values():
        _hut(pg, bid).wait_for(state="visible", timeout=WAIT_MS)
    pg.wait_for_timeout(500)
    before = {t: box(t) for t in ids}
    fields, drum = _hut(pg, ids["fields"]), _hut(pg, ids["war_drum"])
    assert words(fields) == ["Agenttasks", "Myto-dos", "Notes"]        # every part shown, in Office words
    assert words(drum) == ["▪meetings", "↻schedules", "≈limits"]
    fields.locator(".gui-parts__one", has_text="Agent tasks").click()
    fields.locator(".gui-parts__one", has_text="Notes").click()
    drum.locator(".gui-parts__one", has_text="meetings").click()
    pg.wait_for_timeout(500)
    assert pg.locator(".gui-console").is_hidden()                     # a checkbox never opens the hut
    assert fields.locator(".gui-fhut__part").count() == 1               # only My to-dos left
    after = {t: box(t) for t in ids}
    shrunk = before["fields"]["height"] - after["fields"]["height"]
    assert shrunk > 40 and after["fields"]["y"] == before["fields"]["y"]
    assert abs(before["pit"]["y"] - after["pit"]["y"] - shrunk) <= 1   # the hut under it moved up as much
    assert after["war_drum"]["height"] <= before["war_drum"]["height"]
    pg.reload()
    pg.wait_for_selector(".gui-hut", timeout=WAIT_MS)
    pg.wait_for_timeout(800)
    assert _hut(pg, ids["fields"]).locator(".gui-fhut__part").count() == 1   # kept in this browser
    assert abs(box("pit")["y"] - after["pit"]["y"]) <= 2
    for bid in ids.values():
        pg.evaluate(f"id => {link}.then(m => m.command('town.demolish', {{ id }}))", bid)
