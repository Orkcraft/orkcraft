"""The board in focus on the desktop (docs/specs/29a-board-focus.md §1, §6, §7), in a real browser against a stub host
that answers the §6 shapes: the window is the board and a thin top bar (Stop all, the spend) — no town. An idea is
dropped, opened, asked about; Take it to work shows the plan; Start sends it to work. In Camp the board wears v4's kit
(docs/design/design-system-v4.md), in Office it does not. Screenshot to docs/design/img/board/ when ORKCRAFT_SHOTS is
set, and the v4 shots (Camp and Office, desktop) to docs/design/img/board-v4/ when BOARD_V4_SHOTS is."""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

pytest.importorskip("playwright.sync_api")

from tests.test_gui_browser import WAIT_MS, gui  # noqa: E402,F401  (fixture)

pytestmark = pytest.mark.browser

SHOTS = Path(__file__).resolve().parent.parent / "docs" / "design" / "img" / "board"
V4_SHOTS = SHOTS.parent / "board-v4"
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

    def __init__(self, look: str = "office"):
        self.look = look
        self.rev = 1
        self.log: list[tuple[str, dict]] = []
        self.tracks = [{"slug": "general", "title": "General", "about": "", "criteria": [], "deadline": "", "order": 0}]
        self.ideas = {"dark-mode": {"slug": "dark-mode", "title": "Dark mode", "track": "general", "order": 0, "state": "ready",
                                    "size": "M", "asks": 0, "updated": "2026-10-17T09:00:00", "plan": None, "talk": []}}
        self.ws = None

    def snapshot(self):
        return {"t": "state", "state": {
            "focus": "board", "ideas_rev": self.rev, "look": self.look, "project": "orkline", "demo": False, "onboarding": False,
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
                "progress": {"done": sum(k["state"] == "merged" for k in i["plan"]["tasks"]) if i["plan"] else 0,
                             "total": len(i["plan"]["tasks"]) if i["plan"] else 0}} for i in self.ideas.values()]
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

    def seed(self):
        """A few ideas in several states: new, asks you, plan ready with its plan, working 2/5."""
        def idea(slug, title, state, order, plan=None, track="general"):
            self.ideas[slug] = {"slug": slug, "title": title, "track": track, "order": order, "state": state, "size": "S" if order % 2 else "M",
                                "asks": 0, "updated": "", "plan": plan, "talk": []}
        self.tracks.append({"slug": "phone", "title": "Phone app", "about": "", "criteria": [], "deadline": "", "order": 1})
        idea("dark-mode", "Dark mode", "plan", 0, json.loads(json.dumps(PLAN)))
        idea("offline", "Offline mode for the field days", "raw", 1)
        idea("export", "Export the week as a report", "asks", 2)
        work = json.loads(json.dumps(PLAN))
        work["passed_at"] = "2026-10-17T10:05:00"
        work["todos"] = []
        work["estimate"] = {"tasks": 5, "usd_low": 1.2, "usd_high": 3.5}
        work["tasks"] = [dict(PLAN["tasks"][0], id=f"k{n}", title=t, state=st, commit="9f2c41d7e0" if st == "merged" else "",
                              after=[f"k{n - 1}"] if n > 1 else [])
                         for n, (t, st) in enumerate([("Read the sync code", "merged"), ("Add the queue", "merged"),
                                                      ("Retry on a lost signal", "running"), ("Test it offline", "waiting"),
                                                      ("Write the notes", "waiting")], 1)]
        idea("sync", "Sync ideas between the phone and the town", "working", 3, work, track="phone")
        self.ideas["dark-mode"]["talk"] = [{"who": "you", "text": "Does it follow the system's setting?", "section": "Risks", "at": ""},
                                           {"who": "keeper", "text": "Yes: it reads prefers-color-scheme and keeps your choice.",
                                            "section": "Risks", "at": ""}]

    def on_socket(self, ws):
        self.ws = ws
        ws.send(json.dumps(self.snapshot()))

        def on_message(raw):
            m = json.loads(raw)
            ws.send(json.dumps({"t": "reply", "id": m["id"], "ok": True, "result": self.handle(m["name"], m["args"])}))
        ws.on_message(on_message)


