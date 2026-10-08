"""The GUI in a real browser (Chromium through Playwright): the town on a fresh project, every type of the
catalog raised through Build and looked at — closed (its card on the town), then in the panel on the right:
its Work, its Info, the whole town (docs/design/calm-town.md) — plus Lake's documents in the panel, the
Warchief's line and the right click. Each must draw, and the page must log no error.

Skipped where Playwright or Chromium is missing; `-m browser` runs these alone, `-m "not browser"` leaves
them out."""
from __future__ import annotations

import datetime as dt
import os
import subprocess
from pathlib import Path

import pytest

playwright = pytest.importorskip("playwright.sync_api")

from orkcraft.gui import builder  # noqa: E402
from orkcraft.gui.host import Host  # noqa: E402
from orkcraft.gui.server import Server  # noqa: E402
from orkcraft.realm import checkpoint, pipes  # noqa: E402
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
                       "ORKCRAFT_WIKI_AUTO": "0", "ORKCRAFT_NIGHT_ROUND": "0"}.items():
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
    pg.wait_for_selector(".gui-warchief__face", timeout=WAIT_MS)   # Office: the Warchief's line is the hall's way in
    yield pg
    pg.wait_for_timeout(300)                    # what a refresh after the last step draws
    pg.close()
    assert not errors, "\n".join(errors)


def server_building(pg, bid: str) -> dict:
    """What the host's `info` says of a building now."""
    return pg.evaluate("id => import('/static/js/link.js').then(m => m.command('info', { id }))", bid)


def _drop_at(pg, bid: str, spot: tuple[float, float] = (0.55, 0.62)) -> tuple[float, float]:
    """A point on the hut's title the person can see. A new hut may stand under another one's card: it is moved to a
    free `spot` first, and the point is taken once it stands still, where the hut itself is on top."""
    pg.evaluate("([id, x, y]) => import('/static/js/link.js').then(m => m.command('hut.move', { id, x, y }))",
                [bid, spot[0], spot[1]])
    box, still = None, 0
    for _ in range(50):
        now = _hut(pg, bid).locator(".gui-hut__title").bounding_box()
        still = still + 1 if now == box else 0
        if still >= 3:
            break
        box = now
        pg.wait_for_timeout(100)
    hit = pg.evaluate("""id => {
      const el = document.querySelector(`.gui-hut[data-id="${id}"] .gui-hut__title`);
      const r = el.getBoundingClientRect();
      for (let x = r.right - 4; x > r.left; x -= 6) {
        const y = r.top + r.height / 2, top = document.elementFromPoint(x, y);
        if (top && top.closest('.gui-hut') && top.closest('.gui-hut').dataset.id === id) return [x, y];
      }
      return [r.left + r.width / 2, r.top + r.height / 2];
    }""", bid)
    return hit[0], hit[1]


def _hut(pg, bid: str):
    return pg.locator(f'.gui-hut[data-id="{bid}"]')


def _closed(pg, bid: str) -> None:
    hut = _hut(pg, bid)
    hut.wait_for(state="visible", timeout=WAIT_MS)
    assert hut.locator(".gui-hut__title").inner_text().strip()
    card = hut.locator(".ok-hut__card")
    assert card.is_visible() and card.bounding_box()["height"] > 0


def _panel(pg, tab: str = "") -> None:
    """The panel stands, on `tab` (Work or Info) when one is named."""
    panel = pg.locator(".gui-panel")
    panel.wait_for(state="visible", timeout=WAIT_MS)
    assert panel.locator(".ok-win__title").inner_text().strip()
    if tab:
        panel.locator(".gui-panel__tabs .ok-tab.is-active", has_text=tab).wait_for(state="visible", timeout=WAIT_MS)
    assert panel.locator(".gui-win__body").bounding_box()["height"] > 0


def _info(pg) -> None:
    pg.locator(".gui-panel__tabs .ok-tab", has_text="Info").click()
    _panel(pg, "Info")
    pg.locator(".gui-panel .gui-info").first.wait_for(state="visible", timeout=WAIT_MS)


def _three_ways(pg, bid: str, has_view: bool = True) -> None:
    _closed(pg, bid)
    _hut(pg, bid).locator(".gui-hut__title").click()   # open: the panel on its Work
    _panel(pg, "Work" if has_view else "")
    if has_view:                                # its detail came and its panes are laid out
        pg.locator(".gui-panel .gui-win__body.is-view").wait_for(state="visible", timeout=WAIT_MS)
    _info(pg)
    pg.locator(".gui-panel .gui-panel__full").click()  # the whole town
    pg.locator(".gui-panel.is-full").wait_for(state="visible", timeout=WAIT_MS)
    pg.keyboard.press("Escape")                 # back to half
    pg.locator(".gui-panel:not(.is-full)").wait_for(state="visible", timeout=WAIT_MS)
    pg.keyboard.press("Escape")                 # closed
    pg.locator(".gui-panel").wait_for(state="hidden", timeout=WAIT_MS)


def _line(pg, text: str, enter: bool = True) -> None:
    """Something typed into the Warchief's line."""
    field = pg.locator(".gui-warchief__input")
    field.click()
    field.fill(text)
    if enter:
        field.press("Enter")


@pytest.mark.parametrize("type_id", TYPES)
def test_every_type_built_draws_three_ways(page, type_id):
    pg = page
    before = set(pg.locator(".gui-hut").evaluate_all("els => els.map(e => e.dataset.id)"))
    _line(pg, "/build")                         # the catalog
    items = pg.locator(".gui-catalog__item")
    items.first.wait_for(state="visible", timeout=WAIT_MS)
    assert items.count() == len(TYPES)
    items.nth(TYPES.index(type_id)).click()
    pg.locator(".gui-modal").wait_for(state="hidden", timeout=WAIT_MS)
    pg.wait_for_function("n => document.querySelectorAll('.gui-hut').length > n", arg=len(before), timeout=WAIT_MS)
    bid = next(i for i in pg.locator(".gui-hut").evaluate_all("els => els.map(e => e.dataset.id)") if i not in before)
    _panel(pg)                                  # Build leaves the new building open
    pg.keyboard.press("Escape")
    pg.locator(".gui-panel").wait_for(state="hidden", timeout=WAIT_MS)
    _three_ways(pg, bid)
    pg.evaluate("id => import('/static/js/link.js').then(m => m.command('town.demolish', { id }))", bid)
    _hut(pg, bid).wait_for(state="detached", timeout=WAIT_MS)     # the next one stands where this one stood


def test_the_town_hall_is_the_warchiefs_line_in_office(page):
    pg = page
    assert _hut(pg, TOWN_HALL).count() == 0                     # no hut of it on the town
    assert pg.locator(".gui-strip, .gui-status, .gui-advisor").count() == 0   # no console, no status bar
    pg.locator(".gui-warchief__face").click()                   # the hall in the panel, on the Warchief's chat
    _panel(pg, "Work")
    pg.locator(".gui-panel .ok-tab.is-active", has_text="Chat").wait_for(state="visible", timeout=WAIT_MS)
    _info(pg)
    pg.keyboard.press("Escape")
    pg.locator(".gui-panel").wait_for(state="hidden", timeout=WAIT_MS)


def test_huts_move_until_the_person_pins_them(page):
    pg = page
    bid = pg.evaluate("() => import('/static/js/link.js').then(m => m.command('town.build', { type: 'pit' }))")
    hut = _hut(pg, bid)
    hut.wait_for(state="visible", timeout=WAIT_MS)
    pg.keyboard.press("Escape")
    hut.locator(".gui-hut__name").wait_for(state="visible", timeout=WAIT_MS)   # the Pit is built folded: its title bar
    title = hut.locator(".gui-hut__title")
    assert title.locator(".gui-type-icon").count() == 1          # Office: the type's icon before the name
    sprite, card = hut.locator(".gui-hut__sprite"), hut.locator(".ok-hut__card")
    pg.wait_for_function("id => document.querySelector(`.gui-hut[data-id=\"${id}\"] .gui-hut__sprite img`).complete",
                         arg=bid, timeout=WAIT_MS)
    s, c = sprite.bounding_box(), card.bounding_box()           # Office: its building, smaller, at the card's left
    assert s["width"] < 68 and s["x"] + s["width"] / 2 < c["x"] + c["width"] / 2
    pin, name = title.locator(".gui-hut__pin").bounding_box(), title.locator(".gui-hut__name").bounding_box()
    assert pin["x"] >= name["x"] + name["width"]                  # the pin at the right
    assert "is-free" in hut.get_attribute("class")              # a new hut moves: nothing pins it but the person
    hut.locator(".gui-hut__pin").click()
    pg.wait_for_function("id => !document.querySelector(`.gui-hut[data-id=\"${id}\"]`).classList.contains('is-free')",
                         arg=bid, timeout=WAIT_MS)
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
    pg.wait_for_function("id => document.querySelector(`.gui-hut[data-id=\"${id}\"]`).classList.contains('is-free')",
                         arg=bid, timeout=WAIT_MS)
    pg.wait_for_timeout(6_000)
    assert "is-free" in hut.get_attribute("class")              # and stays free: nothing pins it again by itself
    pg.evaluate("id => import('/static/js/link.js').then(m => m.command('town.demolish', { id }))", bid)


def test_a_huts_annex_follows_its_goal_and_its_flag_waits_for_renown(page):
    """docs/design/growth.md §5: balance has no annex, another goal builds one at once; no flag before renown."""
    pg = page
    bid = pg.evaluate("() => import('/static/js/link.js').then(m => m.command('town.build', { type: 'pit' }))")
    pg.keyboard.press("Escape")
    sprite = _hut(pg, bid).locator(".gui-sprite")
    sprite.wait_for(state="attached", timeout=WAIT_MS)
    assert sprite.get_attribute("data-level") == "0"
    assert _hut(pg, bid).locator(".gui-sprite__flag, .gui-sprite__footing, .gui-sprite__annex").count() == 0
    pg.evaluate("id => import('/static/js/link.js').then(m => m.command('building.goal', { id, value: 'thrift' }))", bid)
    pg.wait_for_function("id => document.querySelector(`.gui-hut[data-id=\"${id}\"] .gui-sprite__annex`)"
                         "?.getAttribute('src').endsWith('/flags/annex-thrift.png')", arg=bid, timeout=WAIT_MS)
    pg.evaluate("id => import('/static/js/link.js').then(m => m.command('town.demolish', { id }))", bid)


def test_a_new_orkspace_from_the_fog_takes_the_biome_picked(page):
    """docs/design/war-map.md §2.4: the fog's field names the land and its swatches pick its ground."""
    pg = page
    pg.locator(".gui-map__fog").focus()
    pg.keyboard.press("Enter")
    pg.locator(".gui-map__new").wait_for(state="visible", timeout=WAIT_MS)
    pg.locator('.gui-map__biome[title$="meadow"]').click()
    assert pg.locator(".gui-map__biome.is-on").get_attribute("title").endswith("meadow")
    pg.keyboard.type("Tournament")
    pg.keyboard.press("Enter")
    pg.locator(".gui-map__land.is-open", has_text="Tournament").wait_for(state="visible", timeout=WAIT_MS)
    lands = pg.evaluate("() => import('/static/js/link.js').then(({ town }) => town.value.orkspaces)")
    made = next(o for o in lands if o["name"] == "Tournament")
    assert made["biome"] == "meadow"
    assert pg.locator(".gui-map__title").inner_text().strip().lower() == "war map"   # the brand's words stay
    pg.evaluate("id => import('/static/js/link.js').then(m => m.command('orkspace.remove', { id }))", made["id"])


