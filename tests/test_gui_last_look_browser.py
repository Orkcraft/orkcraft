"""👀 "Since your last look" in a real browser (Chromium through Playwright): the person comes back after two hours,
the page counts the look by itself, the greeting draws its parts with wins first, and "Back to the camp" puts it away.

Skipped where Playwright or Chromium is missing; `-m browser` runs these alone."""
from __future__ import annotations

import datetime as dt
import os
import subprocess
from pathlib import Path

import pytest

playwright = pytest.importorskip("playwright.sync_api")

from orkcraft.gui.host import Host  # noqa: E402
from orkcraft.gui.server import Server  # noqa: E402
from orkcraft.realm import checkpoint, event_log, last_look  # noqa: E402

pytestmark = pytest.mark.browser

CHROMIUM = [p for p in (os.environ.get("ORKCRAFT_CHROMIUM", ""), "/opt/pw-browsers/chromium") if p and Path(p).exists()]
WAIT_MS = 10_000


def _launch(p):
    return p.chromium.launch(executable_path=CHROMIUM[0]) if CHROMIUM else p.chromium.launch()


@pytest.fixture
def gui(tmp_path, monkeypatch):
    try:
        pw = playwright.sync_playwright().start()
        browser = _launch(pw)
    except Exception:
        pytest.skip("no Chromium for Playwright here")
    for key, value in {"ORKCRAFT_LAYOUT_FILE": tmp_path / "layout.json", "ORKCRAFT_SETTINGS_FILE": tmp_path / "settings.json",
                       "ORKCRAFT_LOOK": "camp", "XDG_CACHE_HOME": tmp_path / "cache", "ORKCRAFT_ONBOARDING": "0",
                       "ORKCRAFT_LIMITS": "0", "ORKCRAFT_COUNCIL_LLM": "0", "ORKCRAFT_WIKI_AUTO": "0",
                       "ORKCRAFT_NIGHT_ROUND": "0", "ORKCRAFT_STATE_DIR": tmp_path / "state",
                       "ORKCRAFT_NO_USAGE": "1"}.items():
        monkeypatch.setenv(key, str(value))
    repo = tmp_path / "project"
    repo.mkdir()
    (repo / "README.md").write_text("# Demo project\n", encoding="utf-8")
    git = ["git", "-c", "user.email=test@orkcraft.local", "-c", "user.name=Test Runner"]
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run([*git, "add", "-A"], cwd=repo, check=True)
    subprocess.run([*git, "commit", "-qm", "init"], cwd=repo, check=True)
    checkpoint.ensure(repo)
    # The person looked two hours ago; since then the Publisher launched one and a task was done.
    before = dt.datetime.now().astimezone() - dt.timedelta(hours=2)
    last_look.save(repo, last_look.Look(last_look.iso(before - dt.timedelta(minutes=3)), last_look.iso(before)))
    event_log.record(repo, event_log.BUILT, building="pool", kind="done", title="Fix the login")
    event_log.record(repo, event_log.BUILT, building="pub", kind="launched", title="PR #42")
    server = Server(Host(repo, auto_commit=False))
    thread = server.start_thread()
    yield server, browser
    browser.close()
    pw.stop()
    server.stop()
    thread.join(10)


def test_coming_back_the_greeting_says_what_was_built_first_and_goes_back_to_the_camp(gui):
    server, browser = gui
    pg = browser.new_page(viewport={"width": 1280, "height": 800})
    errors: list[str] = []
    pg.on("pageerror", lambda e: errors.append(f"pageerror: {e}"))
    pg.on("console", lambda m: m.type == "error" and errors.append(f"console: {m.text}"))
    pg.goto(server.url)
    pg.bring_to_front()
    if not pg.evaluate("document.hasFocus()"):         # a headless window may not hold focus: beat as the page would
        pg.wait_for_selector(".gui-warchief__face", timeout=WAIT_MS)
        pg.evaluate("import('/static/js/link.js').then(m => m.command('look.beat'))")
    greeting = pg.locator(".gui-lastlook")
    greeting.wait_for(timeout=WAIT_MS + last_look.LOOK_MIN_S * 1000)
    assert greeting.locator(".ok-dialog__title").inner_text() == "Since your last look"
    assert greeting.locator(".gui-lastlook__headline").inner_text().startswith("Since ")
    parts = greeting.locator(".ok-dialog__section").all_inner_texts()
    assert [p.lower() for p in parts][0] == "what was built"
    rows = greeting.locator(".gui-lastlook__row").all_inner_texts()
    assert rows[0].startswith("Launched: «PR #42»") and rows[1].startswith("Done: «Fix the login»")
    greeting.get_by_role("button", name="Back to the camp").click()
    greeting.wait_for(state="detached", timeout=WAIT_MS)
    pg.close()
    assert not errors, "\n".join(errors)
