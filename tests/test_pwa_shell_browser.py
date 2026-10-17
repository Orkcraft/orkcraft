"""The v1 shell on a phone (gui/static/pwa/board.js, shell-*.js; docs/specs/33-v1-shell.md §6, §8): Chromium at 390 × 844, paired
over the phone listener, against a stub that answers the §5 commands. Three tabs with their counts; the preview (an idea's spec,
a plan, a task, a result's code) on its own screen with Back and its actions pinned at the foot; no horizontal scroll of the
page. Screenshots to docs/design/img/v1/ when ORKCRAFT_SHOTS is set."""
from __future__ import annotations

import asyncio
import copy
import os
from contextlib import asynccontextmanager
from pathlib import Path

import pytest

pw = pytest.importorskip("playwright.async_api")

from orkcraft.gui import mobile, phone_tls  # noqa: E402
from tests.test_phones import _listening, _serve  # noqa: E402
from tests.test_pwa_browser import CHROMIUM, WAIT_MS, _spki  # noqa: E402

SHOTS = Path(__file__).resolve().parent.parent / "docs" / "design" / "img" / "v1"
SECTIONS = ["Gist", "Why", "In", "Out", "Risks", "Open questions", "Estimate", "Stages", "Decisions"]
GREEN = {"passed": 20, "failed": 0, "failing": [], "tail": "20 passed", "green": True}
RED = {"passed": 10, "failed": 10, "failing": ["tests/test_sync.py::test_retry", "tests/test_sync.py::test_queue"], "tail": "10 failed", "green": False}
LONG = "+" + "x" * 300
PATCH = f"diff --git a/sync.py b/sync.py\n@@ -1,2 +1,3 @@\n keep = 1\n-old = 2\n+new = 3\n{LONG}\n"


def task(tid, title, state, after=(), **more):
    return {"id": tid, "title": title, "brief": f"Brief of {title}", "tier": "warrior", "after": list(after), "state": state,
            "branch": f"idea/sync/{tid}", "commit": "", "session": "s", "cost": 0.42, "tokens": 10, "started": "", "finished": "2026-10-17T10:00:00",
            "error": "", "note": "", "round": 1, "tests": None, "diff": None, "conflict": "", "why": "", **more}