def test_the_lake_window_shows_text_markdown_and_code(page):
    pg = page
    pg.evaluate("""async () => {
        const { openInLake } = await import('/static/js/lake.js');
        await openInLake({ text: '# Notes\\n\\n- first', title: 'Notes' });
        await openInLake({ path: 'README.md', title: 'README.md' });
        await openInLake({ path: 'src/app.py', title: 'app.py' });
    }""")
    lake = pg.locator(".gui-panel")                             # documents are the panel's tabs
    lake.wait_for(state="visible", timeout=WAIT_MS)
    pg.wait_for_function("() => document.querySelectorAll('.gui-lake__tabtitle').length >= 3", timeout=WAIT_MS)
    assert lake.locator(".gui-panel__tabs .ok-tab", has_text="Info").count() == 0   # no building open: documents only
    for n in range(lake.locator(".gui-lake__tabtitle").count()):
        lake.locator(".gui-lake__tabtitle").nth(n).click()
        pg.wait_for_function("() => !document.querySelector('.gui-lake__win')?.textContent.includes('Opening…')",
                             timeout=WAIT_MS)
        assert lake.locator(".gui-lake__win").bounding_box()["height"] > 0
    lake.get_by_role("button", name="Full", exact=True).click()
    pg.locator(".gui-panel.is-full").wait_for(state="visible", timeout=WAIT_MS)
    lake.get_by_role("button", name="Half", exact=True).click()
    lake.locator(".gui-win__close").click()                     # closed: its handle stays
    pg.locator(".gui-panel__handle").wait_for(state="visible", timeout=WAIT_MS)
    pg.locator(".gui-panel__handle").click()
    lake.wait_for(state="visible", timeout=WAIT_MS)
    bid = pg.evaluate("() => import('/static/js/link.js').then(m => m.command('town.build', { type: 'pit' }))")
    _hut(pg, bid).locator(".gui-hut__title").click()
    _panel(pg, "Work")                                          # a building opened beside the documents
    assert lake.locator(".gui-lake__tabtitle").count() >= 3
    lake.locator(".gui-lake__tabtitle").first.click()
    lake.locator(".gui-lake__win").wait_for(state="visible", timeout=WAIT_MS)
    lake.locator(".gui-panel__tabs .ok-tab", has_text="Info").click()
    _panel(pg, "Info")
    pg.evaluate("id => import('/static/js/link.js').then(m => m.command('town.demolish', { id }))", bid)


def test_info_keeps_the_buildings_commands_and_work_takes_a_task_in_place(page):
    """Info: 👍 / 👎 and no Pin, nothing recruits, the steward's part with Redesign, its goal and Freedom, Demolish at
    the bottom. The Barracks' Work takes a New task in place (its first words its title)."""
    pg = page
    bid = pg.evaluate("() => import('/static/js/link.js').then(m => m.command('town.build', { type: 'barracks' }))")
    _hut(pg, bid).wait_for(state="visible", timeout=WAIT_MS)
    _hut(pg, bid).locator(".gui-hut__title").click()
    _panel(pg, "Work")
    panel = pg.locator(".gui-panel")
    box = panel.bounding_box()
    assert box["x"] + box["width"] >= pg.viewport_size["width"] - 1            # at the right edge…
    assert abs(box["width"] - pg.viewport_size["width"] / 2) < 2               # …half of the town
    work = panel.locator(".gui-win__body.is-view")
    brief = work.locator(".gui-newtask textarea")
    brief.wait_for(state="visible", timeout=WAIT_MS)
    work.get_by_role("button", name="Pause", exact=True).first.click()
    brief.fill("tidy the readme headings and nothing else")
    work.locator(".gui-newtask").get_by_role("button", name="Send", exact=True).click()
    pg.wait_for_function("() => document.querySelector('.gui-newtask textarea').value === ''", timeout=WAIT_MS)
    assert pg.locator(".gui-modal").count() == 0                  # no window opened for it
    work.get_by_text("Tidy the readme headings").first.wait_for(state="visible", timeout=WAIT_MS)
    _info(pg)
    info = panel.locator(".gui-info-tab")
    info.get_by_role("button", name="Good", exact=True).wait_for(state="visible", timeout=WAIT_MS)
    assert [t.replace("\n", "") for t in info.locator(".gui-thumb").all_inner_texts()] == ["👍0", "👎0"]
    assert pg.get_by_role("button", name="Pin", exact=True).count() == 0          # the pin is the hut's own
    assert pg.get_by_role("button", name="Recruit", exact=True).count() == 0
    assert pg.get_by_role("button", name="Add agent", exact=True).count() == 0
    steward = info.locator(".gui-steward-part")
    steward.get_by_role("button", name="Redesign", exact=True).wait_for(state="visible", timeout=WAIT_MS)
    title = steward.locator("h3").inner_text()
    assert "★" in title and "idle" in title.lower()                               # the steward's name, its status
    steward.get_by_text("Listens to nobody yet").wait_for(state="visible", timeout=WAIT_MS)
    steward.get_by_role("button", name="Quality", exact=True).click()
    pg.wait_for_function("() => [...document.querySelectorAll('.gui-steward-part .gui-steps__one')].find((e) => e.textContent === 'Quality')"
                         ".classList.contains('is-on')", timeout=WAIT_MS)
    assert server_building(pg, bid)["goal"] == "quality"
    town_step = steward.locator(".gui-steps__one.is-as-town")
    assert "is-on" in town_step.get_attribute("class")              # as the town, until one is picked
    clock = steward.locator(".gui-steps__one.is-icon").nth(1)
    clock.click()
    pg.wait_for_function("() => document.querySelectorAll('.gui-steward-part .gui-steps__one.is-icon')[1].classList.contains('is-on')",
                         timeout=WAIT_MS)
    assert server_building(pg, bid)["autonomy"] == "clock"
    clock.click()                                                  # the lit one again: as the town
    pg.wait_for_function("() => document.querySelector('.gui-steward-part .gui-steps__one.is-as-town').classList.contains('is-on')",
                         timeout=WAIT_MS)
    demolish = info.locator(".gui-win__demolish").bounding_box()
    assert demolish["y"] > steward.bounding_box()["y"]             # Demolish at the bottom
    pg.keyboard.press("Escape")
    pg.evaluate("id => import('/static/js/link.js').then(m => m.command('town.demolish', { id }))", bid)


def test_the_right_click_gives_a_buildings_menu_and_the_maps(page):
    pg = page
    bid = pg.evaluate("() => import('/static/js/link.js').then(m => m.command('town.build', { type: 'pit' }))")
    _hut(pg, bid).wait_for(state="visible", timeout=WAIT_MS)
    pg.keyboard.press("Escape")
    _hut(pg, bid).locator(".gui-hut__title").click(button="right")
    menu = pg.locator(".gui-menu")
    menu.wait_for(state="visible", timeout=WAIT_MS)
    assert pg.locator(".gui-panel").count() == 0                   # the menu, not the panel
    items = menu.locator(".gui-menu__item").all_inner_texts()
    assert any(t.startswith("Info") for t in items) and any(t.startswith("Demolish") for t in items)
    menu.locator(".gui-menu__item", has_text="Info").click()
    _panel(pg, "Info")
    pg.keyboard.press("Escape")
    _hut(pg, bid).locator(".gui-hut__title").click(button="right")
    menu.locator(".gui-menu__item", has_text="Ask the").click()     # the Warchief's line, about it
    pg.locator(".gui-warchief__chip", has_text="@").first.wait_for(state="visible", timeout=WAIT_MS)
    pg.keyboard.press("Escape")
    pg.locator(".gui-town").click(button="right", position={"x": 600, "y": 500})
    menu.wait_for(state="visible", timeout=WAIT_MS)
    menu.locator(".gui-menu__item", has_text="Build here").click()
    pg.locator(".gui-modal .gui-catalog__item").first.wait_for(state="visible", timeout=WAIT_MS)
    pg.keyboard.press("Escape")
    _hut(pg, bid).locator(".gui-hut__title").click(button="right")
    menu.locator(".gui-menu__item", has_text="Demolish").click()
    pg.locator(".gui-modal").get_by_role("button", name="Demolish", exact=True).click()
    _hut(pg, bid).wait_for(state="detached", timeout=WAIT_MS)


def test_the_warchiefs_line_runs_commands_names_buildings_and_hints(page):
    pg = page
    field = pg.locator(".gui-warchief__input")
    field.click()
    pg.locator(".gui-warchief__hint").first.wait_for(state="visible", timeout=WAIT_MS)   # empty: hints
    field.fill("/ro")
    pg.locator(".gui-warchief__list .ok-item", has_text="/road").wait_for(state="visible", timeout=WAIT_MS)
    field.press("Tab")
    assert field.input_value() == "/road "
    field.fill("/nonsense")
    field.press("Enter")
    pg.locator(".gui-warchief__said").wait_for(state="visible", timeout=WAIT_MS)
    _line(pg, "/orkspace Billing")                               # a new orkspace, and the town goes to it
    pg.locator(".gui-map__land.is-open", has_text="Billing").wait_for(state="visible", timeout=WAIT_MS)
    first = pg.locator(".gui-map__land[data-id]").first          # a land is cut to its shape: open it by key
    first.focus()
    pg.keyboard.press("Enter")
    pg.wait_for_function("() => !document.querySelector('.gui-map__land.is-open')?.textContent.includes('Billing')",
                         timeout=WAIT_MS)
    bid = pg.evaluate("() => import('/static/js/link.js').then(m => m.command('town.build', { type: 'pit' }))")
    pg.keyboard.press("Escape")
    title = _hut(pg, bid).locator(".gui-hut__name").text_content().strip()
    _line(pg, f"@{title[:3]}", enter=False)
    pg.locator(".gui-warchief__list .ok-item", has_text=title).click()
    assert field.input_value() == f"@{title} "
    field.fill(f"/open @{title}")
    field.press("Enter")
    _panel(pg, "Work")
    pg.locator(".gui-warchief__chip.is-auto", has_text=title).wait_for(state="visible", timeout=WAIT_MS)   # the open one
    _line(pg, "/demolish")                                       # about the building open
    pg.locator(".gui-modal").get_by_role("button", name="Demolish", exact=True).click()
    _hut(pg, bid).wait_for(state="detached", timeout=WAIT_MS)


def test_note_in_the_warchiefs_line_shows_the_wikis_suggestions_before_enter_saves(page, gui, monkeypatch):
    """`/note`: the Wiki's meeting, section and tags stand over the bar; Tab picks another meeting; Enter
    saves what was shown, and the Calendar's meeting says what the Wiki keeps for it
    (docs/design/wiki-librarian.md §4, §6)."""
    pg = page
    server, _ = gui
    from orkcraft.core.workers.scrolls import ScrollsWorker
    # the note's take-in runs no agent here (on a machine with one it would really start)
    monkeypatch.setattr(ScrollsWorker, "work_runner", staticmethod(lambda *a: ("taken in", 0.0, None, "")))
    repo = server.host.town.repo_root
    day = dt.date.today() + dt.timedelta(days=1)
    rows = []
    for n, (summary, when) in enumerate((("Pricing review", day), ("Roadmap sync", day + dt.timedelta(days=1)))):
        rows += ["BEGIN:VEVENT", f"UID:note-{n}@x", f"DTSTART:{when:%Y%m%d}T110000", f"DTEND:{when:%Y%m%d}T113000",
                 f"SUMMARY:{summary}", "END:VEVENT"]
    (repo / "note-cal.ics").write_text("\r\n".join(["BEGIN:VCALENDAR", *rows, "END:VCALENDAR"]) + "\r\n")
    build = "t => import('/static/js/link.js').then(m => m.command('town.build', { type: t }))"
    drum = pg.evaluate(build, "war_drum")
    pg.evaluate("id => import('/static/js/link.js').then(m => m.act(id, 'settings', { ics: 'note-cal.ics' }))", drum)
    wiki = pg.evaluate(build, "scrolls")
    pg.keyboard.press("Escape")
    field = pg.locator(".gui-warchief__input")
    _line(pg, "/note Go over the pricing numbers tomorrow", enter=False)
    meet = pg.locator(".gui-warchief__note-meet")
    meet.filter(has_text="Pricing review").wait_for(state="visible", timeout=WAIT_MS)
    assert "to discuss" in pg.locator(".gui-warchief__note-rows").inner_text()
    field.press("Tab")
    meet.filter(has_text="Roadmap sync").wait_for(state="visible", timeout=WAIT_MS)
    field.press("Tab")
    meet.filter(has_text="Not for a meeting").wait_for(state="visible", timeout=WAIT_MS)
    field.press("Shift+Tab")
    meet.filter(has_text="Roadmap sync").wait_for(state="visible", timeout=WAIT_MS)
    field.press("Shift+Tab")
    meet.filter(has_text="Pricing review").wait_for(state="visible", timeout=WAIT_MS)
    field.press("Enter")
    pg.locator(".ok-toast", has_text="Pricing review").wait_for(state="visible", timeout=WAIT_MS)
    assert field.input_value() == ""
    _hut(pg, drum).locator(".gui-drum__wiki", has_text="1").wait_for(state="visible", timeout=WAIT_MS)
    w = server.host.town.worker(wiki)
    assert not pg.locator(".ok-toast.is-error").count() and not w.last_error
    for bid in (wiki, drum):                    # the next test's buildings stand where these stood
        pg.evaluate("id => import('/static/js/link.js').then(m => m.command('town.demolish', { id }))", bid)
        _hut(pg, bid).wait_for(state="detached", timeout=WAIT_MS)


