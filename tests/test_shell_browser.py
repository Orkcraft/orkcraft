"""The v1 shell on the desktop (docs/specs/33-v1-shell.md §6–§7), in a real browser at 1 440 × 900 against a stub host that
answers the §5 commands: Board on the left, Review on the right, the preview in the centre and Agents under it as VS Code's
terminal. A click on an idea, a to-do, a chip and a result opens the right preview; Merge is off on red with its reason; Send
back needs its line; no camp. Screenshots to docs/design/img/v1/ when ORKCRAFT_SHOTS is set."""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

pytest.importorskip("playwright.sync_api")

from tests.test_gui_browser import WAIT_MS, gui  # noqa: E402,F401  (fixture)

pytestmark = pytest.mark.browser

SHOTS = Path(__file__).resolve().parent.parent / "docs" / "design" / "img" / "v1"
SECTIONS = ["Gist", "Why", "In", "Out", "Risks", "Open questions", "Estimate", "Stages", "Decisions"]
GREEN = {"passed": 20, "failed": 0, "failing": [], "tail": "20 passed in 1.1s", "green": True}
RED = {"passed": 10, "failed": 10, "failing": ["tests/test_sync.py::test_retry", "tests/test_sync.py::test_queue", "t3"],
       "tail": "10 failed, 10 passed in 2.0s", "green": False}
PATCH = "diff --git a/sync.py b/sync.py\n--- a/sync.py\n+++ b/sync.py\n@@ -1,2 +1,3 @@\n keep = 1\n-old = 2\n+new = 3\n+more = 4\n"


def task(tid, title, state, after=(), **more):
    return {"id": tid, "title": title, "brief": f"Brief of {title}", "tier": "warrior", "after": list(after), "state": state,
            "branch": f"idea/sync/{tid}", "commit": "", "session": "s", "cost": 0.42, "tokens": 10, "started": "", "finished": "2026-10-17T10:00:00",
            "error": "", "note": "", "round": 1, "tests": None, "diff": None, "conflict": "", "why": "", **more}


def make_plan():
    return {"idea": "sync", "made_at": "2026-10-17T10:00:00", "passed_at": "2026-10-17T10:05:00",
            "estimate": {"tasks": 5, "usd_low": 1.2, "usd_high": 3.5},
            "todos": [{"id": "t1", "title": "API_KEY", "kind": "secret", "why": "The sync service needs it", "choices": [], "steps": [],
                       "for": ["k2", "k3"], "done": False, "value": None}],
            "tasks": [task("k1", "Read the sync code", "merged"), task("k2", "Add the queue", "review", ["k1"], tests=GREEN,
                      diff={"files": 14, "added": 320, "removed": 41}),
                      task("k3", "Retry on a lost signal", "running", ["k2"]),
                      task("k4", "Test it offline", "review", ["k3"], tests=RED, round=2, diff={"files": 3, "added": 12, "removed": 0},
                           conflict="conflicts with dev in a.py, b.py"),
                      task("k5", "Write the notes", "waiting", ["k4"])]}


