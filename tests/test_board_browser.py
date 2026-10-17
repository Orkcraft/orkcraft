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
SHOTS_29C = SHOTS.parent / "board-29c"
SILENCE = ("The orks ask you when a question, a plan, a red gate twice, a conflict or a spent window needs you. "
           "Otherwise they work and merge.")
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
        self.merged: list[dict] = []                       # part A's merged.jsonl (29c §1): unseen lines, newest first

    def snapshot(self):
        return {"t": "state", "state": {
            "focus": "board", "ideas_rev": self.rev, "look": self.look, "project": "orkline", "demo": False, "onboarding": False,
            "words": [], "resources": {}, "orkspaces": [], "buildings": [], "roads": [], "alerts": [], "score": {},
            "hud": {"gold": "$2.40", "show_gold": True, "lumber": "120k"}}}

    def page(self, slug):
        i = self.ideas[slug]
        # 29c §3: for size S only Gist, In, Out and Stages are shown (the others when they hold text; here they do)
        secs = [{"name": n, "thesis": f"{n} in one line", "text": f"{n}: the longer text of this section.",
                 "shown": i["size"] != "S" or n in ("Gist", "In", "Out", "Stages")} for n in SECTIONS]
        return {"slug": slug, "title": i["title"], "track": i["track"], "state": i["state"], "size": i["size"], "sections": secs,
                "talk": i["talk"][-30:], "plan": i["plan"], "busy": False, "questions": i.get("questions", [])}

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
            needs += [{"idea": i["slug"], "kind": "asks", "title": i["title"], "text": f"{len(i['questions'])} questions"}
                      for i in self.ideas.values() if i.get("questions")]
            unseen = [m for m in self.merged if not m["seen"]]
            return {"tracks": [t | {"count": sum(i["track"] == t["slug"] for i in self.ideas.values())} for t in self.tracks],
                    "ideas": ideas, "today": {"todos": todos, "needs_you": needs, "merged": unseen[:20], "merged_more": max(0, len(unseen) - 20)},
                    "batch_next": "", "rev": self.rev}
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
        elif name == "ideas.seen":
            for m in self.merged:
                m["seen"] = m["seen"] or not a or (m["idea"] == a.get("idea") and m["task"] == a.get("task"))
        elif name == "ideas.revert":
            line = next(m for m in self.merged if m["idea"] == a["idea"] and m["task"] == a["task"])
            if line["subject"].startswith("Conflict"):
                return {"error": "The revert conflicts with a later change: main is untouched."}
            line["reverted"] = line["seen"] = True
        elif name == "ideas.answer":
            qs = self.ideas[a["slug"]]["questions"]
            q = next(q for q in qs if q["id"] == a["id"])
            q["answer"] = a["text"] if "text" in a else q["options"][a["choice"]]
            left = sum(q["answer"] is None for q in qs)
            if not left:
                self.ideas[a["slug"]]["questions"] = []
                self.ideas[a["slug"]]["talk"] += [{"who": "you", "text": "\n".join(f"{q['text']} → {q['answer']}" for q in qs),
                                                   "section": None, "at": ""}]
            self.rev += 1
            if self.ws:
                self.ws.send(json.dumps(self.snapshot()))
            return {"ok": True, "left": left}
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
        self.merge_and_ask()
        self.ideas["dark-mode"]["talk"] = [{"who": "you", "text": "Does it follow the system's setting?", "section": "Risks", "at": ""},
                                           {"who": "keeper", "text": "Yes: it reads prefers-color-scheme and keeps your choice.",
                                            "section": "Risks", "at": ""}]

    def merge_and_ask(self):
        """29c: lines merged without a look, the Taskmaster's questions on an idea that asks, and an S idea."""
        def line(task, goal, subject, tests, cost, est, commit):
            self.merged.append({"idea": "sync", "task": task, "title": goal, "goal": goal, "subject": subject, "commit": commit,
                                "tests": tests, "cost": cost, "estimate": est, "at": "2026-10-17T11:00:00", "seen": False, "reverted": False})
        line("k2", "Add the queue", "Queue ideas while the phone has no signal", "14 passed", 0.42, [0.3, 0.9], "9f2c41d7e0a1")
        line("k1", "Read the sync code", "Read the sync code", "9 passed", 0.18, [0.2, 0.4], "3b7a90c5d2e8")
        self.ideas["export"]["questions"] = [
            {"id": "q1", "text": "Which format should the weekly report take?", "options": ["PDF", "Markdown", "Both"], "recommended": 1,
             "why": "The Wiki is Markdown already, so the report can live beside the pages.", "answer": None},
            {"id": "q2", "text": "Who reads it?", "options": ["Only me", "The team"], "recommended": 0, "why": "You asked for a Monday call.",
             "answer": None}]
        self.ideas["offline"]["size"] = "S"

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


# -- 29c: after the merge, decisions in one tap (docs/specs/29c-after-the-merge.md §1–§3, §5) -------------------------