def test_a_folder_outside_the_project_is_connected_and_the_rules_shown(page, gui, tmp_path):
    """Connect a folder: a path typed (the dialog of the system is the server's), the question about the rules
    for a folder outside the project; then the Rules for AI tools in the window
    (docs/design/wiki-folders-rules.md §2, §3)."""
    pg = page
    server, _ = gui
    outside = tmp_path / "specs"
    outside.mkdir()
    (outside / "brief.md").write_text("# Brief\n")
    link = "import('/static/js/link.js')"
    wiki = pg.evaluate(f"t => {link}.then(m => m.command('town.build', {{ type: t }}))", "scrolls")
    pg.keyboard.press("Escape")
    pg.evaluate("id => import('/static/js/buildings/scrolls.js').then(m => m.quick(id, 'knowledge.add'))", wiki)
    dialog = pg.locator(".ok-dialog", has_text="Connect a folder")
    dialog.wait_for(state="visible", timeout=WAIT_MS)
    assert dialog.get_by_role("button", name="Choose folder…").is_visible()
    dialog.get_by_role("button", name="Type a path").click()
    dialog.locator("input.ok-input").fill(str(outside))
    ask = dialog.locator(".ok-check", has_text="Also tell AI tools working in this folder about the wiki")
    ask.wait_for(state="visible", timeout=WAIT_MS)
    ask.click()
    dialog.screenshot(path=str(tmp_path / "wiki-connect-folder.png"))
    dialog.get_by_role("button", name="Connect it").click()
    dialog.wait_for(state="detached", timeout=WAIT_MS)
    w = server.host.town.worker(wiki)
    assert f"dir:{outside.resolve().as_posix()}" in w.config["sources"]
    assert w.config["rules_in"] == [outside.resolve().as_posix()]
    (w.wiki_root / "pages" / "concepts").mkdir(parents=True, exist_ok=True)
    (w.wiki_root / "pages" / "concepts" / "brief.md").write_text("# Brief\n")
    server.host.town.call(w.refresh)
    server.host.town.call(w.approved)
    pg.evaluate("id => import('/static/js/windows.js').then(m => m.openBuilding(id, 'work'))", wiki)
    rules = pg.locator(".wiki-rules")
    rules.locator("summary", has_text="ready").wait_for(state="visible", timeout=WAIT_MS)   # a take-in waits: its strip is first
    rules.get_by_role("button", name="Write now").click()
    pg.locator(".wiki-rules summary", has_text="written").wait_for(state="visible", timeout=WAIT_MS)
    rules.screenshot(path=str(tmp_path / "wiki-rules.png"))
    assert f"@{(w.wiki_root / 'RULES.md').as_posix()}" in (outside / "CLAUDE.md").read_text()   # no tool on: Claude Code's
    server.host.town.call(w.remove_rules)
    pg.evaluate(f"id => {link}.then(m => m.command('town.demolish', {{ id }}))", wiki)
    _hut(pg, wiki).wait_for(state="detached", timeout=WAIT_MS)


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
    fields.hover()                                                      # the board's tray comes out under the mouse
    assert words(fields) == ["Orkwork", "Myto-dos", "Notes"]          # every part shown, in today's words
    assert words(drum) == ["▪meetings", "↻schedules", "≈limits"]
    fields.locator(".gui-parts__one", has_text="Ork work").click()
    fields.locator(".gui-parts__one", has_text="Notes").click()
    drum.locator(".gui-parts__one", has_text="meetings").click()
    pg.mouse.move(0, 0)
    pg.wait_for_timeout(500)
    assert pg.locator(".gui-panel").count() == 0                      # a checkbox never opens the hut
    assert fields.locator(".gui-fhut__part").count() == 1               # only My to-dos left
    after = {t: box(t) for t in ids}
    shrunk = before["fields"]["height"] - after["fields"]["height"]
    assert shrunk > 10 and after["fields"]["y"] == before["fields"]["y"]   # a quiet board is as tall as what it says
    assert abs(before["pit"]["y"] - after["pit"]["y"] - shrunk) <= 1   # the hut under it moved up as much
    assert after["war_drum"]["height"] <= before["war_drum"]["height"]
    pg.reload()
    pg.wait_for_selector(".gui-hut", timeout=WAIT_MS)
    pg.wait_for_timeout(800)
    assert _hut(pg, ids["fields"]).locator(".gui-fhut__part").count() == 1   # kept in this browser
    assert abs(box("pit")["y"] - after["pit"]["y"]) <= 2
    for bid in ids.values():
        pg.evaluate(f"id => {link}.then(m => m.command('town.demolish', {{ id }}))", bid)


def test_the_stewards_window_lists_the_roads_it_listens_to_with_their_handlers(page):
    """Its head is the steward (its models, task by task); each road in with its handler (the Pit takes no
    plain one); a click on an agent's edits its prompt,
    › opens the ork; an ork no road feeds is listed on its own."""
    pg = page
    link = "import('/static/js/link.js')"
    call = lambda name, args: pg.evaluate(f"([n, a]) => {link}.then(m => m.command(n, a))", [name, args])   # noqa: E731
    src, dst = call("town.build", {"type": "forge"}), call("town.build", {"type": "pit"})
    coder = call("building.recruit", {"id": dst, "name": "Coder", "role": "reads tickets", "orders": "Read the ticket."})
    call("building.recruit", {"id": dst, "name": "Sweeper", "role": "tidies", "orders": "Tidy up."})
    choices = call("roads.choices", {"from": src, "to": dst})
    by_coder = next(c for c in choices if c.get("handler") == coder.split("/", 1)[1])
    call("roads.lay", {"from": src, "to": dst, "event": by_coder["event"], "handler": by_coder["handler"]})
    _hut(pg, dst).wait_for(state="visible", timeout=WAIT_MS)
    pg.keyboard.press("Escape")
    _hut(pg, dst).locator(".gui-hut__title").click()
    _info(pg)
    roster = pg.locator(".gui-steward-part")
    roads = roster.locator(".gui-steward__road")
    roads.first.wait_for(state="visible", timeout=WAIT_MS)
    assert roads.count() == 1                                        # the Pit takes only roads to an ork
    assert "Coder" in roads.first.inner_text() and "agent" in roads.first.inner_text()
    own = roster.locator(".gui-steward__group", has_text="By schedule or by hand")
    assert "Sweeper" in own.inner_text()
    roads.filter(has_text="Coder").click()                          # its prompt
    modal = pg.locator(".gui-modal")
    modal.wait_for(state="visible", timeout=WAIT_MS)
    assert "Coder" in modal.inner_text() and modal.locator("textarea").first.input_value() == "Read the ticket."
    pg.keyboard.press("Escape")
    modal.wait_for(state="hidden", timeout=WAIT_MS)
    roster.locator(".gui-steward__model").click()                   # the steward's models, task by task
    modal.wait_for(state="visible", timeout=WAIT_MS)
    labels = modal.locator(".gui-field .ok-font-label").all_text_contents()   # as written: Camp sets labels in capitals
    assert labels[:3] == ["Watch: findings and proposals", "Redesign the window", "Rules and settings"]
    modal.locator("select").first.select_option("laborer")
    modal.get_by_role("button", name="Save", exact=True).click()
    modal.wait_for(state="hidden", timeout=WAIT_MS)
    assert next(u for u in server_building(pg, dst)["steward"]["uses"] if u["id"] == "watch")["tier"] == "laborer"
    pg.wait_for_function("() => document.querySelector('.gui-steward__model').textContent.includes('+1')", timeout=WAIT_MS)
    roads.filter(has_text="Coder").locator(".gui-steward__more").click()     # › the ork itself
    pg.locator(".gui-panel .gui-info-tab h3", has_text="Inventory").wait_for(state="visible", timeout=WAIT_MS)
    pg.keyboard.press("Escape")
    pg.keyboard.press("Escape")
    for bid in (src, dst):
        call("town.demolish", {"id": bid})


def test_the_stewards_road_rules_are_listed_under_it_and_an_agent_is_handed_over(page, gui):
    """docs/design/steward-listens.md §4: a road rule is no ork — it is listed under the steward, opens its own
    panel (its words, roads, runs); an agent handler's Info hands it to the steward, showing what changes."""
    from orkcraft import scroll as ts
    pg, host = page, gui[0].host
    link = "import('/static/js/link.js')"
    call = lambda name, args: pg.evaluate(f"([n, a]) => {link}.then(m => m.command(n, a))", [name, args])   # noqa: E731
    src, dst = call("town.build", {"type": "forge"}), call("town.build", {"type": "pit"})
    ts.add_handler(host.town.scroll, dst, "Boss's mail", kind="steward", orders="Only the boss's patches.")
    mailman = call("building.recruit", {"id": dst, "name": "Mailman", "role": "reads", "orders": "Summarise it."})
    choices = call("roads.choices", {"from": src, "to": dst})
    for handler in ("boss_s_mail", mailman.split("/", 1)[1]):
        pick = next(c for c in choices if c.get("handler") == handler)
        call("roads.lay", {"from": src, "to": dst, "event": pick["event"], "handler": handler})
    _hut(pg, dst).wait_for(state="visible", timeout=WAIT_MS)
    pg.keyboard.press("Escape")
    _hut(pg, dst).locator(".gui-hut__title").click()
    _info(pg)
    rules = pg.locator(".gui-steward__group", has_text="Road rules")
    rules.wait_for(state="visible", timeout=WAIT_MS)
    assert "Boss's mail" in rules.inner_text() and "→ here" in rules.inner_text()
    assert not pg.locator(".gui-panel .gui-section", has_text="Garrison").filter(has_text="Boss's mail").count()
    rules.locator(".gui-steward__rule").first.click()
    pg.locator(".gui-rule").wait_for(state="visible", timeout=WAIT_MS)
    assert "Only the boss's patches." in pg.locator(".gui-rule__words").inner_text()
    pg.locator(".gui-info__back").click()
    pg.locator(".gui-steward__road", has_text="Mailman").locator(".gui-steward__more").click()
    pg.get_by_role("button", name="Hand to the steward").click()
    modal = pg.locator(".gui-modal")
    modal.locator(".gui-hand").wait_for(state="visible", timeout=WAIT_MS)
    assert "Summarise it." in modal.inner_text()
    modal.get_by_role("button", name="Hand it over").click()
    pg.locator(".gui-rule").wait_for(state="visible", timeout=WAIT_MS)
    assert host.town.scroll.building(dst).garrison.handler("mailman").kind == "steward"
    pg.keyboard.press("Escape")
    for bid in (src, dst):
        call("town.demolish", {"id": bid})