class Stub:
    """The host's §5 commands over a few ideas in memory."""

    def __init__(self) -> None:
        self.rev = 1
        self.calls: list[tuple[str, dict]] = []
        self.into, self.push = "dev", False
        self.todos = [{"idea": "sync", "id": "t1", "title": "API_KEY", "kind": "secret", "why": "The sync service needs it", "choices": [],
                       "steps": [], "done": False}]
        self.plan = {"idea": "sync", "estimate": {"tasks": 5, "usd_low": 1.2, "usd_high": 3.5}, "passed_at": "x",
                     "todos": [{**self.todos[0], "for": ["k2", "k3"]}],
                     "tasks": [task("k1", "Read the sync code", "merged"),
                               task("k2", "Add the queue", "review", ["k1"], tests=GREEN, diff={"files": 14, "added": 320, "removed": 41}),
                               task("k3", "Retry on a lost signal", "running", ["k2"]),
                               task("k4", "Test it offline", "review", ["k3"], tests=RED, round=2, diff={"files": 3, "added": 12, "removed": 0},
                                    conflict="conflicts with dev in a.py, b.py"),
                               task("k5", "Write the notes", "waiting", ["k4"])]}
        self.ideas = {"sync": self.idea("sync", "Sync ideas between the phone and the town", "working", 0),
                      "dark": self.idea("dark", "Dark mode", "plan", 1)}
        self.goals = {"general": self.goal("general", "General", "normal", "ready")}
        self.roles = {"taskmaster": {"slug": "taskmaster", "name": "Taskmaster", "model": "elder", "max_parallel": 1, "instruction": "", "builtin": True},
                      "grunt": {"slug": "grunt", "name": "Grunt", "model": "", "max_parallel": 8, "instruction": "", "builtin": True}}
        self.kinds = {k: "grunt" for k in ("code", "tests", "docs", "text", "research")}

    @staticmethod
    def idea(slug, title, state, order):
        return {"slug": slug, "title": title, "track": "general", "order": order, "state": state, "size": "M", "talk": [], "priority": "normal"}

    @staticmethod
    def goal(slug, title, priority, state, **more):
        return {"slug": slug, "title": title, "about": "", "criteria": [], "deadline": "", "order": 0, "count": 2, "priority": priority, "metrics": [],
                "links": [], "summary": "", "questions": [], "state": state, "error": "", **more}

    def commands(self) -> dict:
        names = ("board", "page", "review_list", "agents", "task", "diff", "merge", "back", "drop_task", "stop_task", "into", "todo", "say",
                 "plan", "start", "stop", "move", "add", "drop", "log", "logs", "goal_save", "goal", "read_now", "roles", "role_save", "role_drop",
                 "kind_set", "doc")
        return {f"ideas.{n}": (lambda a, n=n: self.run(f"ideas.{n}", a)) for n in names}

    def results(self):
        return [{"idea": "sync", "idea_title": self.ideas["sync"]["title"], "task": t["id"], "title": t["title"], "round": t["round"], "tests": t["tests"],
                 "diff": t["diff"], "cost": t["cost"], "conflict": t["conflict"], "finished": t["finished"]} for t in self.plan["tasks"] if t["state"] == "review"]

    def find(self, a):
        return next(t for t in self.plan["tasks"] if t["id"] == a["task"])

    def bump(self, result):
        self.rev += 1
        return result

    def run(self, name, a):
        device = a.get("device")                      # the listener adds it to every board command (mobile.guard)
        assert device == "phone"
        a = {k: v for k, v in a.items() if k != "device" or name == "ideas.log"}
        self.calls.append((name, dict(a)))
        if name == "ideas.board":
            ideas = [i | {"thesis": "Gist in one line", "asks": 0, "updated": "", "progress": {"done": 1, "total": 5} if i["slug"] == "sync" else {"done": 0, "total": 0}}
                     for i in self.ideas.values()]
            return {"tracks": list(self.goals.values()), "ideas": ideas,
                    "today": {"todos": self.todos, "needs_you": [{"idea": "dark", "kind": "plan", "title": "Dark mode", "text": "Plan ready"}]},
                    "batch_next": "", "rev": self.rev}
        if name == "ideas.page":
            i = self.ideas[a["slug"]]
            return {"slug": i["slug"], "title": i["title"], "track": "general", "state": i["state"], "size": "M",
                    "sections": [{"name": n, "thesis": f"{n} in one line", "text": f"{n} in one line\nAnd the {n} at length."} for n in SECTIONS],
                    "talk": [], "plan": copy.deepcopy(self.plan) if a["slug"] == "sync" else None, "busy": False}
        if name == "ideas.review_list":
            return {"into": self.into, "push": self.push, "branches": ["dev", "main"], "results": self.results()}
        if name == "ideas.agents":
            chips = [{"idea": "sync", "idea_title": self.ideas["sync"]["title"], "task": t["id"], "title": t["title"], "state": t["state"], "tier": "warrior", "note": ""}
                     for t in self.plan["tasks"] if t["state"] in ("running", "review")]
            blocks = [{"role": "taskmaster", "name": "Taskmaster", "model": "elder", "max_parallel": 1, "builtin": True, "spend_today": 0, "state": "waiting",
                       "waits_on": {"idea": "dark", "text": "waiting for your answers on “Dark mode”"}, "chips": []},
                      {"role": "grunt", "name": "Grunts", "model": "", "max_parallel": 8, "builtin": True, "spend_today": 1.25, "chips": chips,
                       "kinds": [k for k, r in self.kinds.items() if r == "grunt"]}]
            blocks += [{"role": r["slug"], "name": r["name"], "model": r["model"], "max_parallel": r["max_parallel"], "builtin": False, "spend_today": 0,
                        "chips": [], "kinds": [k for k, x in self.kinds.items() if x == r["slug"]]} for r in self.roles.values() if not r["builtin"]]
            return {"roles": blocks, "done_today": [{"idea": "sync", "task": "k1", "title": "Read the sync code", "role": "grunt"}]}
        if name == "ideas.roles":
            names = {"code": "Code", "tests": "Tests", "docs": "Docs", "text": "Text for people", "research": "Research"}
            return {"roles": [r | {"spend_today": 0} for r in self.roles.values()],
                    "kinds": [{"kind": k, "label": names[k], "role": r} for k, r in self.kinds.items()],
                    "models": [{"id": "", "label": "The task's own tier"}, {"id": "elder", "label": "Elder tier (opus)"},
                               {"id": "warrior", "label": "Warrior tier (sonnet)"}, {"id": "laborer", "label": "Laborer tier (haiku)"}]}
        if name == "ideas.role_save":
            slug = a.get("slug") or a["name"].lower().replace(" ", "-")
            self.roles[slug] = {"slug": slug, "name": a["name"], "model": a["model"], "max_parallel": a["max_parallel"],
                                "instruction": a.get("instruction", ""), "builtin": slug in ("taskmaster", "grunt")}
            return self.bump({"slug": slug})
        if name == "ideas.role_drop":
            self.roles.pop(a["slug"])
            self.kinds = {k: ("grunt" if r == a["slug"] else r) for k, r in self.kinds.items()}
            return self.bump({"ok": True})
        if name == "ideas.kind_set":
            self.kinds[a["kind"]] = a["role"]
            return self.bump({"ok": True})
        if name == "ideas.goal_save":
            slug = a.get("slug") or a["title"].lower().replace(" ", "-")
            self.goals[slug] = self.goal(slug, a["title"], a["priority"], "reading", about=a.get("about", ""), deadline=a.get("deadline", ""),
                                         metrics=[m | {"how": ""} for m in a["metrics"]], links=a["links"])
            return self.bump({"slug": slug})
        if name == "ideas.goal":
            g = self.goals[a["slug"]]
            return g | {"description": g["about"], "talk": [], "busy": g["state"] == "reading", "sections": []}
        if name == "ideas.read_now":
            self.ideas[a["slug"]]["state"] = "ready"
            return self.bump({"ok": True})
        if name == "ideas.doc":
            return {"path": a["path"], "text": f"The text of {a['path']}", "truncated": False}
        if name == "ideas.task":
            return self.find(a) | {"idea": a["slug"], "idea_title": self.ideas["sync"]["title"], "log": "== round 1\nreading sync.py\n"}
        if name == "ideas.diff":
            return {"base": self.into, "branch": f"idea/sync/{a['task']}", "commits": [{"sha": "9f2c41d7e0", "subject": "k2: add the queue"}],
                    "files": [{"path": "sync.py", "added": 2, "removed": 1, "patch": PATCH}, {"path": "huge.json", "added": 9000, "removed": 0, "patch": None}],
                    "truncated": True}
        if name == "ideas.merge":
            self.find(a)["state"] = "merged"
            return self.bump({"ok": True, "commit": "abc"})
        if name == "ideas.back":
            self.find(a).update(state="running", round=self.find(a)["round"] + 1)
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
        if name == "ideas.todo":
            self.todos[0]["done"] = a["done"]
            return self.bump({"ok": True})
        if name == "ideas.add":
            slug = a["text"].lower().replace(" ", "-")
            self.ideas[slug] = self.idea(slug, a["text"], "ready" if a.get("now") else "raw", 9) | {"track": a.get("track", "general")}
            return self.bump({"slug": slug})
        if name == "ideas.logs":
            import base64
            return {"name": "orkline-logs.zip", "data": base64.b64encode(b"PK-not-a-real-zip").decode()}
        if name == "ideas.log":
            return {"ok": True}
        return self.bump({"ok": True})