def _wait_log(pg, host, entry):
    pg.wait_for_function("() => true")
    for _ in range(50):
        if entry in host.log:
            return
        pg.wait_for_timeout(100)
    assert entry in host.log, host.log[-5:]


@pytest.mark.parametrize("look", ["camp", "office"])
def test_merged_without_your_eyes_looked_revert_and_looked_at_all(gui, look):
    pg, host, errors = _open(gui, look, seed=True)
    try:
        group = pg.locator(".board-merged-group")
        group.wait_for(timeout=WAIT_MS)
        assert "Merged without your eyes · 2" in group.locator("h3").text_content()
        first = group.locator(".board-merged").first                 # newest first: the goal bold, the subject, tests · cost, the sha
        text = first.inner_text()
        assert "Add the queue" in text and "Queue ideas while the phone has no signal" in text
        assert "14 passed · $0.42 (est. $0.3–0.9)" in text and "9f2c41d" in text
        assert first.locator(".board-merged__goal").evaluate("e => getComputedStyle(e).fontWeight") in ("700", "bold")
        assert pg.locator(".board-need").count() >= 1 and pg.evaluate(     # under Needs you, above the to-dos
            "() => document.querySelector('.board-merged-group').compareDocumentPosition(document.querySelector('.board-todo, .board-today')) > 0")
        first.get_by_role("button", name="Looked").click()           # Looked clears one line
        _wait_log(pg, host, ("ideas.seen", {"idea": "sync", "task": "k2"}))
        pg.wait_for_function("() => document.querySelectorAll('.board-merged').length === 1")
        assert "Merged without your eyes · 1" in group.locator("h3").text_content()
        line = group.locator(".board-merged")                        # Revert asks once; nothing is sent before the yes
        line.get_by_role("button", name="Revert", exact=True).click()
        assert line.inner_text().count("Revert “Read the sync code” on main?") == 1
        assert not [c for c in host.log if c[0] == "ideas.revert"]
        line.get_by_role("button", name="Keep it").click()
        assert not [c for c in host.log if c[0] == "ideas.revert"]
        line.get_by_role("button", name="Revert", exact=True).click()
        pg.get_by_role("button", name="Revert it").click()
        _wait_log(pg, host, ("ideas.revert", {"idea": "sync", "task": "k1"}))
        pg.wait_for_function("() => !document.querySelector('.board-merged-group')")
        host.merged += [dict(host.merged[0], task=f"x{n}", seen=False, reverted=False) for n in range(2)]
        host.rev += 1
        host.ws.send(json.dumps(host.snapshot()))
        group.get_by_role("button", name="Looked at all").click()
        _wait_log(pg, host, ("ideas.seen", {}))
        pg.wait_for_function("() => !document.querySelector('.board-merged-group')")
    finally:
        pg.close()
    assert not errors, "\n".join(errors)


def test_a_revert_that_fails_leaves_the_line(gui):
    pg, host, errors = _open(gui, "office", seed=True)
    try:
        host.merged[0]["subject"] = "Conflict with the later change"
        host.rev += 1
        host.ws.send(json.dumps(host.snapshot()))
        line = pg.locator(".board-merged", has_text="Conflict with the later change")
        line.wait_for(timeout=WAIT_MS)
        line.get_by_role("button", name="Revert", exact=True).click()
        pg.get_by_role("button", name="Revert it").click()
        pg.get_by_text("main is untouched").first.wait_for(timeout=WAIT_MS)       # the host's plain-words error
        assert pg.locator(".board-merged").count() == 2
    finally:
        pg.close()
    assert not errors, "\n".join(errors)