class StubHost:
    """What part A's commands answer, in the shapes of §5; every change bumps `ideas_rev` and pushes a snapshot."""

    def __init__(self, look="camp", onboarding=None):
        self.look, self.onboarding, self.rev, self.log, self.ws = look, onboarding, 1, [], None
        self.plan = make_plan()
        self.into, self.push = "dev", False
        self.limits = [{"provider": "claude", "name": "Claude", "left": 0.62,
                        "rows": [{"window": "5h", "left": 0.62, "reset": "2026-10-17T18:00"}, {"window": "week", "left": 0.8, "reset": "2026-10-20T09:00"}]},
                       {"provider": "agy", "name": "Antigravity", "left": 0.15, "rows": [{"window": "daily", "left": 0.15, "reset": ""}]}]
        self.ideas = {"sync": self.idea("sync", "Sync ideas between the phone and the town", "working", 0),
                      "dark": self.idea("dark", "Dark mode", "plan", 1),
                      "offline": self.idea("offline", "Offline mode", "raw", 2)}

    def idea(self, slug, title, state, order):
        return {"slug": slug, "title": title, "track": "general", "order": order, "state": state, "size": "M", "asks": 0, "updated": "x", "talk": []}

    def results(self):
        return [{"idea": "sync", "idea_title": "Sync ideas between the phone and the town", "task": t["id"], "title": t["title"], "round": t["round"],
                 "tests": t["tests"], "diff": t["diff"], "cost": t["cost"], "conflict": t["conflict"], "finished": t["finished"]}
                for t in self.plan["tasks"] if t["state"] == "review"]

    def snapshot(self):
        return {"t": "state", "state": {
            "focus": "board", "ideas_rev": self.rev, "look": self.look, "project": "orkline", "demo": False, "onboarding": self.onboarding or False,
            "words": [], "resources": {}, "orkspaces": [], "buildings": [], "roads": [], "alerts": [], "score": {},
            "limits": self.limits, "review_count": len(self.results()), "needs_you": 1,
            "hud": {"gold": "$2.40", "show_gold": True, "lumber": "120k"}}}

    def page(self, slug):
        i = self.ideas[slug]
        secs = [{"name": n, "thesis": f"{n} in one line", "text": f"{n}: the longer text of this section."} for n in SECTIONS]
        return {"slug": slug, "title": i["title"], "track": "general", "state": i["state"], "size": "M", "sections": secs, "talk": i["talk"],
                "plan": self.plan if slug == "sync" else None, "busy": False}

    def find(self, a):
        return next(t for t in self.plan["tasks"] if t["id"] == a["task"])

    def handle(self, name, a):
        self.log.append((name, a))
        if name == "ideas.board":
            ideas = [i | {"thesis": "Gist in one line", "progress": {"done": 1, "total": 5} if i["slug"] == "sync" else {"done": 0, "total": 0}}
                     for i in self.ideas.values()]
            todos = [{"idea": "sync", "id": "t1", "title": "API_KEY", "kind": "secret", "why": "The sync service needs it", "choices": [], "steps": [], "done": False}]
            return {"tracks": [{"slug": "general", "title": "General", "about": "", "criteria": [], "deadline": "", "order": 0, "count": len(ideas)}],
                    "ideas": ideas, "today": {"todos": todos, "needs_you": [{"idea": "dark", "kind": "plan", "title": "Dark mode", "text": "Plan ready"}]},
                    "batch_next": "", "rev": self.rev}
        if name == "ideas.page":
            return self.page(a["slug"])
        if name == "ideas.review_list":
            return {"into": self.into, "push": self.push, "branches": ["dev", "main"], "results": self.results()}
        if name == "ideas.agents":
            chips = [dict(idea="sync", idea_title="Sync ideas between the phone and the town", task=t["id"], title=t["title"],
                          state=t["state"], tier=t["tier"], note="") for t in self.plan["tasks"] if t["state"] in ("running", "review")]
            return {"roles": [{"role": "taskmaster", "name": "Taskmaster", "state": "waiting",
                               "waits_on": {"idea": "dark", "text": "waiting for your answers on “Dark mode”"}, "chips": []},
                              {"role": "grunt", "name": "Grunts", "chips": chips}],
                    "done_today": [{"idea": "sync", "task": "k1", "title": "Read the sync code"}]}
        if name == "ideas.task":
            return self.find(a) | {"idea": a["slug"], "idea_title": "Sync ideas between the phone and the town", "log": "== round 1\nreading sync.py\n"}
        if name == "ideas.diff":
            return {"base": self.into, "branch": f"idea/sync/{a['task']}", "commits": [{"sha": "9f2c41d7e0", "subject": "k2: add the queue"}],
                    "files": [{"path": "sync.py", "added": 2, "removed": 1, "patch": PATCH}, {"path": "huge.json", "added": 9000, "removed": 0, "patch": None}],
                    "truncated": True}
        if name == "ideas.merge":
            self.find(a)["state"] = "merged"
            return self.bump({"ok": True, "commit": "abc"})
        if name == "ideas.back":
            self.find(a).update(state="running", round=self.find(a)["round"] + 1, why=a["why"])
            return self.bump({"ok": True})
        if name == "ideas.drop_task":
            self.find(a).update(state="failed", error="dropped by you")
            return self.bump({"ok": True})
        if name == "ideas.stop_task":
            self.find(a).update(state="ready", note="stopped by you")
            return self.bump({"ok": True})
        if name == "ideas.into":
            self.into, self.push = a.get("branch", self.into), a.get("push", self.push)
            return self.bump({"ok": True})
        if name == "ideas.add":
            self.ideas[a["text"].lower().replace(" ", "-")] = self.idea(a["text"].lower().replace(" ", "-"), a["text"], "raw", 9)
            return self.bump({"slug": a["text"].lower().replace(" ", "-")})
        if name == "onboarding.skip":
            self.onboarding = {"step": "raising", "steps": ["tools"], "n": 0, "raising": {"title": "x", "phase": "done", "steps": [], "buildings": [], "error": ""}}
            return self.bump({})
        if name == "onboarding.close":
            self.onboarding = None
            return self.bump({})
        return {"ok": True}

    def bump(self, result):
        self.rev += 1
        if self.ws:
            self.ws.send(json.dumps(self.snapshot()))
        return result

    def on_socket(self, ws):
        self.ws = ws
        ws.send(json.dumps(self.snapshot()))

        def on_message(raw):
            m = json.loads(raw)
            ws.send(json.dumps({"t": "reply", "id": m["id"], "ok": True, "result": self.handle(m["name"], m["args"])}))
        ws.on_message(on_message)