@asynccontextmanager
async def _phone(repo: Path, monkeypatch):
    stub = Stub()
    real = mobile.phone_snapshot

    def snap(host):
        s = real(host)
        return {**s, "rev": f"{s['rev']}-{stub.rev}", "focus": "board", "ideas_rev": stub.rev, "needs_you": 1, "look": "camp",
                "review_count": len(stub.results()),
                "limits": [{"provider": "claude", "name": "Claude", "left": 0.62,
                            "rows": [{"window": "5h", "left": 0.62, "reset": "2026-10-17T18:00"}, {"window": "week", "left": 0.8, "reset": "2026-10-20T09:00"}]},
                           {"provider": "agy", "name": "Antigravity", "left": 0.15, "rows": [{"window": "daily", "left": 0.15, "reset": ""}]}]}
    monkeypatch.setattr(mobile, "phone_snapshot", snap)
    for name in stub.commands():
        monkeypatch.setitem(mobile.COMMANDS, name, None)
    server, task_ = await _serve(repo)
    server.host.commands.update(stub.commands())
    try:
        offer = server.host.command("phones.pair")
        await _listening(server)
        async with pw.async_playwright() as p:
            flags = [f"--ignore-certificate-errors-spki-list={_spki(phone_tls.paths(server.phones.cert_folder)[0])}"]
            try:
                browser = await (p.chromium.launch(executable_path=CHROMIUM, args=flags) if CHROMIUM else p.chromium.launch(args=flags))
            except Exception as e:                         # noqa: BLE001 — no browser here
                pytest.skip(f"no Chromium for Playwright here: {e}")
            try:
                ctx = await browser.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2, has_touch=True, ignore_https_errors=True)
                page = await ctx.new_page()
                errors: list[str] = []
                page.on("pageerror", lambda e: errors.append(f"pageerror: {e}"))
                await page.goto(f"{server.phones.address}/app/#pair={offer['code']}")
                await page.locator(".board-tabs").wait_for(timeout=WAIT_MS)
                yield stub, page
                assert not errors, "\n".join(errors)
            finally:
                await browser.close()
    finally:
        server.stop()
        await asyncio.wait_for(task_, 10)


async def _shot(page, name: str) -> None:
    if os.environ.get("ORKCRAFT_SHOTS"):
        SHOTS.mkdir(parents=True, exist_ok=True)
        await page.screenshot(path=str(SHOTS / f"{name}.png"))


async def _called(stub, name, args=None, timeout=5.0):
    """The stub got this command (a command goes over the phone's socket and the listener: it takes a moment)."""
    for _ in range(int(timeout * 20)):
        if any(c[0] == name and (args is None or c[1] == args) for c in stub.calls):
            return True
        await asyncio.sleep(0.05)
    return False