def test_the_huds_menu_sets_the_towns_autonomy_and_stop_all_stands_in_the_hud(page):
    """The project's name opens the town's settings: its autonomy and, on the clock, its two waits;
    Stop all stands where Ready was, and the steward's window keeps no waits of its own."""
    pg = page
    hud = pg.locator(".gui-hud")
    assert hud.get_by_role("button", name="Stop all", exact=True).count() == 1 and hud.get_by_text("Ready").count() == 0
    assert hud.get_by_role("button", name="Answers", exact=True).count() == 1          # the orks' questions, always there
    hud.locator(".gui-hud__menu").click()
    modal = pg.locator(".gui-modal")
    modal.wait_for(state="visible", timeout=WAIT_MS)
    lit = lambda: modal.locator(".gui-steps__one.is-on").all_inner_texts()        # noqa: E731
    assert any("On the clock" in t or "Apply if unanswered" in t for t in lit()) and "7 min" in lit()
    modal.get_by_role("button", name="15 min", exact=True).click()
    pg.wait_for_function("() => [...document.querySelectorAll('.gui-modal .gui-steps__one.is-on')].some((e) => e.textContent === '15 min')",
                         timeout=WAIT_MS)
    steps = modal.locator(".gui-field").first.locator(".gui-steps__one")
    steps.nth(2).click()                                            # unchained: no waits to set
    pg.wait_for_function("() => !document.querySelector('.gui-modal').textContent.includes('15 min')", timeout=WAIT_MS)
    settings = pg.evaluate("() => import('/static/js/link.js').then(m => m.command('town.settings'))")
    assert settings["autonomy"] == "free" and settings["wait"] == 15
    pg.evaluate("() => import('/static/js/link.js').then(m => m.command('town.settings.set', { autonomy: 'clock', wait: 7 }))")
    modal.get_by_role("button", name="Close", exact=True).click()
    modal.wait_for(state="hidden", timeout=WAIT_MS)


def test_listen_asks_in_words_and_lays_the_road_the_steward_offers(page, monkeypatch):
    """+ Listen opens the road in words (picking by hand folded below); the steward's offer is laid by a click."""
    import json
    from orkcraft.core import runners
    pg = page
    link = "import('/static/js/link.js')"
    call = lambda name, args: pg.evaluate(f"([n, a]) => {link}.then(m => m.command(n, a))", [name, args])   # noqa: E731
    tower, fields = call("town.build", {"type": "watchtower"}), call("town.build", {"type": "fields"})
    monkeypatch.setattr(runners, "ROAD_RUNNER", lambda p: (json.dumps({"options": [
        {"from": tower, "event": "mail.received", "match": "(?i)unread", "say": "When unread mail comes, a to-do"}]}), 0.01))
    _hut(pg, fields).wait_for(state="visible", timeout=WAIT_MS)
    pg.keyboard.press("Escape")
    _hut(pg, fields).locator(".gui-hut__title").click()
    _info(pg)
    pg.locator(".gui-steward-part .gui-steward__group summary button").first.click()    # + Listen
    modal = pg.locator(".gui-modal")
    modal.wait_for(state="visible", timeout=WAIT_MS)
    manual = modal.locator("details.gui-road__manual")
    assert manual.count() == 1 and manual.get_attribute("open") is None                 # by hand: folded
    modal.locator("textarea").fill("listen to unread messages and make to-dos of them")
    modal.locator("button.primary").click()
    pg.locator(".gui-modal", has_text="When unread mail comes").wait_for(state="visible", timeout=WAIT_MS)
    pg.locator(".gui-modal .ok-act").first.click()
    for _ in range(50):
        listens = server_building(pg, fields)["listens"]
        if listens:
            break
        pg.wait_for_timeout(100)
    assert listens and tower in json.dumps(listens)
    for bid in (tower, fields):
        call("town.demolish", {"id": bid})


def test_the_warchief_gives_the_work_and_his_card_builds_and_undoes_it(page, monkeypatch):
    """A line in words goes to the Warchief; his answer's card (core/warchief.py) raises the building on Build
    and takes it down on Undo, over the line, without the panel."""
    from orkcraft.core import runners
    pg = page
    monkeypatch.setattr(runners, "WARCHIEF_RUNNER", lambda p: ('A drop box takes them.\nDO: {"build": "pit"}', 0.01))
    pg.evaluate("() => import('/static/js/link.js').then(m => m.command('town.settings.set', { autonomy: 'clock' }))")
    before = pg.locator(".gui-hut").count()
    _line(pg, "where do I put the files people send me?")
    card = pg.locator(".gui-warchief__over .gui-card-order").last
    card.wait_for(state="visible", timeout=WAIT_MS)
    assert "DO:" not in pg.locator(".gui-warchief__thread").inner_text()
    card.get_by_role("button", name="Build", exact=True).click()
    pg.wait_for_function("n => document.querySelectorAll('.gui-hut').length > n", arg=before, timeout=WAIT_MS)
    assert pg.locator(".gui-panel").count() == 0                       # the town changed, the panel did not open
    card.get_by_role("button", name="Undo", exact=True).click()
    pg.wait_for_function("n => document.querySelectorAll('.gui-hut').length === n", arg=before, timeout=WAIT_MS)


def test_a_new_tower_opens_on_add_a_source_and_adds_jira_in_its_panel(page, gui, monkeypatch):
    """Build a Watchtower: its panel opens on the picker (no dialog); a pasted Jira link, the login, the projects,
    the first look and Add happen in the panel over the feed, and the new source stands in its chips
    (docs/design/watchtower-quick-add.md §4). The services are fakes; `ORKCRAFT_SHOTS` keeps screenshots."""
    from orkcraft.core.workers.watchtower import WatchtowerWorker
    from tests.test_watchtower_quickadd import ATL, Opener, _gh
    monkeypatch.setattr(WatchtowerWorker, "feed_opener", Opener(ATL))
    monkeypatch.setattr(WatchtowerWorker, "gh_runner", staticmethod(_gh))
    shots = os.environ.get("ORKCRAFT_SHOTS", "")
    shot = (lambda name: pg.locator(".gui-panel").screenshot(path=f"{shots}/{name}.png")) if shots else (lambda name: None)
    pg = page
    bid = pg.evaluate("() => import('/static/js/link.js').then(m => m.command('town.build', { type: 'watchtower' }))")
    add = _hut(pg, bid).locator(".gui-tower__add")              # the empty tower's card: the one thing to do
    add.wait_for(state="visible", timeout=WAIT_MS)
    add.click()
    panel = pg.locator(".gui-panel")
    tiles = panel.locator(".gui-add__tile")
    tiles.first.wait_for(state="visible", timeout=WAIT_MS)          # no source: the panel opens on the picker
    assert pg.locator(".gui-modal").count() == 0 and tiles.count() == 8          # GitLab and Discord too
    groups = panel.locator(".gui-add__group-title").all_inner_texts()            # in groups; Calendar has none yet
    assert groups == ["Messengers", "Mail", "Code", "Other"]
    assert "Slack" in panel.locator(".gui-add__group", has_text="Messengers").inner_text()
    assert panel.locator(".gui-panel__back").count() == 0                        # the first step: no ← Back
    panel.locator(".gui-add__tile", has_text="GitHub").locator(".ok-tone-ok").wait_for(timeout=WAIT_MS)   # ✓ gh · ann
    shot("1-picker")
    panel.locator("#add-link-" + bid).fill("https://acme.atlassian.net/browse/WEB-3")
    panel.get_by_role("button", name="Continue").click()
    panel.locator("#add-email-" + bid).wait_for(state="visible", timeout=WAIT_MS)
    assert panel.locator("#add-site-" + bid).count() == 0          # the link said the site
    back = panel.locator(".gui-panel__back")                                      # past it: ← Back in the top right
    assert back.is_visible() and panel.locator(".gui-add__foot", has_text="Back").count() == 0
    back.click()
    tiles.first.wait_for(state="visible", timeout=WAIT_MS)
    panel.locator("#add-link-" + bid).fill("https://acme.atlassian.net/browse/WEB-3")
    panel.get_by_role("button", name="Continue").click()
    panel.locator("#add-email-" + bid).wait_for(state="visible", timeout=WAIT_MS)
    panel.locator("#add-email-" + bid).fill("ann@acme.io")
    panel.locator("#add-token-" + bid).fill("t" * 24)
    shot("2-login")
    panel.get_by_role("button", name="Continue").click()
    panel.locator(".gui-add__options li", has_text="SUP").wait_for(state="visible", timeout=WAIT_MS)
    shot("3-what")
    whole = panel.locator(".gui-add__switch", has_text="Everything")             # §6: the whole site, an intent asked
    whole.click()
    panel.locator("#add-intent-" + bid).wait_for(state="visible", timeout=WAIT_MS)
    assert panel.locator(".gui-add__options").count() == 0
    shot("3b-everything")
    whole.click()
    panel.locator(".gui-add__options li", has_text="SUP").wait_for(state="visible", timeout=WAIT_MS)
    panel.get_by_role("button", name="Check", exact=True).click()
    panel.locator(".gui-add__verdict", has_text="It hears Jira").wait_for(state="visible", timeout=WAIT_MS)
    shot("4-check")
    panel.get_by_role("button", name="Add Jira").click()
    panel.locator(".gui-info").first.wait_for(state="visible", timeout=WAIT_MS)       # done: the tower's Info
    assert panel.locator(".gui-panel__back").count() == 0
    panel.locator(".gui-panel__tabs .ok-tab", has_text="Work").click()
    panel.locator(".gui-tower__chips .ok-chip", has_text="jira").wait_for(state="visible", timeout=WAIT_MS)
    shot("5-feed")
    # the feed lists the unread; Read too adds the read ones (docs/design/watchtower-automation.md §2 H)
    from orkcraft.realm import watch
    w = gui[0].host.town.worker(bid)
    for i, title in enumerate(["Ann in WEB-5: the old one", "Ben in WEB-7: Login loops after the update"]):
        w.add_signal(watch.Signal(f"2026-10-02T05:{10 + i}:00", "jira", title, "", f"WEB-{5 + i}"))
    w.mark_read([w.signals[1]])
    w.changed()
    panel.locator(".gui-tower__count-head", has_text="Unread · 1").wait_for(state="visible", timeout=WAIT_MS)
    assert panel.locator(".gui-tower__row").count() == 1 and "Login loops" in panel.locator(".gui-tower__row").inner_text()
    card = _hut(pg, bid).locator(".gui-tower__msg")
    assert "Ben" in card.inner_text() and "05:11" in card.inner_text()            # the closed card: the newest unread
    panel.get_by_role("button", name="Read too · ").click()
    panel.locator(".gui-tower__row", has_text="the old one").wait_for(state="visible", timeout=WAIT_MS)
    panel.get_by_role("button", name="Only unread").click()
    panel.get_by_role("button", name="Sources & intent").click()
    panel.locator(".gui-tower__source", has_text="Jira").wait_for(state="visible", timeout=WAIT_MS)
    shot("6-sources")
    # the token is revoked: the next look fails as the login, and Log in again fixes it in one step (§8)
    monkeypatch.setattr(WatchtowerWorker, "feed_opener", Opener({**ATL, "acme.atlassian.net/rest/api/3/myself": 401}))
    panel.get_by_role("button", name="Check now").click()
    failing = panel.locator(".gui-tower__failing", has_text="the token was refused")
    failing.wait_for(state="visible", timeout=WAIT_MS)
    row = panel.locator(".gui-tower__source.is-bad", has_text="Jira")
    row.get_by_role("button", name="Log in again").wait_for(state="visible", timeout=WAIT_MS)
    shot("7-failing")
    monkeypatch.setattr(WatchtowerWorker, "feed_opener", Opener(ATL))
    failing.get_by_role("button", name="Log in again").click()
    panel.locator(".gui-add__sub", has_text="Log in again").wait_for(state="visible", timeout=WAIT_MS)
    assert panel.locator("#add-site-" + bid).count() == 0          # the site is kept
    panel.locator("#add-email-" + bid).fill("ann@acme.io")
    panel.locator("#add-token-" + bid).fill("n" * 24)
    shot("8-login-again")
    panel.get_by_role("button", name="Continue").click()
    panel.locator(".gui-add__options li", has_text="SUP").wait_for(state="visible", timeout=WAIT_MS)
    panel.get_by_role("button", name="Check", exact=True).click()
    panel.get_by_role("button", name="Keep it").click()
    panel.locator(".gui-info").first.wait_for(state="visible", timeout=WAIT_MS)
    panel.locator(".gui-panel__tabs .ok-tab", has_text="Work").click()
    panel.locator(".gui-tower__chips .ok-chip", has_text="jira").wait_for(state="visible", timeout=WAIT_MS)
    panel.get_by_role("button", name="Check now").click()
    pg.wait_for_function("() => !document.querySelector('.gui-panel .gui-tower__failing')", timeout=WAIT_MS)
    pg.evaluate("id => import('/static/js/link.js').then(m => m.command('town.demolish', { id }))", bid)


