"""The Night report on the board's Today (docs/specs/32-night-gate.md §3), in a real browser against stub hosts: on the
desktop (1440 × 900) and on the phone (390 × 844), in both looks. Green → *N changes ready for main*, the steps, the
cost, Pass to main behind one confirm naming the count, Details; red → in Needs you with what failed and what the check
could not fix, no Pass. Screenshots to docs/design/img/night-gate/ when NIGHT_GATE_SHOTS is set."""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

pytest.importorskip("playwright.sync_api")

from tests.test_board_browser import StubHost  # noqa: E402
from tests.test_gui_browser import WAIT_MS, _hut, gui, page  # noqa: E402,F401  (fixtures)

pytestmark = pytest.mark.browser

SHOTS = Path(__file__).resolve().parent.parent / "docs" / "design" / "img" / "night-gate"
TAKE = bool(os.environ.get("NIGHT_GATE_SHOTS"))

GREEN = {"date": "2026-10-17", "green": True, "running": False, "count": 2, "stale": False, "passed_at": "", "error": "",
         "commits": [{"sha": "9f2c41d7e0a1", "subject": "Queue ideas while the phone has no signal", "idea": "sync"},
                     {"sha": "3b7a90c5d2e8", "subject": "Dark mode switch", "idea": "dark-mode"}],
         "steps": [{"name": "Full suite", "ok": True, "summary": "1842 passed, 12 skipped in 412s", "failed": []},
                   {"name": "Browser tests", "ok": True, "summary": "96 passed in 188s", "failed": []},
                   {"name": "Daily check", "ok": True, "summary": "both changes do what their ideas ask", "failed": []}],
         "fixed": [], "not_fixed": [], "cost": 0.62, "budget": 2.0, "dev": "3b7a90c5d2e8", "main": "1a2b3c",
         "started": "2026-10-17T03:00:04", "finished": "2026-10-17T03:21:40", "hour": 3}
RED = {**GREEN, "green": False,
       "steps": [{"name": "Full suite", "ok": False, "summary": "1 failed, 1841 passed in 409s",
                  "failed": ["tests/test_sync.py::test_queue_survives_a_restart"]},
                 {"name": "Browser tests", "ok": True, "summary": "96 passed in 190s", "failed": []},
                 {"name": "Daily check", "ok": False, "summary": "stopped at its budget, $2.00", "failed": []}],
       "not_fixed": ["tests/test_sync.py::test_queue_survives_a_restart"], "cost": 2.04}


class NightHost(StubHost):
    """The board's stub, with the night's card in Today and the gate's two commands."""

    def __init__(self, look: str, night: dict):
        super().__init__(look)
        self.night = json.loads(json.dumps(night))

    def handle(self, name, a):
        if name == "ideas.board":
            got = super().handle(name, a)
            got["today"]["night"] = self.night
            return got
        if name == "gate.pass_night":
            self.log.append((name, a))
            self.night["passed_at"] = "2026-10-17T08:12:00"
            self.rev += 1
            self.ws.send(json.dumps(self.snapshot()))
            return {"ok": True, "main": self.night["dev"], "note": ""}
        if name == "gate.run_night":
            self.log.append((name, a))
            self.night.update(running=True, started="2026-10-17T08:15:00")
            self.rev += 1
            self.ws.send(json.dumps(self.snapshot()))
            return {"ok": True}
        return super().handle(name, a)


def _open(gui, look, night, viewport=None):
    server, browser = gui
    host = NightHost(look, night)
    pg = browser.new_page(viewport=viewport or {"width": 1440, "height": 900})
    errors: list[str] = []
    pg.on("pageerror", lambda e: errors.append(f"pageerror: {e}"))
    pg.route_web_socket("**/ws*", host.on_socket)
    pg.goto(server.url)
    pg.wait_for_selector(".board-night", timeout=WAIT_MS)
    pg.wait_for_function(f"document.documentElement.dataset.look === '{look}'", timeout=WAIT_MS)
    return pg, host, errors


def _shot(pg, name):
    if TAKE:
        SHOTS.mkdir(parents=True, exist_ok=True)
        pg.screenshot(path=str(SHOTS / f"{name}.png"))