NO_SCROLL = "document.documentElement.scrollWidth <= 390 && document.body.scrollWidth <= 390"
SMALL = """() => [...document.querySelectorAll('.board button, .board input, .board textarea, .screen button, .screen input')]
    .filter((b) => b.offsetParent && !b.closest('[hidden]') && !b.matches('.sec-head *')).map((b) => [b.textContent || b.getAttribute('aria-label'), b.getBoundingClientRect().height])
    .filter(([, h]) => h < 43)"""


@pytest.mark.asyncio
async def test_three_tabs_with_their_counts_the_top_bar_and_no_camp(fake_repo, monkeypatch):
    async with _phone(fake_repo, monkeypatch) as (stub, page):
        tabs = page.locator(".board-tabs")
        assert [await b.get_attribute("aria-label") for b in await tabs.get_by_role("tab").all()] == ["Board, 2", "Agents", "Review, 2"]
        assert await page.evaluate("document.documentElement.dataset.look") == "office"        # the phone's look is camp: not here
        assert await page.locator(".dock, .camp, .grid, .head").count() == 0
        top = page.locator(".board-bar")
        assert "Stop all" in await top.inner_text() and await top.get_by_role("button", name="Settings").is_visible()
        chip = top.locator(".limit-chip")
        assert "15 %" in await chip.inner_text() and "is-warn" in await chip.get_attribute("class")      # the smallest of all tools
        await chip.click()
        sheet = page.get_by_role("dialog", name="What is left")
        await sheet.wait_for(timeout=WAIT_MS)
        assert "Claude" in await sheet.inner_text() and "resets at 18:00" in await sheet.inner_text()
        await sheet.get_by_role("button", name="Close").click()
        await page.get_by_role("heading", name="Needs you").wait_for(timeout=WAIT_MS)
        await _shot(page, "phone-board-390x844")
        await tabs.get_by_role("tab").nth(1).click()
        await page.locator(".chip", has_text="Retry on a lost signal").wait_for(timeout=WAIT_MS)
        assert "waiting for your answers" in await page.locator(".agents").inner_text() and "Done today (1)" in await page.locator(".agents").inner_text()
        await _shot(page, "phone-agents-390x844")
        await tabs.get_by_role("tab").nth(2).click()
        await page.locator(".result").first.wait_for(timeout=WAIT_MS)
        await _shot(page, "phone-review-390x844")
        for tab in range(3):
            await tabs.get_by_role("tab").nth(tab).click()
            assert await page.evaluate(NO_SCROLL)
        await tabs.get_by_role("tab").nth(0).click()
        assert await page.evaluate(SMALL) == []
        await page.get_by_role("button", name="Stop all").click()
        await page.get_by_role("button", name="Stop every ork").click()
        await page.get_by_role("dialog", name="Stop all").wait_for(state="hidden", timeout=WAIT_MS)


@pytest.mark.asyncio
async def test_an_idea_a_todo_a_chip_and_a_result_each_open_on_their_own_screen_with_back(fake_repo, monkeypatch):
    async with _phone(fake_repo, monkeypatch) as (stub, page):
        await page.locator(".idea-card", has_text="Dark mode").get_by_role("button").click()          # an idea → its spec
        screen = page.locator(".screen")
        await screen.locator(".sec").first.wait_for(timeout=WAIT_MS)
        box = await screen.bounding_box()
        assert box["x"] == 0 and box["y"] == 0 and box["width"] == 390 and box["height"] == 844       # its own full screen
        assert await screen.locator(".sec").count() == len(SECTIONS) and "spec" in (await screen.locator(".screen-head").inner_text()).lower()
        await _shot(page, "phone-spec-390x844")
        bar = await screen.locator(".screen-bar").bounding_box()
        assert abs(bar["y"] + bar["height"] - 844) < 2                                                 # the actions pinned at the foot
        assert "Start · 5 tasks" in await screen.locator(".screen-bar").inner_text() or "Start" in await screen.locator(".screen-bar").inner_text()
        assert await _called(stub, "ideas.log", {"event": "opened", "what": "idea", "ref": "dark", "device": "phone"})
        await page.get_by_role("button", name="Back", exact=True).click()
        await page.locator(".screen").wait_for(state="hidden", timeout=WAIT_MS)
        assert (await page.locator(".board-tab.is-active").inner_text()).startswith("Board")                     # back on the tab it came from

        await page.locator(".todo-open", has_text="API_KEY").click()                                  # a to-do → the plan, scrolled to it
        target = page.locator(".screen .plan-todo.is-target")
        await target.wait_for(timeout=WAIT_MS)
        assert "tasks k2 and k3 wait for it" in await target.inner_text()
        await page.go_back()                                                                           # the system back gesture
        await page.locator(".screen").wait_for(state="hidden", timeout=WAIT_MS)

        await page.get_by_role("tab", name="Agents").click()                                           # a chip → its task, with Stop pinned
        await page.locator(".chip", has_text="Retry on a lost signal").click()
        await page.locator(".screen .log").wait_for(timeout=WAIT_MS)
        text = await page.locator(".screen-body").inner_text()
        assert "Brief of Retry on a lost signal" in text and "reading sync.py" in text and "idea/sync/k3" in text
        await _shot(page, "phone-task-390x844")
        await page.locator(".screen-bar").get_by_role("button", name="Stop").click()
        assert await _called(stub, "ideas.stop_task", {"slug": "sync", "task": "k3"})
        await page.get_by_role("button", name="Back", exact=True).click()
        assert (await page.locator(".board-tab.is-active").inner_text()).startswith("Agents")


