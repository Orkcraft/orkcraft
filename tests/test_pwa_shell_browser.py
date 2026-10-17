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

    @staticmethod
    def idea(slug, title, state, order):
        return {"slug": slug, "title": title, "track": "general", "order": order, "state": state, "size": "M", "talk": []}

    def commands(self) -> dict:
        names = ("board", "page", "review_list", "agents", "task", "diff", "merge", "back", "drop_task", "stop_task", "into", "todo", "say",
                 "plan", "start", "stop", "move", "add", "drop")
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
        self.calls.append((name, dict(a)))
        if name == "ideas.board":
            ideas = [i | {"thesis": "Gist in one line", "asks": 0, "updated": "", "progress": {"done": 1, "total": 5} if i["slug"] == "sync" else {"done": 0, "total": 0}}
                     for i in self.ideas.values()]
            return {"tracks": [{"slug": "general", "title": "General", "about": "", "criteria": [], "deadline": "", "order": 0, "count": 2}], "ideas": ideas,
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
            return {"roles": [{"role": "taskmaster", "name": "Taskmaster", "state": "waiting",
                               "waits_on": {"idea": "dark", "text": "waiting for your answers on “Dark mode”"}, "chips": []},
                              {"role": "grunt", "name": "Grunts", "chips": chips}], "done_today": [{"idea": "sync", "task": "k1", "title": "Read the sync code"}]}
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
            return self.bump({"slug": "new"})
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
        assert await green.get_by_text("Drop this result?").is_visible()
        await green.get_by_role("button", name="Keep it").click()
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
        await page.get_by_role("button", name="Drop it").click()
        assert await _called(stub, "ideas.add", {"text": "Offline mode", "track": "general"})