def _open(gui, viewport=None, host=None, ready=".shell-card"):
    server, browser = gui
    host = host or StubHost()
    pg = browser.new_page(viewport=viewport or {"width": 1440, "height": 900})
    errors: list[str] = []
    pg.on("pageerror", lambda e: errors.append(f"pageerror: {e}"))
    pg.on("console", lambda m: m.type == "error" and errors.append(f"console: {m.text}"))
    pg.route_web_socket("**/ws*", host.on_socket)
    pg.goto(server.url)
    if ready:
        pg.wait_for_selector(ready, timeout=WAIT_MS)
    return pg, host, errors


@pytest.fixture
def shell(gui):
    pg, host, errors = _open(gui)
    yield pg, host
    pg.close()
    assert not errors, "\n".join(errors)


def box(pg, selector):
    return pg.locator(selector).first.bounding_box()


def test_three_columns_agents_under_the_preview_and_no_camp(shell):
    pg, host = shell
    board, preview, review, agents = box(pg, ".shell-board"), box(pg, ".shell-preview"), box(pg, ".shell-review"), box(pg, ".shell-agents")
    assert board["x"] < preview["x"] < review["x"] and 280 <= board["width"] <= 320 and 320 <= review["width"] <= 360
    assert board["height"] > 500 and review["height"] > 500                                   # both full height
    assert agents["y"] > preview["y"] + preview["height"] - 2 and abs(agents["x"] - preview["x"]) < 2   # Agents under the preview
    assert 0.25 < agents["height"] / (agents["y"] + agents["height"] - preview["y"]) < 0.42   # about a third of the centre
    assert pg.evaluate("document.documentElement.dataset.look") == "office"                   # the person's look is camp: not here
    for gone in (".gui-hud", ".gui-camp", ".gui-town", ".gui-foot", ".gui-warchief__face", "[data-look=camp]"):
        assert pg.locator(gone).count() == 0, gone
    assert pg.locator(".shell-preview").inner_text().startswith("") and "Open an idea, a task or a result" in pg.locator(".shell-preview").inner_text()
    assert "Dark mode" in pg.locator(".shell-preview").inner_text()                            # the first Needs you item
    assert not pg.evaluate("document.documentElement.scrollWidth > document.documentElement.clientWidth")
    if os.environ.get("ORKCRAFT_SHOTS"):
        SHOTS.mkdir(parents=True, exist_ok=True)
        pg.locator(".shell-card").nth(0).click()
        pg.locator(".shell-file").first.wait_for(timeout=WAIT_MS)
        pg.locator(".shell-file").first.locator("summary").click()
        pg.screenshot(path=str(SHOTS / "desktop-1440x900.png"))


