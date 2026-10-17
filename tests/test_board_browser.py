"""The board in focus on the desktop (docs/specs/29a-board-focus.md §1, §6, §7), in a real browser against a stub host
that answers the §6 shapes: the window is the board and a thin top bar (Stop all, the spend) — no town. An idea is
dropped, opened, asked about; Take it to work shows the plan; Start sends it to work. Screenshot to
docs/design/img/board/ when ORKCRAFT_SHOTS is set."""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

pytest.importorskip("playwright.sync_api")

from tests.test_gui_browser import WAIT_MS, gui  # noqa: E402,F401  (fixture)

pytestmark = pytest.mark.browser

SHOTS = Path(__file__).resolve().parent.parent / "docs" / "design" / "img" / "board"
SECTIONS = ["Gist", "Why", "In", "Out", "Risks", "Open questions", "Estimate", "Stages", "Decisions"]
PLAN = {"idea": "dark-mode", "made_at": "2026-10-17T10:00:00", "passed_at": None,
        "estimate": {"tasks": 2, "usd_low": 0.6, "usd_high": 1.8},
        "todos": [{"id": "t1", "title": "API_KEY", "kind": "secret", "why": "The theme service needs it", "choices": [],
                   "steps": [], "for": ["k1"], "done": False, "value": None}],
        "tasks": [{"id": "k1", "title": "Add the theme switch", "brief": "…", "tier": "warrior", "after": [], "state": "waiting",
                   "branch": "", "commit": "", "session": "", "cost": None, "tokens": None, "started": "", "finished": "",
                   "error": "", "note": ""},
                  {"id": "k2", "title": "Test it", "brief": "…", "tier": "laborer", "after": ["k1"], "state": "waiting",
                   "branch": "", "commit": "", "session": "", "cost": None, "tokens": None, "started": "", "finished": "",
                   "error": "", "note": ""}]}


class StubHost:
    """What part A's commands answer, in the shapes of §6; every change bumps `ideas_rev` and pushes a snapshot."""

    def __init__(self):
        self.rev = 1
        self.log: list[tuple[str, dict]] = []
        self.tracks = [{"slug": "general", "title": "General", "about": "", "criteria": [], "deadline": "", "order": 0}]
        self.ideas = {"dark-mode": {"slug": "dark-mode", "title": "Dark mode", "track": "general", "order": 0, "state": "ready",
                                    "size": "M", "asks": 0, "updated": "2026-10-17T09:00:00", "plan": None, "talk": []}}
        self.ws = None

    def snapshot(self):
        return {"t": "state", "state": {
            "focus": "board", "ideas_rev": self.rev, "look": "office", "project": "orkline", "demo": False, "onboarding": False,
            "words": [], "resources": {}, "orkspaces": [], "buildings": [], "roads": [], "alerts": [], "score": {},
            "hud": {"gold": "$2.40", "show_gold": True, "lumber": "120k"}}}

    def page(self, slug):
        i = self.ideas[slug]
        secs = [{"name": n, "thesis": f"{n} in one line", "text": f"{n}: the longer text of this section."} for n in SECTIONS]
        return {"slug": slug, "title": i["title"], "track": i["track"], "state": i["state"], "size": i["size"], "sections": secs,
                "talk": i["talk"][-30:], "plan": i["plan"], "busy": False}

    def handle(self, name, a):
        self.log.append((name, a))
        if name == "ideas.board":
            ideas = [{k: v for k, v in i.items() if k not in ("plan", "talk")} | {
                "thesis": "Gist in one line", "asks": 0,
                "progress": {"done": 0, "total": len(i["plan"]["tasks"]) if i["plan"] else 0}} for i in self.ideas.values()]
            todos = [{"idea": i["slug"], "id": t["id"], "title": t["title"], "kind": t["kind"], "why": t["why"],
                      "choices": t["choices"], "steps": t["steps"], "done": t["done"]}
                     for i in self.ideas.values() if i["plan"] and i["plan"]["passed_at"] for t in i["plan"]["todos"]]
            needs = [{"idea": i["slug"], "kind": "plan", "title": i["title"], "text": "Plan ready"}
                     for i in self.ideas.values() if i["state"] == "plan"]
            return {"tracks": [t | {"count": sum(i["track"] == t["slug"] for i in self.ideas.values())} for t in self.tracks],
                    "ideas": ideas, "today": {"todos": todos, "needs_you": needs}, "batch_next": "", "rev": self.rev}
        if name == "ideas.page":
            return self.page(a["slug"])
        if name == "ideas.add":
            slug = a["text"].lower().replace(" ", "-")[:20]
            self.ideas[slug] = {"slug": slug, "title": a["text"], "track": a.get("track") or "general", "order": len(self.ideas),
                                "state": "raw", "size": "", "asks": 0, "updated": "", "plan": None, "talk": []}
            return {"slug": slug}
        if name == "ideas.say":
            self.ideas[a["slug"]]["talk"] += [{"who": "you", "text": a["text"], "section": a.get("section"), "at": ""},
                                              {"who": "keeper", "text": "Understood.", "section": a.get("section"), "at": ""}]
        elif name == "ideas.plan":
            self.ideas[a["slug"]]["state"], self.ideas[a["slug"]]["plan"] = "plan", json.loads(json.dumps(PLAN))
        elif name == "ideas.start":
            i = self.ideas[a["slug"]]
            i["state"], i["plan"]["passed_at"] = "working", "2026-10-17T10:05:00"
            i["plan"]["tasks"][0]["state"] = "running"
        elif name == "ideas.stop":
            self.ideas[a["slug"]]["state"] = "failed"
        elif name == "ideas.drop":
            self.ideas.pop(a["slug"], None)
        elif name == "halt":
            return {}
        else:
            return {"ok": True}
        self.rev += 1
        if self.ws:
            self.ws.send(json.dumps(self.snapshot()))
        return {"ok": True}

    def on_socket(self, ws):
        self.ws = ws
        ws.send(json.dumps(self.snapshot()))

        def on_message(raw):
            m = json.loads(raw)
            ws.send(json.dumps({"t": "reply", "id": m["id"], "ok": True, "result": self.handle(m["name"], m["args"])}))
        ws.on_message(on_message)