@pytest.mark.asyncio
async def test_review_merge_is_off_on_red_send_back_needs_a_line_and_a_patch_scrolls_inside_its_box(fake_repo, monkeypatch):
    async with _phone(fake_repo, monkeypatch) as (stub, page):
        await page.get_by_role("tab", name="Review").click()
        green, red = page.locator(".result", has_text="Add the queue"), page.locator(".result", has_text="Test it offline")
        assert "20 / 20 passed" in await green.inner_text() and "14 files, +320 −41" in await green.inner_text()
        assert "10 / 20 failed" in await red.inner_text() and "round 2" in await red.inner_text() and "conflicts with dev in a.py, b.py" in await red.inner_text()
        merge = red.get_by_role("button", name="Merge into dev")
        assert await merge.is_disabled() and "red" in await red.locator(".why").inner_text()
        await red.get_by_role("button", name="Fix", exact=True).click()                                # Fix: the line prefilled, required
        line = red.get_by_label("What to fix, in one line")
        assert (await line.input_value()).startswith("Resolve the conflict with dev")
        await line.fill("")
        assert await red.locator(".back-line .ok-btn.primary").is_disabled()
        await line.fill("Rebase and keep both queues")
        await red.locator(".back-line .ok-btn.primary").click()
        assert await _called(stub, "ideas.back", {"slug": "sync", "task": "k4", "why": "Rebase and keep both queues"})
        await page.locator(".result", has_text="Test it offline").wait_for(state="detached", timeout=WAIT_MS)

        await page.get_by_role("button", name="Merge into dev ▾").click()                              # Merge into ▾: the branches
        sheet = page.get_by_role("dialog", name="Merge into")
        await sheet.get_by_role("radio", name="main").click()
        assert await _called(stub, "ideas.into", {"branch": "main"})
        await green.get_by_role("button", name="Drop…").click()                                        # Drop asks first, apart from Merge
        drop = page.get_by_role("dialog", name="Drop this result?")                                    # … on a sheet (spec 34 §5)
        await drop.wait_for(timeout=WAIT_MS)
        await drop.get_by_role("button", name="Keep it").click()
        await drop.wait_for(state="hidden", timeout=WAIT_MS)
        assert ("ideas.drop_task", {"slug": "sync", "task": "k2"}) not in stub.calls

        await green.locator(".result-open").click()                                                     # the code on its own screen
        screen = page.locator(".screen")
        await screen.locator(".commits").wait_for(timeout=WAIT_MS)
        await screen.locator(".file", has_text="sync.py").locator("summary").click()
        patch = screen.locator(".patch")
        await patch.wait_for(timeout=WAIT_MS)
        assert await screen.locator(".pl.is-add").count() == 2 and await screen.locator(".pl.is-del").count() == 1
        assert await patch.evaluate("(el) => el.scrollWidth > el.clientWidth")                         # it scrolls sideways in its own box …
        assert await page.evaluate(NO_SCROLL) and await page.evaluate("document.querySelector('.screen-body').scrollWidth <= 390")   # … never the page
        await screen.locator(".file", has_text="huge.json").locator("summary").click()
        await screen.get_by_text("Too large to show.", exact=True).wait_for(timeout=WAIT_MS)
        await _shot(page, "phone-result-390x844")
        bar = screen.locator(".screen-bar")
        bb = await bar.bounding_box()
        assert abs(bb["y"] + bb["height"] - 844) < 2 and await bar.get_by_role("button", name="Merge into main").is_enabled()
        await bar.get_by_role("button", name="Merge into main").click()
        await screen.wait_for(state="hidden", timeout=WAIT_MS)
        assert ("ideas.merge", {"slug": "sync", "task": "k2"}) in stub.calls
        assert await page.get_by_role("tab", name="Review").locator(".count").count() == 1 and await page.locator(".result").count() == 0