def test_the_top_bar_limits_spend_stop_all_and_the_push_switch(shell):
    pg, host = shell
    top = pg.locator(".shell-top")
    assert "62 %" in top.locator(".shell-limit").nth(0).inner_text() and top.locator(".shell-limit").nth(0).get_attribute("data-provider") == "claude"
    assert "is-warn" in top.locator(".shell-limit").nth(1).get_attribute("class") and "15 %" in top.locator(".shell-limit").nth(1).inner_text()
    pop = top.locator(".shell-limit").nth(0).locator(".shell-pop")
    assert not pop.is_visible()
    top.locator(".shell-limit").nth(0).hover()
    assert pop.is_visible() and "week" in pop.inner_text() and "resets at 18:00" in pop.inner_text()
    assert "$2.40" in top.inner_text()
    top.get_by_role("button", name="Stop all").click()
    pg.wait_for_function("() => true")
    assert ("halt", {}) in host.log
    top.get_by_role("button", name="Settings").click()
    label = pg.get_by_text("Push after merging (sends your code to origin)")
    assert label.is_visible() and not pg.get_by_role("checkbox", name="Push after merging").is_checked()
    pg.get_by_text("Push after merging (sends your code to origin)").click()
    pg.wait_for_function("() => true")
    assert ("ideas.into", {"push": True}) in host.log


def test_agents_resize_hide_and_remember(shell, gui):
    pg, host = shell
    h0 = box(pg, ".shell-agents")["height"]
    handle = box(pg, ".shell-split")
    pg.mouse.move(handle["x"] + 40, handle["y"] + 2)
    pg.mouse.down()
    pg.mouse.move(handle["x"] + 40, handle["y"] - 150, steps=5)
    pg.mouse.up()
    assert box(pg, ".shell-agents")["height"] > h0 + 120
    pg.keyboard.press("Control+j")                                       # hides it, as VS Code's panel
    assert pg.locator(".shell-agents__body").count() == 0 and box(pg, ".shell-agents")["height"] < 60
    assert pg.locator(".shell-split").count() == 0
    pg.reload()
    pg.wait_for_selector(".shell-card", timeout=WAIT_MS)
    assert pg.locator(".shell-agents__body").count() == 0               # kept in localStorage
    pg.get_by_role("button", name="Show Agents (Ctrl+J)").click()
    assert pg.locator(".shell-agents__body").is_visible() and box(pg, ".shell-agents")["height"] > h0 + 120   # and its height


def test_a_click_on_an_idea_a_todo_a_chip_and_a_result_opens_the_right_preview(shell):
    pg, host = shell
    pg.locator(".board-card", has_text="Sync ideas").click()                      # an idea → its spec: the nine sections
    pg.locator(".shell-preview .board-sec").first.wait_for(timeout=WAIT_MS)
    assert pg.locator(".shell-preview .board-sec").count() == len(SECTIONS)
    assert "Spec" in pg.locator(".shell-preview > header").inner_text()

    pg.locator(".board-todo__title", has_text="API_KEY").click()                  # a to-do → the plan, scrolled to it, said what it unblocks
    target = pg.locator(".shell-preview .board-plan__todo.is-target")
    target.wait_for(timeout=WAIT_MS)
    assert "tasks k2 and k3 wait for it" in target.inner_text()
    assert pg.locator(".shell-preview > header").inner_text().startswith("Plan")

    pg.locator(".shell-chip", has_text="Retry on a lost signal").click()          # a chip → the task: brief, log, Stop
    pg.locator(".shell-task").wait_for(timeout=WAIT_MS)
    text = pg.locator(".shell-task").inner_text()
    assert "Brief of Retry on a lost signal" in text and "reading sync.py" in text and "idea/sync/k3" in text and "working" in text
    pg.get_by_role("button", name="Stop", exact=True).click()
    pg.wait_for_function("() => true")
    assert ("ideas.stop_task", {"slug": "sync", "task": "k3"}) in host.log

    pg.locator(".shell-card", has_text="Add the queue").click()                   # a result → its code
    pg.locator(".shell-result .shell-commits").wait_for(timeout=WAIT_MS)
    assert "k2: add the queue" in pg.locator(".shell-commits").inner_text()
    pg.locator(".shell-file", has_text="sync.py").locator("summary").click()
    pg.locator(".shell-patch__line.is-add").first.wait_for(timeout=WAIT_MS)
    assert pg.locator(".shell-patch__line.is-add").count() == 2 and pg.locator(".shell-patch__line.is-del").count() == 1
    pg.locator(".shell-file", has_text="huge.json").locator("summary").click()
    pg.get_by_text("Too large to show.").wait_for(timeout=WAIT_MS)
    colors = pg.evaluate("""() => { const cs = (q) => getComputedStyle(document.querySelector(q)).color;
      return [cs('.shell-patch__line.is-add'), cs('.shell-patch__line.is-del'), getComputedStyle(document.documentElement).getPropertyValue('--success').trim()]; }""")
    assert colors[0] != colors[1]
    assert pg.get_by_role("button", name="Merge into dev").last.is_visible()      # its actions stay pinned at the foot
    foot, body = box(pg, ".shell-result__foot"), box(pg, ".shell-result__body")
    assert foot["y"] >= body["y"] + body["height"] - 2