def test_a_tower_hears_jira_through_claudes_connection_without_a_token(page, monkeypatch):
    """A service Claude Code has a connection for reads ✓ in Claude; its step 1 offers Claude's connection, step 2
    asks what to look for, how often and the most a day, Check makes one (recorded) look, and Add writes the
    agent line (docs/design/watchtower-quick-add.md §7.3). `ORKCRAFT_SHOTS` keeps screenshots."""
    from orkcraft.core.workers.watchtower import WatchtowerWorker
    from tests.test_watchtower_agent import MCP_LIST, Run, events, mcp_list
    monkeypatch.setattr(WatchtowerWorker, "mcp_runner", staticmethod(mcp_list(MCP_LIST)))
    monkeypatch.setattr(WatchtowerWorker, "agent_runner", staticmethod(Run(events())))
    shots = os.environ.get("ORKCRAFT_SHOTS", "")
    shot = (lambda name: pg.locator(".gui-panel").screenshot(path=f"{shots}/{name}.png")) if shots else (lambda name: None)
    pg = page
    bid = pg.evaluate("() => import('/static/js/link.js').then(m => m.command('town.build', { type: 'watchtower' }))")
    add = _hut(pg, bid).locator(".gui-tower__add")
    add.wait_for(state="visible", timeout=WAIT_MS)
    add.click()
    panel = pg.locator(".gui-panel")
    jira = panel.locator(".gui-add__tile", has_text="Jira")
    jira.locator(".ok-tone-ok", has_text="in Claude").wait_for(timeout=WAIT_MS)
    panel.locator(".gui-add__tile", has_text="Slack").locator(".gui-add__mark", has_text="needs a login").wait_for(timeout=WAIT_MS)
    shot("c1-picker")
    jira.click()
    use = panel.get_by_role("button", name="Use Claude's connection")
    use.wait_for(state="visible", timeout=WAIT_MS)
    assert panel.locator("#add-token-" + bid).count() == 1           # the token way stays, first
    shot("c2-login")
    use.click()
    panel.locator("#add-ask-" + bid).wait_for(state="visible", timeout=WAIT_MS)
    panel.locator("#add-ask-" + bid).fill("mentions of me in project WEB")
    panel.locator("#add-every-" + bid).select_option("15")
    shot("c3-ask")
    panel.get_by_role("button", name="Check", exact=True).click()
    panel.locator(".gui-add__verdict", has_text="It hears Jira").wait_for(state="visible", timeout=WAIT_MS)
    assert "every 15 min, a model run each look" in panel.locator(".gui-add__verdict").inner_text()
    shot("c4-check")
    panel.get_by_role("button", name="Add Jira").click()
    panel.locator(".gui-info").first.wait_for(state="visible", timeout=WAIT_MS)
    panel.locator(".gui-panel__tabs .ok-tab", has_text="Work").click()
    panel.get_by_role("button", name="Sources & intent").click()
    panel.locator(".gui-tower__source", has_text="via Claude · atlassian · every 15 min").wait_for(state="visible", timeout=WAIT_MS)
    shot("c5-sources")
    pg.evaluate("id => import('/static/js/link.js').then(m => m.command('town.demolish', { id }))", bid)


def test_a_review_board_is_set_up_in_its_panel_burns_when_it_asks_and_sends_down_an_exit(page, monkeypatch):
    """A new Review board: its card says Set up the review; the purpose, the clan picked for it and the exits happen
    in the panel; a review that asks sets the hut on fire, and an exit's button sends the document on with the
    verdict on top (docs/design/review-board.md). The clan is a fake; `ORKCRAFT_SHOTS` keeps screenshots."""
    from orkcraft.core.workers.council import CouncilWorker
    from tests.test_review_board import Clan
    shots = os.environ.get("ORKCRAFT_SHOTS", "")
    shot = (lambda name, what=".gui-panel": pg.locator(what).first.screenshot(path=f"{shots}/{name}.png")) if shots \
        else (lambda name, what=".gui-panel": None)
    pg = page
    call = lambda name, args: pg.evaluate("([n, a]) => import('/static/js/link.js').then(m => m.command(n, a))", [name, args])
    bid = call("town.build", {"type": "council"})
    setup = _hut(pg, bid).locator(".council-card__setup")
    setup.wait_for(state="visible", timeout=WAIT_MS)
    shot("rb-0-card", f'.gui-hut[data-id="{bid}"]')
    setup.click()
    panel = pg.locator(".gui-panel")
    panel.locator(f"#purpose-{bid}").wait_for(state="visible", timeout=WAIT_MS)
    assert pg.locator(".gui-modal").count() == 0
    panel.get_by_role("button", name="PRD review").click()
    shot("rb-1-purpose")
    panel.get_by_role("button", name="Propose the clan").click()
    panel.locator(".council-setup__item", has_text="Risks analyzer").wait_for(state="visible", timeout=WAIT_MS)
    shot("rb-2-clan")
    panel.get_by_role("button", name="Next: the exits").click()
    panel.locator(".council-setup__exit").first.wait_for(state="visible", timeout=WAIT_MS)
    panel.locator(".gui-panel__back").click()                                    # ← Back, top right: the clan again
    panel.locator(".council-setup__item", has_text="Risks analyzer").wait_for(state="visible", timeout=WAIT_MS)
    panel.get_by_role("button", name="Next: the exits").click()
    panel.locator(".council-setup__exit").first.wait_for(state="visible", timeout=WAIT_MS)
    panel.locator(".council-setup__exit").first.fill("To development")
    shot("rb-3-exits")
    panel.get_by_role("button", name="Save the board").click()
    panel.locator(".gui-info").first.wait_for(state="visible", timeout=WAIT_MS)       # saved: the board's Info
    panel.locator(".gui-panel__tabs .ok-tab", has_text="Work").click()
    panel.locator(".council-clan").wait_for(state="visible", timeout=WAIT_MS)

    monkeypatch.setattr(CouncilWorker, "runner", staticmethod(
        Clan("DECISION: ask\nShip it now, or after the audit?", {"Product critic": "CHANGES: the metric needs a baseline"})))
    call("act", {"id": bid, "act": "review", "args": {"text": "# PRD: Onboarding v2\n\nFive minutes to a working town."}})
    pg.locator(f'.gui-hut.is-alert[data-id="{bid}"]').wait_for(state="visible", timeout=WAIT_MS)            # it burns
    ask = panel.locator(".council-ask.is-asking")
    ask.wait_for(state="visible", timeout=WAIT_MS)
    shot("rb-4-asks")
    ask.locator("input").fill("Ship it; add the baseline next sprint")
    assert ask.get_by_role("button", name="To development · not connected").is_disabled()       # no road: no exit
    ask.get_by_role("button", name="Back to the author").click()
    sent = panel.locator(".council-sent")
    sent.wait_for(state="visible", timeout=WAIT_MS)
    sent.locator("summary").click()
    assert "Review notes — Back to the author" in sent.inner_text() and "Ship it; add the baseline" in sent.inner_text()
    shot("rb-5-sent")
    shot("rb-6-card", f'.gui-hut[data-id="{bid}"]')
    call("town.demolish", {"id": bid})


def test_a_review_boards_exit_with_no_road_is_a_stub_pulled_to_a_building(page):
    """A named exit with no road is a dashed stub off the board with its name; pulled to a building, the road is laid
    for that exit and signed with its name (docs/design/review-board.md §2). `ORKCRAFT_SHOTS` keeps screenshots."""
    pg = page
    shots = os.environ.get("ORKCRAFT_SHOTS", "")
    call = lambda name, args: pg.evaluate("([n, a]) => import('/static/js/link.js').then(m => m.command(n, a))", [name, args])
    bid = call("town.build", {"type": "council"})
    to = call("town.build", {"type": "pit"})
    call("act", {"id": bid, "act": "setup_save", "args": {
        "purpose": "PRDs before development",
        "members": [{"role": "Product critic", "checks": "scope", "tier": "", "veto": False}],
        "exits": [{"name": "To development", "when": "ready to build"}, {"name": "To the designer", "when": "flows unclear"}]}})
    pg.keyboard.press("Escape")
    stub = pg.locator(".gui-loose", has_text="To development")
    stub.wait_for(state="visible", timeout=WAIT_MS)
    assert "no road" in stub.get_attribute("title") and pg.locator(".gui-loose").count() == 2
    if shots:
        pg.locator(".gui-town").screenshot(path=f"{shots}/rb-7-stubs.png")
    s, (tx, ty) = stub.locator(".gui-loose__stub").bounding_box(), _drop_at(pg, to)   # its title: a folded Pit is no taller
    pg.mouse.move(s["x"] + 4, s["y"] + 1)
    pg.mouse.down()
    pg.mouse.move(tx, ty, steps=6)
    pg.mouse.up()
    pg.locator(".gui-sign", has_text="To development").and_(pg.locator(":not(.gui-loose__sign)")) \
        .wait_for(state="visible", timeout=WAIT_MS)                          # the road, signed with the exit
    pg.wait_for_function("() => document.querySelectorAll('.gui-loose').length === 1", timeout=WAIT_MS)
    assert pg.locator(".gui-modal").count() == 0                                # laid at once, nothing asked
    if shots:
        pg.locator(".gui-town").screenshot(path=f"{shots}/rb-8-road.png")
    call("town.demolish", {"id": to})
    call("town.demolish", {"id": bid})


def test_a_signposts_route_with_no_road_is_a_stub_pulled_to_a_building(page, gui):
    """The same stubs for a Signpost: each route of its rules with no road out; pulled to a building, the road is laid
    for that route and signed with it. `ORKCRAFT_SHOTS` keeps a screenshot."""
    pg = page
    shots = os.environ.get("ORKCRAFT_SHOTS", "")
    call = lambda name, args: pg.evaluate("([n, a]) => import('/static/js/link.js').then(m => m.command(n, a))", [name, args])
    post = call("town.build", {"type": "signpost"})
    to = call("town.build", {"type": "pit"})
    town = gui[0].host.town                                     # the rules, as the steward would write them
    town.call(lambda: town.worker(post).set_rules(["bugs: contains error", "rest: else"]))
    pg.keyboard.press("Escape")
    stub = pg.locator(f'.gui-loose[aria-label="Connect bugs"]')
    stub.wait_for(state="visible", timeout=WAIT_MS)
    if shots:
        pg.locator(".gui-town").screenshot(path=f"{shots}/sp-1-stubs.png")
    s, (tx, ty) = stub.locator(".gui-loose__stub").bounding_box(), _drop_at(pg, to)   # its title: a folded Pit is no taller
    pg.mouse.move(s["x"] + 4, s["y"] + 1)
    pg.mouse.down()
    pg.mouse.move(tx, ty, steps=6)
    pg.mouse.up()
    pg.wait_for_function("() => document.querySelectorAll('.gui-loose').length === 1", timeout=WAIT_MS)
    assert pg.locator(".gui-signs .gui-sign", has_text="bugs").count() == 1 and pg.locator(".gui-modal").count() == 0
    if shots:
        pg.locator(".gui-town").screenshot(path=f"{shots}/sp-2-road.png")
    call("town.demolish", {"id": to})
    call("town.demolish", {"id": post})