@pytest.mark.asyncio
async def test_a_secret_todo_is_entered_over_the_paired_link_on_the_board(fake_repo, monkeypatch):
    async with _phone(fake_repo, monkeypatch) as (stub, page):
        secret = page.locator(".todo", has_text="API_KEY")
        assert await secret.locator("input").get_attribute("type") == "password"
        await secret.locator("input").fill("s3cret")
        await secret.get_by_role("button", name="Store it").click()
        await page.locator(".todo.is-done", has_text="API_KEY").wait_for(timeout=WAIT_MS)
        assert ("ideas.todo", {"idea": "sync", "id": "t1", "done": True, "value": "s3cret"}) in stub.calls
        await page.get_by_role("button", name="New idea").click()                                       # New idea: one field in a sheet
        await page.get_by_label("The idea").fill("Offline mode")
        await page.get_by_role("dialog", name="New idea").get_by_role("button", name="Later").click()
        assert await _called(stub, "ideas.add", {"text": "Offline mode", "now": False, "track": "general"})


@pytest.mark.asyncio
async def test_the_gear_downloads_the_days_logs_on_the_phone_and_tabs_are_logged(fake_repo, monkeypatch):
    async with _phone(fake_repo, monkeypatch) as (stub, page):
        await page.get_by_role("tab", name="Agents").click()
        assert await _called(stub, "ideas.log", {"event": "opened", "what": "tab", "ref": "agents", "device": "phone"})
        await page.get_by_role("button", name="Settings").click()
        sheet = page.get_by_role("dialog", name="Settings")
        await sheet.wait_for(timeout=WAIT_MS)
        assert "Download today's logs" in await sheet.inner_text()
        async with page.expect_download() as got:
            await sheet.get_by_role("button", name="Today", exact=True).click()
        download = await got.value
        assert download.suggested_filename == "orkline-logs.zip"
        assert await _called(stub, "ideas.logs", {"days": 1})



# -- spec 34 round 2 on the phone: sheets, goals, ideas now or later, agents by task type, the top bar -------------------------

def _adds(stub):
    return [a for n, a in stub.calls if n == "ideas.add"]


@pytest.mark.asyncio
async def test_the_top_bar_shows_spend_whole_and_no_band_sits_above_it(fake_repo, monkeypatch):
    async with _phone(fake_repo, monkeypatch) as (stub, page):
        bar = await page.locator(".board-bar").bounding_box()
        assert bar["y"] == 0 and bar["x"] == 0 and bar["width"] == 390                                  # no empty band above it
        spend = page.locator(".board-spend")
        text = await spend.inner_text()
        assert "Spend today" in text and "…" not in text and "..." not in text                          # the whole of today's spend
        assert await spend.evaluate("e => e.scrollWidth <= e.clientWidth + 1 && getComputedStyle(e).textOverflow !== 'ellipsis'")
        assert await page.evaluate(NO_SCROLL)


@pytest.mark.asyncio
async def test_every_sheet_is_dimmed_closes_on_esc_and_keeps_its_buttons_at_its_foot(fake_repo, monkeypatch):
    async with _phone(fake_repo, monkeypatch) as (stub, page):
        opens = [("New goal", lambda: page.get_by_role("button", name="New goal", exact=True).click()),
                 ("New idea", lambda: page.get_by_role("button", name="New idea", exact=True).click()),
                 ("Settings", lambda: page.get_by_role("button", name="Settings").click()),
                 ("Stop all", lambda: page.get_by_role("button", name="Stop all").click())]
        for name, opener in opens:
            await opener()
            sheet = page.get_by_role("dialog", name=name)
            await sheet.wait_for(timeout=WAIT_MS)
            shade = await sheet.evaluate("e => getComputedStyle(e, '::backdrop').backgroundColor")
            assert shade.startswith("rgba(") and 0.2 < float(shade.split(",")[3].strip(" )")) < 0.9, (name, shade)          # dimmed
            assert await sheet.evaluate("e => getComputedStyle(e).backgroundColor") not in ("rgba(0, 0, 0, 0)", "transparent")  # opaque panel
            box = await sheet.bounding_box()
            assert box["x"] == 0 and box["width"] == 390 and box["y"] + box["height"] == 844                # from the bottom, full width
            assert await page.evaluate(NO_SCROLL)
            await page.keyboard.press("Escape")
            await sheet.wait_for(state="hidden", timeout=WAIT_MS)
        await page.get_by_role("button", name="New goal", exact=True).click()                           # the buttons are pinned at the foot
        sheet = page.get_by_role("dialog", name="New goal")
        foot = await sheet.locator(".sheet-foot").bounding_box()
        assert foot["y"] + foot["height"] >= 844 - 2
        await page.keyboard.press("Escape")