def test_merge_is_off_on_red_with_its_reason_and_send_back_needs_a_line(shell):
    pg, host = shell
    green, red = pg.locator(".shell-card", has_text="Add the queue"), pg.locator(".shell-card", has_text="Test it offline")
    assert "20 / 20 passed" in green.inner_text() and "14 files, +320 −41" in green.inner_text() and "$0.42" in green.inner_text()
    assert "10 / 20 failed" in red.inner_text() and "test_retry" in red.inner_text() and "round 2" in red.inner_text()
    assert "conflicts with dev in a.py, b.py" in red.inner_text()
    merge = red.get_by_role("button", name="Merge into dev")
    assert merge.is_disabled() and "red" in red.locator(".shell-actions__why").inner_text()
    assert green.get_by_role("button", name="Merge into dev").is_enabled()
    # the quiet Drop is apart from Merge
    drop, mergeb = red.get_by_role("button", name="Drop…").bounding_box(), merge.bounding_box()
    assert drop["x"] > mergeb["x"] + mergeb["width"] + 10

    fix = red.get_by_role("button", name="Fix", exact=True)                       # red / conflict: Fix, the line prefilled
    fix.click()
    line = red.get_by_label("What to fix, in one line")
    assert line.input_value().startswith("Resolve the conflict with dev")
    line.fill("")
    assert red.locator(".shell-actions__line .ok-btn.primary").is_disabled()      # the line is required
    line.fill("Rebase and keep both queues")
    red.locator(".shell-actions__line .ok-btn.primary").click()
    pg.wait_for_function("() => true")
    assert ("ideas.back", {"slug": "sync", "task": "k4", "why": "Rebase and keep both queues"}) in host.log

    green.get_by_role("button", name="Send back").click()
    assert green.locator(".shell-actions__line .ok-btn.primary").is_disabled()
    green.get_by_role("button", name="Merge into dev").click()
    pg.wait_for_function("() => true")
    assert ("ideas.merge", {"slug": "sync", "task": "k2"}) in host.log
    pg.locator(".shell-card").first.wait_for(state="detached", timeout=WAIT_MS) if pg.locator(".shell-card").count() else None
    assert pg.locator(".shell-card", has_text="Add the queue").count() == 0


def test_drop_asks_first_and_merge_into_changes_the_branch(shell):
    pg, host = shell
    card = pg.locator(".shell-card", has_text="Add the queue")
    card.get_by_role("button", name="Drop…").click()
    assert card.get_by_text("Drop this result?").is_visible()
    card.get_by_role("button", name="Keep it").click()
    assert ("ideas.drop_task", {"slug": "sync", "task": "k2"}) not in host.log
    pg.get_by_role("button", name="Merge into dev ▾").click()
    assert pg.get_by_role("menuitemradio").count() == 2
    pg.get_by_role("menuitem", name="New branch…").click()
    pg.get_by_label("Name of the new branch").fill("next")
    pg.get_by_role("button", name="Make it").click()
    pg.wait_for_function("() => true")
    assert ("ideas.into", {"branch": "next"}) in host.log
    pg.get_by_role("button", name="Merge into next ▾").wait_for(timeout=WAIT_MS)