def test_settings_turn_an_ai_tool_on_and_make_it_the_main_one(page):
    """Settings → AI tools: a tool turned on joins the main tool's choices; picking it says decisions run there."""
    pg = page
    pg.locator(".gui-hud .gui-hud__menu").click()
    modal = pg.locator(".gui-modal")
    modal.wait_for(state="visible", timeout=WAIT_MS)
    tools = modal.get_by_role("group", name="AI tools")
    tools.get_by_role("button", name="π pi").click()
    main = modal.get_by_role("group", name="Main tool")
    main.get_by_role("button", name="π pi").wait_for(timeout=WAIT_MS)
    main.get_by_role("button", name="π pi").click()
    pg.wait_for_function("() => document.querySelector('.gui-modal').textContent.includes('Decisions run on pi')",
                         timeout=WAIT_MS)
    shot = os.environ.get("ORKCRAFT_SHOT")
    if shot:
        modal.screenshot(path=shot)
    settings = pg.evaluate("() => import('/static/js/link.js').then(m => m.command('town.settings'))")
    assert settings["main_tool"] == "pi" and settings["main_now"] == "pi"
    pg.evaluate("() => import('/static/js/link.js').then(m => m.command('town.settings.set', "
                "{ tools: { pi: false }, main_tool: '' }))")


def test_settings_choose_a_tiers_model_and_reset_it(page):
    """Settings → AI tools: each tier of a tool that is on runs on Latest of its family; another model typed is
    kept and said; Reset to latest drops it."""
    from orkcraft import settings
    pg = page
    pg.evaluate("() => import('/static/js/link.js').then(m => m.command('town.settings.set', { tools: { agy: true } }))")
    pg.locator(".gui-hud .gui-hud__menu").click()
    modal = pg.locator(".gui-modal")
    modal.wait_for(state="visible", timeout=WAIT_MS)
    pick = modal.get_by_label("Antigravity: the 🔮 Elder model", exact=True)
    pick.wait_for(timeout=WAIT_MS)
    assert "Latest Gemini Pro High" in pick.locator("option:checked").inner_text()
    pick.select_option(label="Another model…")
    modal.get_by_label("Antigravity: the 🔮 Elder model's name").fill("gemini-3.0-pro-high")
    modal.get_by_role("button", name="Use it").click()
    pg.wait_for_function("() => document.querySelector('.gui-modal').textContent.includes('Runs on gemini-3.0-pro-high')",
                         timeout=WAIT_MS)
    shot = os.environ.get("ORKCRAFT_SHOT")
    if shot:
        modal.screenshot(path=shot)
    assert settings.load().tier_models == {"agy": {"elder": "gemini-3.0-pro-high"}}
    modal.get_by_role("button", name="Reset to latest").click()
    pg.wait_for_function("() => !document.querySelector('.gui-modal').textContent.includes('Reset to latest')",
                         timeout=WAIT_MS)
    assert settings.load().tier_models == {}
    pg.evaluate("() => import('/static/js/link.js').then(m => m.command('town.settings.set', { tools: { agy: false } }))")


def test_settings_accounts_open_the_connect_google_wizard(page):
    """Settings → Accounts: Connect Google opens the wizard, five steps with a link to each page of Google Cloud;
    once the client is pasted, step 5 signs in. `ORKCRAFT_SHOTS` keeps screenshots."""
    pg = page
    shots = os.environ.get("ORKCRAFT_SHOTS", "")
    pg.locator(".gui-hud .gui-hud__menu").click()
    modal = pg.locator(".gui-modal")
    modal.wait_for(state="visible", timeout=WAIT_MS)
    modal.get_by_role("button", name="Connect Google", exact=True).click()
    wizard = pg.locator(".gui-modal", has=pg.locator(".gui-acc__steps"))
    wizard.wait_for(state="visible", timeout=WAIT_MS)
    links = wizard.locator("a").evaluate_all("els => els.map((e) => e.href)")
    assert any("projectcreate" in x for x in links) and any("enableapi" in x for x in links)
    assert any("/auth/clients/create" in x for x in links)
    if shots:
        wizard.locator(".ok-dialog").screenshot(path=f"{shots}/google-wizard.png")
    wizard.get_by_placeholder("1234-abc.apps.googleusercontent.com").fill(
        "123456789-abcdefgh123.apps.googleusercontent.com")
    wizard.get_by_placeholder("GOCSPX-…").fill("GOCSPX-abcdefghijklmn")
    wizard.get_by_role("button", name="Save the client").click()
    wizard.get_by_role("button", name="Sign in with Google").wait_for(timeout=WAIT_MS)
    if shots:
        wizard.locator(".ok-dialog").screenshot(path=f"{shots}/google-wizard-signin.png")
    pg.evaluate("() => import('/static/js/link.js').then(m => m.command('google.forget_client'))")


def test_a_loot_cart_is_edited_in_the_window_and_a_file_of_its_branch_rejected(page, gui):
    """A held cart in the whole town's width: a file its task committed on its branch is rejected (it leaves the
    branch's list, kept aside) and brought back; its picture shows in the window; Edit writes the person's version
    there, and Accept takes it. `ORKCRAFT_SHOTS` keeps screenshots."""
    from orkcraft.realm import pipes
    pg = page
    shots = os.environ.get("ORKCRAFT_SHOTS", "")
    call = lambda name, args: pg.evaluate("([n, a]) => import('/static/js/link.js').then(m => m.command(n, a))", [name, args])
    town = gui[0].host.town
    root = town.repo_root
    git = lambda cwd, *a: subprocess.run(["git", "-c", "user.email=test@orkcraft.local", "-c", "user.name=Test Runner", *a],
                                         cwd=cwd, check=True, capture_output=True, text=True).stdout.strip()
    base = git(root, "rev-parse", "--abbrev-ref", "HEAD")
    wt = root / ".orkcraft" / "worktrees" / "loot-browser"
    git(root, "worktree", "add", "-q", "-b", "pool/camp/loot-browser", str(wt), "HEAD")
    (wt / "notes.md").write_text("# Notes\n")
    (wt / "shot.svg").write_text('<svg xmlns="http://www.w3.org/2000/svg" width="40" height="20"><rect width="40" height="20" fill="red"/></svg>')
    git(wt, "add", "-A")
    git(wt, "commit", "-qm", "work")
    git(wt, "config", "user.email", "test@orkcraft.local")
    git(wt, "config", "user.name", "Test Runner")
    bid = call("town.build", {"type": "loot"})
    hop = pipes.hop("camp", "grub", "agent", 900, 0.04, str(wt.relative_to(root)), "pool/camp/loot-browser", "error", base=base)
    cart = pipes.Payload(pipes.TEXT, "## Done\n\nthe notes", "camp", "pool.done", "The notes", (hop,), "LB-1")
    town.call(lambda: town.worker(bid).receive(cart, "The notes", cart.value))
    pg.keyboard.press("Escape")
    _hut(pg, bid).locator(".gui-hut__title").click()
    pg.locator(".gui-panel .gui-panel__full").click()
    pg.locator(".loot-card", has_text="The notes").click()
    files = pg.locator(".loot-detail .ok-file")
    files.first.wait_for(state="visible", timeout=WAIT_MS)
    files.filter(has_text="shot.svg").click()
    pg.locator(".loot-branch-file img.loot-what__pic").wait_for(state="visible", timeout=WAIT_MS)   # the picture, here
    files.filter(has_text="notes.md").click()
    pg.get_by_role("button", name="Reject this file", exact=True).click()
    pg.locator(".loot-rejected", has_text="notes.md").wait_for(state="visible", timeout=WAIT_MS)
    assert files.filter(has_text="notes.md").count() == 0 and not (wt / "notes.md").exists()
    if shots:
        pg.locator(".gui-panel").screenshot(path=f"{shots}/loot-1-rejected.png")
    pg.locator(".loot-rejected").get_by_role("button", name="Bring it back", exact=True).click()
    files.filter(has_text="notes.md").wait_for(state="visible", timeout=WAIT_MS)
    pg.locator(".loot-detail").get_by_role("button", name="Edit", exact=True).click()
    box = pg.locator(".loot-edit__text")
    box.fill("## Done\n\nthe notes, checked")
    if shots:
        pg.locator(".gui-panel").screenshot(path=f"{shots}/loot-2-editor.png")
    pg.get_by_role("button", name="Accept this version", exact=True).click()
    pg.wait_for_function("() => !document.querySelector('.loot-card')", timeout=WAIT_MS)
    stored = town.worker(bid).stored
    assert len(stored) == 1 and "the notes, checked" in (root / stored[0].path).read_text()
    pg.keyboard.press("Escape")
    call("town.demolish", {"id": bid})


def test_a_folded_hut_shows_its_title_peeks_under_a_drag_and_unfolds(page):
    """docs/design/folded-cards.md: a Pit is built folded — its title bar alone; a drag held over it peeks its card
    over the hut under it, which does not move, and the drop goes in; ▸ unfolds it, the right click folds it back.
    `ORKCRAFT_SHOTS` keeps screenshots."""
    pg = page
    shots = os.environ.get("ORKCRAFT_SHOTS", "")
    shot = (lambda name: pg.locator(".gui-town").screenshot(path=f"{shots}/{name}.png")) if shots else (lambda name: None)
    call = lambda name, args: pg.evaluate("([n, a]) => import('/static/js/link.js').then(m => m.command(n, a))", [name, args])
    pit, pool = call("town.build", {"type": "pit"}), call("town.build", {"type": "barracks"})
    call("hut.move", {"id": pit, "x": 0.05, "y": 0.05})
    call("hut.move", {"id": pool, "x": 0.05, "y": 0.2})
    pg.keyboard.press("Escape")
    hut, under = _hut(pg, pit), _hut(pg, pool)
    pg.locator(f'.gui-hut.is-folded[data-id="{pit}"]').wait_for(state="visible", timeout=WAIT_MS)
    assert "is-folded" not in under.get_attribute("class")              # a Barracks is built open
    assert hut.locator(".gui-pit__icon").count() == 0 and hut.locator(".gui-hut__name").inner_text().strip()
    pg.wait_for_timeout(300)
    shot("fold-1-folded")
    below = under.bounding_box()
    dt = pg.evaluate_handle("() => { const d = new DataTransfer(); d.setData('text/plain', 'a folded drop'); return d; }")
    hut.locator(".gui-hut__title").dispatch_event("dragenter", {"dataTransfer": dt})
    peek = hut.locator(".gui-hut__peek .gui-pit__icon")
    peek.wait_for(state="visible", timeout=WAIT_MS)                     # the card peeks out…
    assert under.bounding_box() == below                                 # …over the hut under it, which stays
    shot("fold-2-peek")
    hut.locator(".gui-pit__card").dispatch_event("dragover", {"dataTransfer": dt})
    hut.locator(".gui-pit__card").dispatch_event("drop", {"dataTransfer": dt})
    hut.locator(".gui-hut__mark", has_text="1 dropped").wait_for(state="visible", timeout=WAIT_MS)   # it went in
    peek.wait_for(state="detached", timeout=WAIT_MS)                    # and the peek folds again
    assert pg.locator(".gui-panel").count() == 0
    hut.hover()
    hut.locator(".gui-hut__fold").click()                               # ▸ unfolds it for good
    hut.locator(".gui-pit__icon").wait_for(state="visible", timeout=WAIT_MS)
    shot("fold-3-unfolded")
    assert server_building(pg, pit)["pinned"] is False and pg.locator(".gui-panel").count() == 0
    hut.locator(".gui-hut__title").click(button="right")
    pg.locator(".gui-menu__item, [role=menuitem]", has_text="Fold the card").first.click()
    pg.locator(f'.gui-hut.is-folded[data-id="{pit}"]').wait_for(state="visible", timeout=WAIT_MS)
    for bid in (pit, pool):
        call("town.demolish", {"id": bid})