@pytest.mark.asyncio
async def test_new_goal_sheet_metrics_links_priority_then_the_goal_reads_and_shows_its_summary(fake_repo, monkeypatch):
    async with _phone(fake_repo, monkeypatch) as (stub, page):
        await page.get_by_role("button", name="New goal", exact=True).click()
        sheet = page.get_by_role("dialog", name="New goal")
        assert await sheet.get_by_role("button", name="Save goal").is_disabled()                        # a title is required
        await sheet.get_by_label("Title").fill("Grow installs")
        await sheet.get_by_label("Description").fill("More people try Orkline.")
        await sheet.get_by_label("Metric 1: what is measured").fill("weekly installs")
        await sheet.get_by_label("Metric 1: the target").fill("50")
        await sheet.get_by_role("button", name="+ Add a metric").click()
        await sheet.get_by_label("Metric 2: what is measured").fill("signups")
        await sheet.get_by_role("button", name="Remove metric 2").click()
        await sheet.get_by_role("radio", name="High").click()
        await sheet.get_by_label("Link 1", exact=True).fill("docs/plan.md")
        await sheet.get_by_role("button", name="+ Add a link").click()
        await sheet.get_by_label("Link 2", exact=True).fill("https://example.com/post")
        await sheet.get_by_label("Deadline").fill("2026-12-01")
        await _shot(page, "phone-new-goal-390x844")
        await sheet.get_by_role("button", name="Save goal").click()
        assert await _called(stub, "ideas.goal_save", {"title": "Grow installs", "about": "More people try Orkline.", "priority": "high",
                                                       "deadline": "2026-12-01", "metrics": [{"name": "weekly installs", "target": "50"}],
                                                       "links": ["docs/plan.md", "https://example.com/post"]})
        screen = page.locator(".screen")
        await screen.get_by_text("the Taskmaster is reading", exact=False).first.wait_for(timeout=WAIT_MS)      # the goal on its own screen: reading
        stub.goals["grow-installs"].update(state="asks", summary="Installs are the first step.", questions=["Which channel first?"],
                                           metrics=[{"name": "weekly installs", "target": "50", "how": "npm downloads, per week"}])
        stub.bump({})
        await screen.get_by_text("Installs are the first step.").wait_for(timeout=WAIT_MS)
        text = await screen.inner_text()
        assert "npm downloads, per week" in text and "Which channel first?" in text and "asks you" in text
        await screen.get_by_label("Answer the Taskmaster").fill("npm first")
        await screen.get_by_role("button", name="Send", exact=True).click()
        assert await _called(stub, "ideas.say", {"slug": "grow-installs", "text": "npm first", "goal": True})
        await screen.get_by_role("button", name="docs/plan.md").click()                                 # a repository path opens on a screen
        await screen.get_by_text("The text of docs/plan.md").wait_for(timeout=WAIT_MS)
        await screen.get_by_role("button", name="← Back to the goal").click()
        assert await screen.get_by_role("link", name="https://example.com/post").get_attribute("target") == "_blank"
        await screen.get_by_role("button", name="Edit goal", exact=True).click()                        # Edit: the sheet is filled
        sheet = page.get_by_role("dialog", name="Edit goal")
        assert await sheet.get_by_label("Title").input_value() == "Grow installs"
        assert await sheet.get_by_label("Metric 1: the target").input_value() == "50"
        await page.keyboard.press("Escape")
        await page.get_by_role("button", name="Back", exact=True).click()
        goal = page.locator(".goal-card", has_text="Grow installs")
        assert "High" in await goal.inner_text() and "asks you" in await goal.inner_text()
        assert await page.evaluate(NO_SCROLL)


@pytest.mark.asyncio
async def test_new_idea_sheet_process_now_later_closed_with_text_and_closed_empty(fake_repo, monkeypatch):
    async with _phone(fake_repo, monkeypatch) as (stub, page):
        await page.get_by_role("button", name="New idea", exact=True).click()
        sheet = page.get_by_role("dialog", name="New idea")
        await sheet.get_by_label("The idea", exact=True).fill("Dark mode please")
        await _shot(page, "phone-new-idea-390x844")
        await sheet.get_by_role("button", name="Process now").click()
        await page.locator(".idea-card", has_text="Dark mode please").wait_for(timeout=WAIT_MS)
        assert _adds(stub) == [{"text": "Dark mode please", "now": True, "track": "general"}]
        assert "ready" in await page.locator(".idea-card", has_text="Dark mode please").inner_text()    # read at once: not new
        await page.get_by_role("button", name="New idea", exact=True).click()                           # Later
        await page.get_by_label("The idea", exact=True).fill("Later idea")
        await page.get_by_role("dialog", name="New idea").get_by_role("button", name="Later").click()
        await page.locator(".idea-card", has_text="Later idea").wait_for(timeout=WAIT_MS)
        assert _adds(stub)[-1] == {"text": "Later idea", "now": False, "track": "general"}
        await page.get_by_role("button", name="New idea", exact=True).click()                           # closed with text: saved as Later
        await page.get_by_label("The idea", exact=True).fill("Closed with text")
        await page.get_by_role("dialog", name="New idea").get_by_role("button", name="Close").click()
        await page.locator(".idea-card", has_text="Closed with text").wait_for(timeout=WAIT_MS)
        assert _adds(stub)[-1] == {"text": "Closed with text", "now": False, "track": "general"}
        await page.get_by_role("button", name="New idea", exact=True).click()                           # Esc with text: Later too
        await page.get_by_label("The idea", exact=True).fill("Saved by Esc")
        await page.keyboard.press("Escape")
        await page.locator(".idea-card", has_text="Saved by Esc").wait_for(timeout=WAIT_MS)
        assert _adds(stub)[-1] == {"text": "Saved by Esc", "now": False, "track": "general"}
        before = len(_adds(stub))                                                                       # closed empty: nothing
        await page.get_by_role("button", name="New idea", exact=True).click()
        await page.get_by_role("dialog", name="New idea").get_by_role("button", name="Close").click()
        await page.wait_for_timeout(300)
        assert len(_adds(stub)) == before
        card = page.locator(".idea-card", has_text="Closed with text")                                  # a new idea's card has Process now
        await card.get_by_role("button", name="Process now: Closed with text").click()
        assert await _called(stub, "ideas.read_now", {"slug": "closed-with-text"})