def test_esc_closes_the_preview_and_arrows_move_through_the_review_cards(shell):
    pg, host = shell
    pg.locator(".board-card", has_text="Dark mode").click()
    pg.locator(".shell-preview .board-sec").first.wait_for(timeout=WAIT_MS)
    pg.keyboard.press("Escape")
    pg.locator(".shell-empty").wait_for(timeout=WAIT_MS)
    first = pg.locator(".shell-card").nth(0)
    first.focus()
    pg.keyboard.press("ArrowDown")
    pg.locator(".shell-card.is-on", has_text="Test it offline").wait_for(timeout=WAIT_MS)
    assert "Test it offline" in pg.locator(".shell-preview > header").inner_text()
    pg.keyboard.press("ArrowUp")
    pg.locator(".shell-card.is-on", has_text="Add the queue").wait_for(timeout=WAIT_MS)
    assert not [c for c in host.log if c[0] in ("ideas.merge", "ideas.back", "ideas.drop_task")]     # no shortcut merges


def test_the_board_drops_an_idea_and_lists_it_with_its_state_in_words(shell):
    pg, host = shell
    assert "working 1/5" in pg.locator(".board-card", has_text="Sync ideas").inner_text()
    assert "plan ready" in pg.locator(".board-card", has_text="Dark mode").inner_text()
    pg.get_by_role("button", name="New idea").click()
    pg.get_by_label("Your idea").fill("Offline sync")
    pg.get_by_role("button", name="Drop it").click()
    pg.locator(".board-card", has_text="Offline sync").wait_for(timeout=WAIT_MS)
    assert ("ideas.add", {"text": "Offline sync"}) in host.log


def test_below_1024_the_phones_layout_three_tabs_and_the_preview_on_its_own_screen(gui):
    pg, host, errors = _open(gui, {"width": 900, "height": 800}, ready=".shell-tabs")
    try:
        tabs = pg.locator(".shell-tabs")
        assert tabs.get_by_role("tab", name="Review").inner_text().replace("\n", "") == "Review2"
        assert pg.locator(".shell-review").is_hidden() and pg.locator(".shell-board").is_visible()
        tabs.get_by_role("tab", name="Review").click()
        pg.locator(".shell-card", has_text="Add the queue").click()
        pg.locator(".shell-preview.is-open").wait_for(timeout=WAIT_MS)
        box_ = box(pg, ".shell-preview")
        assert box_["x"] == 0 and box_["width"] == 900
        pg.get_by_role("button", name="Back", exact=True).click()
        assert pg.locator(".shell-card").first.is_visible()
    finally:
        pg.close()
    assert not errors, "\n".join(errors)


def test_the_first_start_shows_the_first_screen_then_opens_the_shell(gui):
    onboarding = {"step": "tools", "steps": ["tools", "who", "town"], "n": 0, "again": False, "raising": None, "classes": [], "only_kin": "",
                  "tools": {"ready": True, "warder": True, "warder_agy": "", "cli": [], "others": [], "missing": [], "recommended": [],
                            "rows": [{"id": "claude", "title": "Claude Code", "mark": "✱", "enabled": True, "billing": "subscription", "version": "2.0",
                                      "logged_in": True, "login": "", "check": None, "risk": ""}]}}
    pg, host, errors = _open(gui, host=StubHost(onboarding=onboarding), ready=".gui-onb__card")
    try:
        card = pg.locator(".gui-onb__card").inner_text()
        assert "Your AI tools" in card and "Claude Code" in card
        for gone in ("Who are you", "Mission", "Skip: empty town", "Security reviewer"):
            assert gone not in pg.locator(".gui-onb").inner_text()
        pg.get_by_role("button", name="Open the board", exact=True).click()
        pg.locator(".shell-card").first.wait_for(timeout=WAIT_MS)
        assert ("onboarding.skip", {}) in host.log and ("onboarding.close", {}) in host.log
    finally:
        pg.close()
    assert not errors, "\n".join(errors)