def test_the_bare_map_and_the_warchiefs_line_fold_the_quiet_ones_and_unfold_all(page):
    """docs/design/folded-cards.md §4: Fold the quiet ones and Unfold all on the bare map; `/fold @name`, `/unfold`."""
    pg = page
    call = lambda name, args: pg.evaluate("([n, a]) => import('/static/js/link.js').then(m => m.command(n, a))", [name, args])
    pool, forge = call("town.build", {"type": "barracks"}), call("town.build", {"type": "forge"})
    call("hut.move", {"id": pool, "x": 0.05, "y": 0.05})
    call("hut.move", {"id": forge, "x": 0.4, "y": 0.05})
    pg.keyboard.press("Escape")
    folded = lambda bid: pg.locator(f'.gui-hut.is-folded[data-id="{bid}"]')
    _hut(pg, forge).wait_for(state="visible", timeout=WAIT_MS)
    room = pg.locator(".gui-town__room").bounding_box()
    pg.mouse.click(room["x"] + room["width"] * 0.5, room["y"] + room["height"] * 0.6, button="right")
    pg.locator(".gui-menu__item", has_text="Fold the quiet ones").click()
    folded(pool).wait_for(state="visible", timeout=WAIT_MS)
    folded(forge).wait_for(state="visible", timeout=WAIT_MS)
    pg.mouse.click(room["x"] + room["width"] * 0.5, room["y"] + room["height"] * 0.6, button="right")
    assert pg.locator(".gui-menu__item", has_text="Fold the quiet ones").count() == 0     # nothing left to fold
    pg.locator(".gui-menu__item", has_text="Unfold all").click()
    pg.wait_for_function("() => !document.querySelector('.gui-hut.is-folded')", timeout=WAIT_MS)
    _line(pg, "/fold @Agent pool")
    folded(pool).wait_for(state="visible", timeout=WAIT_MS)
    assert folded(forge).count() == 0
    _line(pg, "/unfold")
    pg.wait_for_function("() => !document.querySelector('.gui-hut.is-folded')", timeout=WAIT_MS)
    for bid in (pool, forge):
        call("town.demolish", {"id": bid})


def test_a_task_that_settles_says_when_it_goes_and_what_joined_it(page, gui):
    """A send_new board holds a new task (⏳ goes at …, Send now); a related one joins it (↳ with …, +1 added) and
    Split off takes it out again; a near one asks Join or Keep apart (docs/design/settle-and-join.md)."""
    pg = page
    server, _ = gui
    bid = pg.evaluate("() => import('/static/js/link.js').then(m => m.command('town.build', { type: 'fields' }))")
    w = server.host.town.worker(bid)
    w.save_config({"send_new": True, "path": "SETTLE.md", "settle": 120})
    first = w.add("Make the CSV export", "todo")
    w.add("New design for the CSV export: the button on the right", "todo")
    w.add("Fix the login bug", "todo")
    w.add("Login page design", "todo")
    _hut(pg, bid).locator(".gui-hut__title").click()
    _panel(pg, "Work")
    panel = pg.locator(".gui-panel")
    settling = panel.locator(".fields-settle")
    settling.filter(has_text="goes at").filter(has_text="+1 added").wait_for(state="visible", timeout=WAIT_MS)
    joined = settling.filter(has_text="↳ with “Make the CSV export”")
    joined.wait_for(state="visible", timeout=WAIT_MS)
    settling.filter(has_text="Looks like").wait_for(state="visible", timeout=WAIT_MS)
    assert "waiting to go" in _hut(pg, bid).inner_text()
    if os.environ.get("ORKCRAFT_SHOTS"):
        pg.screenshot(path=str(Path(os.environ["ORKCRAFT_SHOTS"]) / "settle.png"), full_page=True)
    joined.get_by_role("button", name="Split off").click()
    joined.wait_for(state="detached", timeout=WAIT_MS)
    assert w.held(first.id) and not w.joined_cards(first.id)
    wait = panel.get_by_label("When new tasks go to the orks")
    assert wait.input_value() == "120"
    wait.select_option("0")                                   # at once: what waited goes now
    settling.filter(has_text="goes at").first.wait_for(state="detached", timeout=WAIT_MS)
    assert w.config["settle"] == 0 and not w.waiting()
    pg.evaluate("id => import('/static/js/link.js').then(m => m.command('town.demolish', { id }))", bid)
    _hut(pg, bid).wait_for(state="detached", timeout=WAIT_MS)


def test_roads_from_one_building_into_another_are_one_road_and_its_card_lists_them(page):
    """docs/design/road-sound.md §2: the roads from one building into the same other one are drawn as one; a click
    picks all of it and its card lists each, with its handler and Remove."""
    pg = page
    shots = os.environ.get("ORKCRAFT_SHOTS", "")
    link = "import('/static/js/link.js')"
    call = lambda name, args: pg.evaluate(f"([n, a]) => {link}.then(m => m.command(n, a))", [name, args])   # noqa: E731
    a, b = call("town.build", {"type": "forge"}), call("town.build", {"type": "forge"})
    choices = [c for c in call("roads.choices", {"from": a, "to": b}) if not c.get("handler")]
    events = list(dict.fromkeys(c["event"] for c in choices))
    assert len(events) >= 2
    for event in events[:2]:
        call("roads.lay", {"from": a, "to": b, "event": event, "handler": None})
    pg.keyboard.press("Escape")
    labels = [pipes.label(e) for e in events[:2]]
    road = pg.locator(".gui-road").filter(has=pg.locator(".gui-road__label", has_text=" · ".join(labels)))
    road.wait_for(state="attached", timeout=WAIT_MS)                   # one road for two: its label names both
    road.locator(".gui-road__hit").dispatch_event("click")
    card = pg.locator(".gui-roadbar")
    card.wait_for(state="visible", timeout=WAIT_MS)
    pg.wait_for_function("() => document.querySelectorAll('.gui-roadbar__row').length === 2", timeout=WAIT_MS)
    assert "2 events" in card.locator(".gui-roadbar__head").inner_text()   # the card lists both once the page has both
    if shots:
        pg.screenshot(path=f"{shots}/road-card.png")
    card.locator(".gui-roadbar__row").first.get_by_role("button", name="Remove").click()
    pg.wait_for_function("() => document.querySelectorAll('.gui-roadbar__row').length === 1", timeout=WAIT_MS)
    assert "events" not in card.locator(".gui-roadbar__head").inner_text()     # the card stays on what is left
    card.get_by_role("button", name="Close").click()
    card.wait_for(state="hidden", timeout=WAIT_MS)
    for bid in (a, b):
        call("town.demolish", {"id": bid})


def test_the_night_round_marks_a_card_says_it_in_the_morning_and_sits_in_settings(page, gui, monkeypatch):
    """🌙 on a card the Night round found something for: a click shows its words and commits, Seen takes it off;
    an idea of the round is marked too; its morning line is the Warchief's and opens the board; Settings turns
    it off and on and has Look now (docs/design/night-round.md)."""
    from orkcraft.core import runners
    from orkcraft.realm import growth
    monkeypatch.setattr(runners, "ROUND_RUNNER", lambda prompt: ('{"ideas": []}' if "cleanup" in prompt else "NOTHING", 0.0))
    pg = page
    server, _ = gui
    host = server.host
    bid = pg.evaluate("() => import('/static/js/link.js').then(m => m.command('town.build', { type: 'fields' }))")
    w = host.town.worker(bid)
    w.save_config({"path": "NIGHT.md"})
    card = w.add("Fix the export form dates", "todo")
    idea = w.add("Test the date check", "ideas")
    w.lore.set_news(card.id, {"at": "2026-10-08T04:40:00", "commits": [["a1b2c3d", "Export form: validate the dates"]],
                              "pages": [], "words": "The export form now checks dates; the card may be done."})
    w.lore.set_idea(idea.id, "2026-10-08T04:40:00-1")
    growth.tell(host.town.repo_root, growth.News("round", "Night round: 1 card has news, 1 cleanup idea", bid, "🌙", "work"))
    host.growth.settle()
    line = pg.locator(".gui-warchief__news").filter(has_text="Night round: 1 card has news")
    line.wait_for(state="visible", timeout=WAIT_MS)
    line.get_by_role("button", name="🌙 Night round: 1 card has news, 1 cleanup idea").click()
    _panel(pg, "Work")
    panel = pg.locator(".gui-panel")
    moon = panel.locator(".ok-card", has_text="Fix the export form dates").get_by_role(
        "button", name="What's new: the Night round found something for it")
    moon.wait_for(state="visible", timeout=WAIT_MS)
    assert panel.locator(".ok-card", has_text="Test the date check").locator(".fields-mark", has_text="🌙").count() == 1
    moon.click()
    modal = pg.locator(".gui-modal")
    modal.filter(has_text="What's new · Fix the export form dates").wait_for(state="visible", timeout=WAIT_MS)
    assert "the card may be done" in modal.inner_text() and "a1b2c3d" in modal.inner_text()
    if os.environ.get("ORKCRAFT_SHOTS"):
        pg.screenshot(path=str(Path(os.environ["ORKCRAFT_SHOTS"]) / "night-news.png"))
    modal.get_by_role("button", name="Seen").click()
    moon.wait_for(state="detached", timeout=WAIT_MS)
    assert w.lore.news(card.id) == {}
    pg.locator(".gui-hud .gui-hud__menu").click()
    modal.wait_for(state="visible", timeout=WAIT_MS)
    group = modal.get_by_role("group", name="Night round: the orks look over the boards")
    group.get_by_role("button", name="Off").click()
    pg.wait_for_function("() => [...document.querySelectorAll('.gui-modal .gui-steps__one.is-on')]"
                         ".some((b) => b.closest('[role=group]').ariaLabel.startsWith('Night round') && b.textContent === 'Off')",
                         timeout=WAIT_MS)
    group.get_by_role("button", name="On").click()
    modal.get_by_role("button", name="Look now").click()
    modal.locator(".ok-tone-ok", has_text="Night round").wait_for(state="visible", timeout=WAIT_MS)
    if os.environ.get("ORKCRAFT_SHOTS"):
        modal.screenshot(path=str(Path(os.environ["ORKCRAFT_SHOTS"]) / "night-settings.png"))
    pg.keyboard.press("Escape")
    pg.evaluate("id => import('/static/js/link.js').then(m => m.command('town.demolish', { id }))", bid)
    _hut(pg, bid).wait_for(state="detached", timeout=WAIT_MS)


def test_a_narrow_window_shows_the_buildings_as_a_list_of_cards(gui):
    """A phone-wide window (js/pocket.js): no map — the quiet buildings fold under one line, a tap opens a card in
    place, a swipe to the left lays out its actions, Open takes the whole building."""
    server, browser = gui
    pg = browser.new_page(viewport={"width": 390, "height": 844}, has_touch=True)
    errors: list[str] = []
    pg.on("pageerror", lambda e: errors.append(f"pageerror: {e}"))
    pg.goto(server.url)
    pg.wait_for_selector(".gui-pocket", timeout=WAIT_MS)
    bid = pg.evaluate("() => import('/static/js/link.js').then(m => m.command('town.build', { type: 'pit' }))")
    pg.keyboard.press("Escape")
    pg.locator(".gui-panel").wait_for(state="hidden", timeout=WAIT_MS)
    assert pg.locator(".gui-town__room, .gui-map").count() == 0           # no map, no roads, no War Map
    row = pg.locator(f"#pocket-{bid}")
    if not row.count():                                                    # quiet: folded under Buildings
        pg.locator(".gui-pocket__jump", has_text="uildings").click()
    row.wait_for(state="visible", timeout=WAIT_MS)
    row.locator(".gui-pocket__head").click()
    row.locator(".gui-pocket__body").wait_for(state="visible", timeout=WAIT_MS)
    box = row.locator(".gui-pocket__head").bounding_box()
    y = box["y"] + box["height"] / 2
    pg.mouse.move(box["x"] + box["width"] - 20, y)
    pg.mouse.down()
    pg.mouse.move(box["x"] + 40, y, steps=8)
    pg.mouse.up()
    row.locator(".gui-pocket__swiped").wait_for(state="visible", timeout=WAIT_MS)
    row.locator(".gui-pocket__swiped .ok-btn.primary", has_text="Open").click()
    pg.locator(".gui-panel").wait_for(state="visible", timeout=WAIT_MS)
    pg.keyboard.press("Escape")
    pg.evaluate("id => import('/static/js/link.js').then(m => m.command('town.demolish', { id }))", bid)
    pg.close()
    assert not errors, "\n".join(errors)