@pytest.mark.asyncio
async def test_agents_add_an_agent_give_it_a_task_type_edit_and_delete_it(fake_repo, monkeypatch):
    async with _phone(fake_repo, monkeypatch) as (stub, page):
        await page.get_by_role("tab", name="Agents").click()
        agents = page.locator(".agents")
        await agents.get_by_role("button", name="+ Add agent").wait_for(timeout=WAIT_MS)
        assert "Task types" in await agents.inner_text()
        for kind in ("Code", "Tests", "Docs", "Text for people", "Research"):
            assert await agents.get_by_label(f"Agent for {kind}").input_value() == "grunt"
        await agents.get_by_role("button", name="+ Add agent").click()
        sheet = page.get_by_role("dialog", name="Add agent")
        await sheet.get_by_label("Name").fill("Docs scribe")
        await sheet.get_by_label("Model").select_option("laborer")
        await sheet.get_by_label("At most at once").select_option("3")
        await sheet.get_by_label("Instruction").fill("Write plainly.")
        await sheet.get_by_role("button", name="Save agent").click()
        assert await _called(stub, "ideas.role_save", {"name": "Docs scribe", "model": "laborer", "max_parallel": 3, "instruction": "Write plainly."})
        await agents.locator(".role[data-slug='docs-scribe']").wait_for(timeout=WAIT_MS)
        await agents.get_by_label("Agent for Docs").select_option("docs-scribe")                        # a type assigned
        assert await _called(stub, "ideas.kind_set", {"kind": "docs", "role": "docs-scribe"})
        await agents.get_by_label("Agent for Research").select_option("__new__")                        # New agent… from the type
        sheet = page.get_by_role("dialog", name="Add agent")
        await sheet.get_by_label("Name").fill("Reader")
        await sheet.get_by_role("button", name="Save agent").click()
        assert await _called(stub, "ideas.kind_set", {"kind": "research", "role": "reader"})
        if os.environ.get("ORKCRAFT_SHOTS"):
            await page.wait_for_timeout(500)
            await agents.locator(".kinds").scroll_into_view_if_needed()
            await _shot(page, "phone-agents-types-390x844")
        await agents.get_by_role("button", name="Edit Docs scribe").click()
        sheet = page.get_by_role("dialog", name="Edit agent")
        assert await sheet.get_by_label("Instruction").input_value() == "Write plainly."
        await sheet.get_by_role("button", name="Delete…").click()
        assert "back to Grunt" in await sheet.inner_text()
        await sheet.get_by_role("button", name="Delete agent").click()
        await agents.locator(".role[data-slug='docs-scribe']").wait_for(state="detached", timeout=WAIT_MS)
        assert await agents.get_by_label("Agent for Docs").input_value() == "grunt"
        assert await page.evaluate(NO_SCROLL)


@pytest.mark.asyncio
async def test_pair_a_phone_in_the_gear_says_where_it_is_done_and_how_the_phone_reaches_the_computer(fake_repo, monkeypatch):
    async with _phone(fake_repo, monkeypatch) as (stub, page):
        await page.get_by_role("button", name="Settings").click()
        await page.get_by_role("button", name="Pair a phone").click()
        sheet = page.get_by_role("dialog", name="Pair a phone")
        await sheet.wait_for(timeout=WAIT_MS)
        text = await sheet.inner_text()
        assert "On the same Wi-Fi" in text and "tailnet" in text and "Install Tailscale" in text and "from the computer" in text
        await _shot(page, "phone-pair-390x844")
        assert await page.evaluate(NO_SCROLL)