def _open(gui, look="office", seed=False, viewport=None, scale=1):
    server, browser = gui
    host = StubHost(look)
    if seed:
        host.seed()
    pg = browser.new_page(viewport=viewport or {"width": 1440, "height": 900}, device_scale_factor=scale)
    errors: list[str] = []
    pg.on("pageerror", lambda e: errors.append(f"pageerror: {e}"))
    pg.on("console", lambda m: m.type == "error" and errors.append(f"console: {m.text}"))
    pg.route_web_socket("**/ws*", host.on_socket)                # the stub host stands in for the town's socket
    pg.goto(server.url)
    pg.wait_for_selector(".board-main .board-card", timeout=WAIT_MS)
    return pg, host, errors


@pytest.fixture
def board(gui):
    pg, host, errors = _open(gui)
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


KIT = """() => {
  const cs = (q) => getComputedStyle(document.querySelector(q));
  return { look: document.documentElement.dataset.look,
    panels: [".board-tracks", ".board-mid", ".board-idea"].map((q) => cs(q).borderImageSource),
    plate: cs(".board-idea .board-col__plate").borderImageSource, band: cs(".board-today .board-sub").borderImageSource,
    card: cs(".board-card.is-on").borderImageSource, stop: cs(".board-top .gui-hud__stop").borderImageSource,
    heading: cs(".board-idea .board-col__plate").fontFamily, thesis: cs(".board-idea .board-sec__thesis").fontFamily,
    text: cs(".board-idea .board-sec__text").fontFamily, mark: cs(".board-sec__mark").display, svg: cs(".board-sec__icon").display };
}"""


@pytest.mark.parametrize("look", ["camp", "office"])
def test_in_camp_the_board_wears_the_kit_and_in_office_it_does_not(gui, look):
    pg, host, errors = _open(gui, look, seed=True)
    try:
        pg.locator(".board-card", has_text="Dark mode").click()
        pg.locator(".board-idea .board-sec").first.wait_for(timeout=WAIT_MS)
        got = pg.evaluate(KIT)
        assert got["look"] == look
        if look == "camp":                                   # the frame, the plate, the band, the teal rim, the teal Stop all
            assert all("frame" in p for p in got["panels"]), got["panels"]
            assert "plate" in got["plate"] and "band" in got["band"] and "well-on" in got["card"] and "btn-teal" in got["stop"]
            assert "Jersey 15" in got["heading"] and "Jersey" not in got["thesis"] and "Jersey" not in got["text"]
            assert got["mark"] != "none" and got["svg"] == "none"
        else:                                                # Office: calm, no piece, no sprite
            assert all(p == "none" for p in got["panels"]) and got["plate"] == got["band"] == got["card"] == "none"
            assert "Jersey" not in got["heading"] and got["mark"] == "none" and got["svg"] != "none"
    finally:
        pg.close()
    assert not errors, "\n".join(errors)


@pytest.mark.skipif(not os.environ.get("BOARD_V4_SHOTS"), reason="the v4 shots are taken on demand")
@pytest.mark.parametrize("look", ["camp", "office"])
def test_board_v4_shots(gui, look):
    """docs/design/img/board-v4/desktop-<look>-*.png at 1400 × 860, density 2: the board with an idea of each state, the
    plan ready opened with its plan, and the work at 2/5."""
    V4_SHOTS.mkdir(parents=True, exist_ok=True)
    pg, host, errors = _open(gui, look, seed=True, viewport={"width": 1400, "height": 860}, scale=2)
    try:
        pg.screenshot(path=str(V4_SHOTS / f"desktop-{look}-board.png"))
        pg.locator(".board-card", has_text="Dark mode").click()
        pg.get_by_role("button", name="Start · 2 tasks · ~$0.6–1.8").wait_for(timeout=WAIT_MS)
        pg.locator(".board-sec[data-name=Risks] summary").click()
        pg.mouse.move(0, 0)
        pg.screenshot(path=str(V4_SHOTS / f"desktop-{look}-plan.png"))
        pg.locator(".board-track", has_text="Phone app").click()
        pg.locator(".board-card", has_text="Sync ideas").click()
        pg.get_by_role("button", name="Stop", exact=True).wait_for(timeout=WAIT_MS)
        pg.mouse.move(0, 0)
        pg.screenshot(path=str(V4_SHOTS / f"desktop-{look}-working.png"))
    finally:
        pg.close()
    assert not errors, "\n".join(errors)