def test_the_portrait_opens_its_menu_switches_the_look_and_holds_the_noise(page):
    """The person framed over the town's top-left corner (docs/design/portrait.md): its menu heads with You, Camp
    turns to Office (no sprites, the monogram, the office theme) and back, Do not disturb strikes the horn on its
    toggle (never a mark on the head), and
    Fire on the roofs turns off and on there, no longer in Town settings."""
    pg = page
    assert pg.locator(".gui-hud .gui-portrait").count() == 0              # a wide window: out of the HUD
    portrait = pg.locator(".gui-portrait-slot.is-corner .gui-portrait")
    assert portrait.locator(".gui-mascot").count() == 1 and pg.evaluate("document.documentElement.dataset.look") == "camp"
    portrait.click()
    menu = pg.locator(".gui-portrait__menu")
    menu.wait_for(state="visible", timeout=WAIT_MS)
    assert menu.locator(".gui-you__deeds").count() == 1
    menu.get_by_role("button", name="Office", exact=True).click()
    pg.wait_for_function("() => document.documentElement.dataset.look === 'office'", timeout=WAIT_MS)
    assert pg.evaluate("document.documentElement.dataset.theme") == "office"
    assert portrait.locator(".gui-portrait__mono").count() == 1 and pg.locator(".gui-warchief__mono").count() == 1
    assert pg.locator(".gui-warchief__crowned").count() == 0
    dnd_row = menu.get_by_role("group", name="Do not disturb", exact=True)
    dnd_row.get_by_role("button", name="On", exact=True).click()
    pg.get_by_role("button", name="Do not disturb", exact=True).and_(pg.locator("[aria-pressed=true]")).wait_for(
        state="visible", timeout=WAIT_MS)
    assert "🌙" not in portrait.inner_text()
    dnd_row.get_by_role("button", name="Off", exact=True).click()
    pg.locator(".gui-warchief__news").wait_for(state="visible", timeout=WAIT_MS)   # what gathered, said once
    assert "While you were away" in pg.locator(".gui-warchief__news").inner_text()
    pg.locator(".gui-warchief__news").get_by_role("button", name="Seen").click()   # a click away closes the menu
    menu.wait_for(state="hidden", timeout=WAIT_MS)
    portrait.click()
    menu.get_by_role("button", name="Camp", exact=True).click()
    pg.wait_for_function("() => document.documentElement.dataset.look === 'camp'", timeout=WAIT_MS)
    # Fire on the roofs is the person's now, in this menu; Town settings no longer shows it
    fire = menu.get_by_role("group", name="Fire on the roofs", exact=True)
    fire.get_by_role("button", name="Off", exact=True).click()
    fire.locator("[aria-pressed=true]", has_text="Off").wait_for(state="visible", timeout=WAIT_MS)
    fire.get_by_role("button", name="On", exact=True).click()
    fire.locator("[aria-pressed=true]", has_text="On").wait_for(state="visible", timeout=WAIT_MS)
    menu.get_by_role("button", name="Town settings…").click()
    pg.get_by_role("dialog", name="Town settings").wait_for(state="visible", timeout=WAIT_MS)
    assert pg.get_by_role("group", name="Fire on the roofs").count() == 0
    pg.keyboard.press("Escape")
    pg.get_by_role("dialog", name="Town settings").wait_for(state="hidden", timeout=WAIT_MS)
    menu.wait_for(state="hidden", timeout=WAIT_MS)                       # Town settings… closed the menu
    # its quick toggles beside it: Do not disturb on and off, the look to Office and back, without the menu
    dnd, look = pg.get_by_role("button", name="Do not disturb", exact=True), pg.get_by_role("button", name="Office look", exact=True)
    horn = lambda: dnd.locator("img.gui-portrait__horn").get_attribute("src")
    assert horn() == "/ds/sprites/icons/notify-on.png"                    # Camp: the horn, the town may call
    dnd.click()
    pg.wait_for_function("() => document.querySelector('.gui-portrait__horn').src.endsWith('notify-off.png')", timeout=WAIT_MS)
    assert dnd.get_attribute("aria-pressed") == "true" and "🌙" not in portrait.inner_text()   # struck through
    dnd.click()
    pg.wait_for_function("() => document.querySelector('.gui-portrait__horn').src.endsWith('notify-on.png')", timeout=WAIT_MS)
    look.click()
    pg.wait_for_function("() => document.documentElement.dataset.look === 'office'", timeout=WAIT_MS)
    look.click()
    pg.wait_for_function("() => document.documentElement.dataset.look === 'camp'", timeout=WAIT_MS)


def test_import_calendar_takes_a_file_and_a_link_in_steps_over_its_info(page, gui, tmp_path, monkeypatch):
    """The Calendar's Info: Import calendar opens a page in steps over it — a file or a link; every step after
    the first has ← Back at the window's top right; once imported, the usual Info is back and the settings
    list the calendar, a link by its host alone (docs/design/calendar-import.md)."""
    from orkcraft.realm import calendar_imports
    pg = page
    server, _ = gui
    day = dt.date.today() + dt.timedelta(days=1)
    event = lambda uid, title: (f"BEGIN:VEVENT\r\nUID:{uid}\r\nDTSTART:{day:%Y%m%d}T110000\r\n"
                                f"DTEND:{day:%Y%m%d}T113000\r\nSUMMARY:{title}\r\nEND:VEVENT\r\n")
    secret = "https://calendar.example.com/ical/private-0c9e1d/basic.ics"
    monkeypatch.setattr(calendar_imports, "fetch",
                        lambda url: "BEGIN:VCALENDAR\r\n" + event("w@x", "Team sync") + "END:VCALENDAR\r\n")
    drum = pg.evaluate("t => import('/static/js/link.js').then(m => m.command('town.build', { type: t }))", "war_drum")
    _hut(pg, drum).locator(".gui-hut__title").click()
    _info(pg)
    panel = pg.locator(".gui-panel")
    panel.get_by_role("button", name="Import calendar", exact=True).click()
    steps = panel.locator(".gui-infopage")
    steps.locator(".gui-infopage__title", has_text="Import calendar").wait_for(state="visible", timeout=WAIT_MS)
    assert steps.locator(".gui-infopage__back").count() == 0 and panel.locator(".gui-info__head").count() == 0

    steps.get_by_role("button", name="A file (.ics)").click()
    back = steps.locator(".gui-infopage__back")
    back.wait_for(state="visible", timeout=WAIT_MS)
    head, b = steps.locator(".gui-infopage__head").bounding_box(), back.bounding_box()
    assert b["x"] + b["width"] >= head["x"] + head["width"] - 2 and b["y"] - head["y"] < 8     # the top right
    back.click()
    steps.get_by_role("button", name="A link (iCal address)").wait_for(state="visible", timeout=WAIT_MS)
    steps.get_by_role("button", name="A file (.ics)").click()
    ics_file = tmp_path / "Offsite.ics"
    ics_file.write_text("BEGIN:VCALENDAR\r\n" + event("o@x", "Offsite prep") + "END:VCALENDAR\r\n")
    steps.locator(".drum-import__input").set_input_files(str(ics_file))
    steps.get_by_text("Offsite.ics").wait_for(state="visible", timeout=WAIT_MS)
    assert steps.get_by_label("Name").input_value() == "Offsite"
    steps.get_by_role("button", name="Import", exact=True).click()
    pg.locator(".ok-toast", has_text="Offsite — 1 events").wait_for(state="visible", timeout=WAIT_MS)
    panel.locator(".gui-info__head").wait_for(state="visible", timeout=WAIT_MS)       # the usual Info again
    assert panel.locator(".gui-infopage").count() == 0

    panel.get_by_role("button", name="Import calendar", exact=True).click()
    steps.get_by_role("button", name="A link (iCal address)").click()
    link = steps.get_by_label("Link")
    assert link.get_attribute("type") == "password"
    link.fill(secret.replace("https://", "webcal://"))
    steps.get_by_label("Name").fill("Team")
    steps.get_by_label("Updated").select_option("60")
    steps.get_by_role("button", name="Subscribe", exact=True).click()
    pg.locator(".ok-toast", has_text="Team — 1 events, updated every hour").wait_for(state="visible", timeout=WAIT_MS)
    panel.locator(".gui-info__head").wait_for(state="visible", timeout=WAIT_MS)
    w = server.host.town.worker(drum)
    assert sorted(e.summary for e in w.day.events) == ["Offsite prep", "Team sync"]
    assert all("private-0c9e1d" not in p.read_text(errors="replace") for p in server.host.town.repo_root.rglob("*")
               if p.is_file() and ".git" not in p.parts)                    # the link is in no file of the project
    panel.locator(".gui-panel__tabs .ok-tab", has_text="Work").click()
    settings = panel.locator(".drum-settings")
    settings.locator("summary").click()
    rows = settings.locator(".drum-imports__row")
    rows.filter(has_text="Team").filter(has_text="calendar.example.com").wait_for(state="visible", timeout=WAIT_MS)
    assert rows.count() == 2 and "private-0c9e1d" not in pg.content()
    pg.keyboard.press("Escape")
    for row in w.import_rows():                 # a demolished Calendar's worker stays: its meetings go with its imports
        pg.evaluate("([id, imp]) => import('/static/js/link.js').then(m => m.act(id, 'import_remove', { id: imp }))", [drum, row["id"]])
    pg.evaluate("id => import('/static/js/link.js').then(m => m.command('town.demolish', { id }))", drum)
    _hut(pg, drum).wait_for(state="detached", timeout=WAIT_MS)


def test_a_tool_that_failed_says_so_with_switch_retry_and_details(page, gui, monkeypatch, tmp_path):
    """An AI tool that failed (gui/failures.py): its toast says who and what, Details keeps its own words."""
    from orkcraft.realm import tool_errors
    server, _ = gui
    host = server.host
    monkeypatch.setattr(tool_errors.shutil, "which", lambda name: f"/usr/bin/{name}" if name in ("claude", "codex") else None)
    ran: list[int] = []
    error = tool_errors.ToolError("claude", "API Error: 529 {\"type\":\"overloaded_error\"}", 1)
    host.town.call(lambda: host.failures.report(error, "Recruiter", retry=lambda: ran.append(1)))
    toast = page.locator(".gui-toolerr")
    toast.wait_for(state="visible", timeout=WAIT_MS)
    assert "Claude Code hit an error" in toast.inner_text()
    assert "Ork setup: Claude Code hit a usage limit or its service is overloaded." in toast.inner_text()   # today's word
    assert toast.get_by_role("button", name="Switch to Codex").is_visible()
    marks = toast.locator('img[data-kind="harness"]')               # each tool wears its harness mark
    assert [marks.nth(i).get_attribute("src") for i in range(marks.count())] == [
        "/ds/sprites/icons/harness-claude.png", "/ds/sprites/icons/harness-codex.png"]
    toast.get_by_role("button", name="Details").click()
    assert "overloaded_error" in toast.locator("pre").inner_text()
    toast.screenshot(path=str(tmp_path / "tool-error.png"))
    page.evaluate("document.documentElement.dataset.look = 'office'")    # Office: the small coloured SVG, no sprites
    assert toast.locator(".gui-toolerr__title .gui-toolmark__svg").is_visible()
    assert not toast.locator(".gui-toolerr__title img[data-kind=harness]").is_visible()
    toast.screenshot(path=str(tmp_path / "tool-error-office.png"))
    page.evaluate("document.documentElement.dataset.look = 'camp'")
    toast.get_by_role("button", name="Retry").click()
    toast.wait_for(state="detached", timeout=WAIT_MS)
    for _ in range(50):
        if ran:
            break
        page.wait_for_timeout(100)
    assert ran == [1]