@pytest.fixture
def board(gui):
    server, browser = gui
    host = StubHost()
    pg = browser.new_page(viewport={"width": 1440, "height": 900})
    errors: list[str] = []
    pg.on("pageerror", lambda e: errors.append(f"pageerror: {e}"))
    pg.on("console", lambda m: m.type == "error" and errors.append(f"console: {m.text}"))
    pg.route_web_socket("**/ws*", host.on_socket)                # the stub host stands in for the town's socket
    pg.goto(server.url)
    pg.wait_for_selector(".board-main .board-card", timeout=WAIT_MS)
    yield pg, host
    pg.close()
    assert not errors, "\n".join(errors)


def test_focus_shows_only_the_board_with_stop_all_and_the_spend(board):
    pg, host = board
    assert pg.locator(".board").is_visible()
    for gone in (".gui-hud", ".gui-camp", ".gui-town", ".gui-foot", ".gui-warchief__face"):
        assert pg.locator(gone).count() == 0, gone
    top = pg.locator(".board-top")
    assert top.get_by_role("button", name="Stop all").is_visible() and "$2.40" in top.inner_text()
    top.get_by_role("button", name="Stop all").click()
    pg.wait_for_function("() => true")
    assert ("halt", {}) in host.log


def test_an_idea_dropped_opened_asked_taken_to_work_and_started(board):
    pg, host = board
    pg.get_by_role("button", name="+ Idea").click()
    pg.get_by_label("Your idea").fill("Offline mode")
    pg.get_by_role("button", name="Drop it").click()
    pg.locator(".board-card", has_text="Offline mode").wait_for(timeout=WAIT_MS)
    assert host.log and ("ideas.add", {"text": "Offline mode"}) in host.log
    assert host.ideas["offline-mode"]["state"] == "raw"

    pg.locator(".board-card", has_text="Dark mode").click()           # opened: its nine sections as blocks
    pg.locator(".board-idea .board-sec").first.wait_for(timeout=WAIT_MS)
    assert pg.locator(".board-idea .board-sec").count() == len(SECTIONS)
    assert len({pg.locator(".board-sec").nth(n).get_attribute("data-sec") for n in range(len(SECTIONS))}) > 3

    pg.locator(".board-sec[data-name=Risks] summary").click()         # a block opens from its thesis
    pg.get_by_role("button", name="Ask about Risks").click()          # the question box, on a section
    box = pg.get_by_label("Ask or answer the Taskmaster")
    assert box.get_attribute("placeholder") == "About Risks…"
    box.fill("What if it flickers?")
    pg.get_by_role("button", name="Ask", exact=True).click()
    pg.locator(".board-talk", has_text="Understood.").wait_for(timeout=WAIT_MS)
    assert ("ideas.say", {"slug": "dark-mode", "text": "What if it flickers?", "section": "Risks"}) in host.log

    pg.get_by_role("button", name="Take it to work").click()          # the plan is shown
    start = pg.get_by_role("button", name="Start · 2 tasks · ~$0.6–1.8")
    start.wait_for(timeout=WAIT_MS)
    assert "Add the theme switch" in pg.locator(".board-plan").inner_text() and "after k1" in pg.locator(".board-plan").inner_text()
    if os.environ.get("ORKCRAFT_SHOTS"):
        SHOTS.mkdir(parents=True, exist_ok=True)
        pg.screenshot(path=str(SHOTS / "board-desktop.png"))
    start.click()
    pg.locator(".board-task__state[data-state=running]").wait_for(timeout=WAIT_MS)
    assert ("ideas.start", {"slug": "dark-mode"}) in host.log
    pg.get_by_role("button", name="Stop", exact=True).wait_for(timeout=WAIT_MS)
    assert pg.get_by_role("button", name="Stop all").is_visible()
    pg.locator(".board-todo", has_text="API_KEY").get_by_label("Value of API_KEY").fill("s3cret")   # a secret todo, password field
    assert pg.get_by_label("Value of API_KEY").get_attribute("type") == "password"
    pg.get_by_role("button", name="Keep it").first.click()
    pg.wait_for_function("() => true")
    assert ("ideas.todo", {"idea": "dark-mode", "id": "t1", "done": True, "value": "s3cret"}) in host.log