@pytest.mark.parametrize("look", ["camp", "office"])
def test_the_green_card_and_its_confirm(gui, look):
    pg, host, errors = _open(gui, look, GREEN)
    card = pg.locator(".board-night")
    assert card.locator(".board-night__title").inner_text() == "Night report · 2026-10-17"
    assert card.locator(".board-night__lead").inner_text() == "2 changes ready for main"
    assert card.locator(".board-night__steps li").count() == 3
    assert "Cost $0.62 of its $2.00 budget" in card.inner_text()
    # green stands under Needs you, not in it: the count says nothing waits
    assert pg.locator(".board-today > h3").first.locator(".board-count").count() == 0
    card.get_by_role("button", name="Details").click()
    assert "Dark mode switch" in card.locator(".board-night__details").inner_text()
    assert "dark-mode" in card.locator(".board-night__details").inner_text()
    _shot(pg, f"desktop-{look}-green")
    card.get_by_role("button", name="Pass to main").click()
    assert card.locator(".board-night__sure").inner_text().startswith("Pass 2 changes to main?")
    _shot(pg, f"desktop-{look}-confirm")
    assert not [n for n, _ in host.log if n == "gate.pass_night"]          # the confirm first, nothing sent yet
    card.get_by_role("button", name="Pass 2 changes").click()
    pg.wait_for_selector(".board-night", state="detached", timeout=WAIT_MS)  # passed: Today lets it go
    assert ("gate.pass_night", {"date": "2026-10-17"}) in host.log
    assert errors == []
    pg.close()


@pytest.mark.parametrize("look", ["camp", "office"])
def test_the_red_card_stands_in_needs_you(gui, look):
    pg, host, errors = _open(gui, look, RED)
    card = pg.locator(".board-night")
    assert card.evaluate("(el) => el.classList.contains('is-red')")
    # it is the first thing under Needs you, and counted there
    assert pg.locator(".board-today > h3").first.locator(".board-count").inner_text() == "1"
    assert pg.evaluate("""() => { const h = document.querySelector('.board-today > h3');
        return h.nextElementSibling === document.querySelector('.board-night'); }""")
    assert card.locator(".board-night__lead").inner_text() == "Red: Full suite, Daily check"
    assert "test_queue_survives_a_restart" in card.locator(".board-night__notfixed").inner_text()
    assert card.get_by_role("button", name="Pass to main").count() == 0
    _shot(pg, f"desktop-{look}-red")
    card.get_by_role("button", name="Run now").click()
    pg.wait_for_function("document.querySelector('.board-night')?.dataset.state === 'running'", timeout=WAIT_MS)
    assert ("gate.run_night", {}) in host.log and errors == []
    pg.close()


def test_dev_moved_since_the_night_offers_no_pass(gui):
    pg, _host, _errors = _open(gui, "office", {**GREEN, "stale": True})
    card = pg.locator(".board-night")
    assert "dev moved since the night; run again" in card.inner_text()
    assert card.get_by_role("button", name="Pass to main").count() == 0
    assert card.get_by_role("button", name="Run now").count() == 1
    pg.close()


def test_the_review_gate_shows_the_same_card(page, gui):
    """The real host: a night's report in `.orkcraft/gate/night/`, the Review gate's large card shows it as the board does."""
    town = gui[0].host.town
    folder = Path(town.repo_root) / ".orkcraft" / "gate" / "night"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "2026-10-17.json").write_text(json.dumps(GREEN))
    call = lambda name, args: page.evaluate("([n, a]) => import('/static/js/link.js').then(m => m.command(n, a))", [name, args])
    bid = call("town.build", {"type": "loot"})
    page.keyboard.press("Escape")
    _hut(page, bid).wait_for(state="visible", timeout=WAIT_MS)
    page.evaluate("id => import('/static/js/windows.js').then(m => m.openBuilding(id))", bid)
    card = page.locator(f'.gui-hut[data-id="{bid}"] .loot-large .board-night')
    card.wait_for(state="visible", timeout=WAIT_MS)
    assert card.locator(".board-night__title").inner_text() == "Night report · 2026-10-17"
    assert "Cost $0.62 of its $2.00 budget" in card.inner_text()
    if TAKE:
        _hut(page, bid).screenshot(path=str(SHOTS / "review-gate-office.png"))
    (folder / "2026-10-17.json").unlink()
