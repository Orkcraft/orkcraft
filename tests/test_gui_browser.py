"""The GUI in a real browser (Chromium through Playwright): the town on a fresh project, every type of the
catalog raised through Build and looked at — closed (its card on the town), then in the panel on the right:
its Work, its Info, the whole town (docs/design/calm-town.md) — plus Lake's documents in the panel, the
Warchief's line and the right click. Each must draw, and the page must log no error.

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
    pg.wait_for_selector(".gui-warchief__face", timeout=WAIT_MS)   # Office: the Warchief's line is the hall's way in
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
    hut.locator(".gui-pit__icon").wait_for(state="visible", timeout=WAIT_MS)   # the Pit's card: only its tray
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
    work.locator(".gui-newtask").get_by_role("button", name="Send it").click()
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
