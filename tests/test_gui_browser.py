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
    with playwright.sync_playwright() as p:
        browser = _launch(p)
        yield server, browser
        browser.close()
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
    pg.wait_for_selector(f'.gui-hut[data-id="{TOWN_HALL}"]', timeout=WAIT_MS)
    yield pg
    pg.wait_for_timeout(300)                    # what a refresh after the last step draws
    pg.close()
    assert not errors, "\n".join(errors)


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
    _hut(pg, TOWN_HALL).locator("button", has_text="Build").click()
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


def test_the_town_hall_draws_three_ways(page):
    _three_ways(page, TOWN_HALL)


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
