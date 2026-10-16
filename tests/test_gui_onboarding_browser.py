"""The onboarding's one fork in a real browser (docs/specs/17a-mission-starts-at-once.md):
the town step shows exactly the two cards; Start the tutorial starts Mission 1 when the town opens;
Get a ready town shows the ready towns and Describe your town, and Back returns; no Empty town in a
first session; Set up again as before. Screenshots go to docs/design/img/onboarding/ when ORKCRAFT_SHOTS is set."""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

playwright = pytest.importorskip("playwright.sync_api")

from orkcraft.gui.host import Host  # noqa: E402
from orkcraft.gui.server import Server  # noqa: E402
from orkcraft.realm import checkpoint  # noqa: E402
from tests.test_gui_browser import CHROMIUM, WAIT_MS, _launch  # noqa: E402

pytestmark = pytest.mark.browser

SHOTS = Path(__file__).resolve().parent.parent / "docs" / "design" / "img" / "onboarding"


def _shot(pg, name: str) -> None:
    if os.environ.get("ORKCRAFT_SHOTS"):
        SHOTS.mkdir(parents=True, exist_ok=True)
        pg.screenshot(path=str(SHOTS / f"{name}.png"))


@pytest.fixture
def onboarding_gui(tmp_path):
    pw = playwright.sync_playwright().start()
    browser = _launch(pw)
    mp = pytest.MonkeyPatch()
    for key, value in {"ORKCRAFT_LAYOUT_FILE": tmp_path / "layout.json",
                       "ORKCRAFT_SETTINGS_FILE": tmp_path / "settings.json",
                       "ORKCRAFT_LOOK": "camp",
                       "ORKCRAFT_CALENDARS_FILE": tmp_path / "calendars.json",
                       "XDG_CACHE_HOME": tmp_path / "cache",
                       "ORKCRAFT_ONBOARDING": "1",
                       "ORKCRAFT_LIMITS": "0",
                       "ORKCRAFT_COUNCIL_LLM": "0",
                       "ORKCRAFT_WIKI_AUTO": "0",
                       "ORKCRAFT_NIGHT_ROUND": "0",
                       "ORKCRAFT_GOOGLE": "0",
                       "ORKCRAFT_STATE_DIR": tmp_path / "state"}.items():
        mp.setenv(key, str(value))
    repo = tmp_path / "project"
    (repo / "src").mkdir(parents=True)
    (repo / "README.md").write_text("# Demo project\n\nA small project for the browser check.\n", encoding="utf-8")
    (repo / "src" / "app.py").write_text("print('hello')\n", encoding="utf-8")
    git = ["git", "-c", "user.email=test@orkcraft.local", "-c", "user.name=Test Runner"]
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run([*git, "add", "-A"], cwd=repo, check=True)
    subprocess.run([*git, "commit", "-qm", "init"], cwd=repo, check=True)
    checkpoint.ensure(repo)
    host = Host(repo, auto_commit=False)
    server = Server(host)
    thread = server.start_thread()
    yield server, browser, host
    browser.close()
    pw.stop()
    server.stop()
    thread.join(10)
    mp.undo()


def test_onboarding_one_fork_and_ready_towns_in_browser(onboarding_gui):
    server, browser, host = onboarding_gui
    pg = browser.new_page(viewport={"width": 1440, "height": 900})
    errors: list[str] = []
    pg.on("pageerror", lambda e: errors.append(f"pageerror: {e}"))
    pg.on("console", lambda m: m.type == "error" and errors.append(f"console: {m.text}"))
    pg.goto(server.url)

    # 1. Onboarding opens on Tools
    pg.wait_for_selector(".gui-onb", timeout=WAIT_MS)
    next_btn = pg.locator(".gui-onb__foot button.primary")
    next_btn.wait_for(state="visible", timeout=WAIT_MS)
    next_btn.click()

    # 2. Who are you step: select a class
    kin = pg.locator(".gui-onb__kin").first
    kin.wait_for(state="visible", timeout=WAIT_MS)
    kin.click()

    # 3. Town step: exactly the two cards, side by side, nothing else
    fork = pg.locator(".gui-onb__fork")
    fork.wait_for(state="visible", timeout=WAIT_MS)
    cards = fork.locator(".gui-onb__card")
    assert cards.count() == 2

    # Card 1: I'm new
    card1 = cards.nth(0)
    assert "I'm new: show me around" in card1.inner_text()
    assert "Build your camp one building at a time with the Workchief. About 5 minutes, free, no model." in card1.inner_text()
    assert card1.get_by_role("button", name="Start the tutorial").is_visible()

    # Card 2: Punk ork
    card2 = cards.nth(1)
    assert "Punk ork: I know orkestration" in card2.inner_text()
    assert "Start with a ready town, or describe the one you want." in card2.inner_text()
    assert card2.get_by_role("button", name="Get a ready town").is_visible()

    # Nothing else on the screen, no Empty town
    assert not pg.locator(".ok-tabs").is_visible()
    assert not pg.locator(".gui-onb__town").is_visible()
    assert not pg.locator(".gui-onb__foot").is_visible()
    assert not pg.get_by_text("Empty town").is_visible()
    _shot(pg, "fork")

    # 4. Get a ready town -> ready towns screen
    card2.get_by_role("button", name="Get a ready town").click()
    pg.locator(".ok-tabs").wait_for(state="visible", timeout=WAIT_MS)
    assert pg.locator(".gui-onb__town").is_visible()
    assert pg.get_by_role("button", name="Use this town").is_visible()
    assert pg.get_by_role("button", name="Describe your town").is_visible()
    assert not pg.get_by_text("Empty town").is_visible()
    assert pg.locator(".gui-onb__foot").get_by_role("button", name="Back").is_visible()
    _shot(pg, "ready-towns")

    # 5. Back returns to the fork
    pg.locator(".gui-onb__foot").get_by_role("button", name="Back").click()
    fork.wait_for(state="visible", timeout=WAIT_MS)
    assert cards.count() == 2
    assert not pg.locator(".ok-tabs").is_visible()

    # 6. Start the tutorial -> Mission 1 starts when town opens
    card1.get_by_role("button", name="Start the tutorial").click()
    setup = pg.locator(".gui-onb__setup")
    setup.wait_for(state="visible", timeout=WAIT_MS)
    open_btn = setup.get_by_role("button", name="Open the town")
    open_btn.wait_for(state="visible", timeout=WAIT_MS)

    # Let the raising complete
    pg.wait_for_function("() => !document.querySelector('.gui-onb__setup button.primary')?.disabled", timeout=WAIT_MS)
    open_btn.click()

    # Onboarding closes, Mission 1 begins
    pg.wait_for_selector(".gui-onb", state="detached", timeout=WAIT_MS)
    log = pg.locator(".gui-warchief__setup")
    log.wait_for(state="visible", timeout=WAIT_MS)
    assert "Mission 1" in log.inner_text()
    _shot(pg, "mission1-started")

    # 7. Set up again as before
    pg.evaluate("() => import('/static/js/link.js').then(m => m.command('onboarding.start'))")
    pg.wait_for_selector(".gui-onb", timeout=WAIT_MS)
    assert pg.locator(".gui-onb__title").text_content() in ("Your AI tools", "No AI tool here yet")
    assert "town" not in host.snapshot()["onboarding"]["steps"]
    pg.get_by_role("button", name="Cancel").click()
    pg.wait_for_selector(".gui-onb", state="detached", timeout=WAIT_MS)

    pg.close()
    assert not errors, "\n".join(errors)