@pytest.mark.parametrize("look", ["camp", "office"])
def test_questions_are_chips_on_the_needs_you_card_and_on_the_idea(gui, look):
    pg, host, errors = _open(gui, look, seed=True)
    try:
        card = pg.locator(".board-today li", has=pg.locator(".board-need[data-kind=asks]"))
        card.wait_for(timeout=WAIT_MS)
        q1 = card.locator(".board-q[data-id=q1]")
        assert q1.locator(".board-opt").all_inner_texts()[:3] == ["PDF", "Markdown\nrecommended", "Both"] or \
            [t.replace("\n", " ") for t in q1.locator(".board-opt").all_inner_texts()] == ["PDF", "Markdown recommended", "Both", "Other…"]
        assert q1.locator(".board-opt.is-rec").count() == 1 and "Markdown" in q1.locator(".board-opt.is-rec").inner_text()
        why = q1.locator(".board-why")                               # its why on hover
        assert not why.is_visible()
        q1.locator(".board-opt.is-rec").hover()
        assert why.is_visible() and "The Wiki is Markdown already" in why.inner_text()
        pg.mouse.move(0, 0)
        assert pg.evaluate("() => [...document.querySelectorAll('.board-opt')].every((b) => b.getBoundingClientRect().height >= 24)")
        q1.get_by_role("button", name="Markdown").click()            # one tap answers
        _wait_log(pg, host, ("ideas.answer", {"slug": "export", "id": "q1", "choice": 1}))
        q2 = card.locator(".board-q[data-id=q2]")
        q2.get_by_role("button", name="Other…").click()              # Other…: one line of its own
        q2.get_by_label("Your answer to: Who reads it?").fill("Me and Dana")
        q2.get_by_role("button", name="Answer", exact=True).click()
        _wait_log(pg, host, ("ideas.answer", {"slug": "export", "id": "q2", "text": "Me and Dana"}))
        pg.wait_for_function("() => !document.querySelector('.board-need[data-kind=asks]')")     # all answered: the questions are cleared
        assert host.ideas["export"]["questions"] == [] and "Markdown" in host.ideas["export"]["talk"][-1]["text"]
        host.ideas["export"]["questions"] = [{"id": "q3", "text": "Which week?", "options": ["This", "Last"], "recommended": 1, "why": "Mondays.",
                                              "answer": None}]
        host.rev += 1
        host.ws.send(json.dumps(host.snapshot()))
        pg.locator(".board-card", has_text="Export the week").click()          # and on the idea itself
        on_idea = pg.locator(".board-idea .board-q[data-id=q3]")
        on_idea.wait_for(timeout=WAIT_MS)
        on_idea.get_by_role("button", name="Last").click()
        _wait_log(pg, host, ("ideas.answer", {"slug": "export", "id": "q3", "choice": 1}))
    finally:
        pg.close()
    assert not errors, "\n".join(errors)


@pytest.mark.parametrize("look", ["camp", "office"])
def test_hidden_sections_wait_behind_more_sections(gui, look):
    pg, host, errors = _open(gui, look, seed=True)
    try:
        pg.locator(".board-card", has_text="Offline mode").click()         # size S: Gist, In, Out and Stages
        pg.locator(".board-idea .board-sec").first.wait_for(timeout=WAIT_MS)
        assert pg.locator(".board-idea .board-sec").evaluate_all("els => els.map((e) => e.dataset.name)") == ["Gist", "In", "Out", "Stages"]
        more = pg.get_by_role("button", name="More sections")
        assert more.is_visible() and pg.evaluate("() => document.querySelector('.board-more').previousElementSibling.classList.contains('board-sec')")
        more.click()
        assert pg.locator(".board-idea .board-sec").count() == len(SECTIONS)
        pg.get_by_role("button", name="Fewer sections").click()
        assert pg.locator(".board-idea .board-sec").count() == 4
        pg.locator(".board-card", has_text="Export the week").click()      # size M: all, no link
        pg.locator(".board-idea .board-sec").nth(8).wait_for(timeout=WAIT_MS)
        assert pg.get_by_role("button", name="More sections").count() == 0
    finally:
        pg.close()
    assert not errors, "\n".join(errors)


def test_the_silence_line_stands_at_the_foot_of_today(board):
    pg, _ = board
    line = pg.locator(".board-silence")
    assert line.inner_text().replace("\n", " ") == SILENCE
    assert pg.evaluate("() => { const l = document.querySelector('.board-silence'), t = document.querySelector('.board-today');"
                       " return t.lastElementChild === l; }")


@pytest.mark.skipif(not os.environ.get("BOARD_29C_SHOTS"), reason="the 29c shots are taken on demand")
@pytest.mark.parametrize("look", ["camp", "office"])
def test_board_29c_shots(gui, look):
    """docs/design/img/board-29c/desktop-<look>-*.png at 1400 × 860, density 2: Today with merged lines and a question's
    chips (the why on hover), and an S idea with More sections."""
    SHOTS_29C.mkdir(parents=True, exist_ok=True)
    pg, host, errors = _open(gui, look, seed=True, viewport={"width": 1400, "height": 860}, scale=2)
    try:
        pg.locator(".board-merged-group").wait_for(timeout=WAIT_MS)
        pg.locator(".board-q[data-id=q1] .board-opt.is-rec").hover()
        pg.screenshot(path=str(SHOTS_29C / f"desktop-{look}-today.png"))
        pg.mouse.move(0, 0)
        pg.locator(".board-card", has_text="Offline mode").click()
        pg.get_by_role("button", name="More sections").wait_for(timeout=WAIT_MS)
        pg.mouse.move(0, 0)
        pg.screenshot(path=str(SHOTS_29C / f"desktop-{look}-s-idea.png"))
        pg.locator(".board-card", has_text="Export the week").click()
        pg.locator(".board-idea .board-q").first.wait_for(timeout=WAIT_MS)
        pg.mouse.move(0, 0)
        pg.screenshot(path=str(SHOTS_29C / f"desktop-{look}-questions.png"))
    finally:
        pg.close()
    assert not errors, "\n".join(errors)
