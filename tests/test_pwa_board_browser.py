"""The board on a phone, in focus (gui/static/pwa/board.js; docs/specs/29a-board-focus.md §7): Chromium at 390 × 844,
paired over the phone listener, against a stub that answers the spec's §6 commands (the keeper and the runner are
other parts). What a person sees and taps: only the board, Today's to-dos, an idea dropped from + under General, its
sections, reordering, Take it to work and Start. In Camp the board wears v4's kit (docs/design/design-system-v4.md), in
Office it does not; the v4 shots go to docs/design/img/board-v4/ when BOARD_V4_SHOTS is set."""
from __future__ import annotations

import asyncio
import os
from contextlib import asynccontextmanager
from pathlib import Path

import pytest

pw = pytest.importorskip("playwright.async_api")

from orkcraft.gui import mobile, phone_tls  # noqa: E402
from tests.test_phones import _listening, _serve  # noqa: E402
from tests.test_pwa_browser import CHROMIUM, WAIT_MS, _spki  # noqa: E402

SHOTS = os.environ.get("BOARD_SHOTS", "")
V4_SHOTS = Path(__file__).resolve().parent.parent / "docs" / "design" / "img" / "board-v4"
SECTIONS = ["Gist", "Why", "In", "Out", "Risks", "Open questions", "Estimate", "Stages", "Decisions"]


class Stub:
    """The host's §6 commands over a few ideas in memory."""

    def __init__(self) -> None:
        self.rev = 1
        self.calls: list[tuple[str, dict]] = []
        self.ideas: dict[str, dict] = {}
        self.todos = [
            {"idea": "seed", "id": "t1", "title": "Confirm the tag", "kind": "confirm", "why": "k1 waits", "choices": [], "steps": [], "done": False},
            {"idea": "seed", "id": "t2", "title": "API_KEY", "kind": "secret", "why": "to call the service", "choices": [], "steps": [], "done": False},
            {"idea": "seed", "id": "t3", "title": "Pick a region", "kind": "choice", "why": "", "choices": ["eu", "us"], "steps": [], "done": False},
            {"idea": "seed", "id": "t4", "title": "Open the console", "kind": "instructions", "why": "", "choices": [], "steps": ["Log in", "Copy the id"], "done": False},
        ]
        self.needs = [{"idea": "seed", "kind": "asks", "title": "Seed idea", "text": "2 questions"}]
        self.add_idea("seed", "Seed idea", "ready", "A seed\nMore about the seed.")

    def add_idea(self, slug: str, title: str, state: str, gist: str) -> None:
        self.ideas[slug] = {"slug": slug, "title": title, "track": "general", "order": len(self.ideas), "state": state, "size": "M",
                            "gist": gist, "plan": None, "talk": []}

    def bump(self) -> None:
        self.rev += 1

    def ordered(self) -> list[dict]:
        return sorted(self.ideas.values(), key=lambda i: i["order"])

    def commands(self) -> dict:
        return {"ideas.board": self.board, "ideas.page": self.page, "ideas.add": self.add, "ideas.say": self.say, "ideas.plan": self.plan,
                "ideas.start": self.start, "ideas.move": self.move, "ideas.todo": self.todo, "ideas.stop": self.stop}

    def logged(self, name: str, args: dict) -> None:
        self.calls.append((name, dict(args)))

    def board(self, args):
        thesis = lambda i: i["gist"].splitlines()[0]  # noqa: E731
        return {"tracks": [{"slug": "general", "title": "General", "about": "", "criteria": [], "deadline": "", "order": 0,
                            "count": len(self.ideas)}],
                "ideas": [{"slug": i["slug"], "title": i["title"], "track": i["track"], "order": i["order"], "state": i["state"],
                           "size": i["size"], "thesis": thesis(i), "asks": 0, "progress": self.progress(i), "updated": ""}
                          for i in self.ordered()],
                "today": {"todos": self.todos, "needs_you": self.needs}, "batch_next": "", "rev": self.rev}

    @staticmethod
    def progress(i: dict) -> dict:
        tasks = (i["plan"] or {}).get("tasks") or []
        return {"done": sum(k["state"] == "merged" for k in tasks), "total": len(tasks) or 2}

    def page(self, args):
        i = self.ideas[args["slug"]]
        sections = [{"name": n, "thesis": (i["gist"].splitlines()[0] if n == "Gist" else f"{n} in a line"),
                     "text": i["gist"] if n == "Gist" else f"{n} in a line\nAnd the {n} at length."} for n in SECTIONS]
        return {"slug": i["slug"], "title": i["title"], "track": i["track"], "state": i["state"], "size": i["size"], "sections": sections,
                "talk": i["talk"], "plan": i["plan"], "busy": False}

    def add(self, args):
        self.logged("ideas.add", args)
        slug = f"idea-{len(self.ideas)}"
        self.add_idea(slug, args["text"].splitlines()[0][:40], "raw", args["text"])
        self.bump()
        return {"slug": slug}

    def say(self, args):
        self.logged("ideas.say", args)
        self.ideas[args["slug"]]["talk"].append({"who": "you", "text": args["text"], "section": args.get("section", ""), "at": ""})
        self.bump()
        return {"ok": True}

    def plan(self, args):
        self.logged("ideas.plan", args)
        i = self.ideas[args["slug"]]
        i["state"] = "plan"
        i["plan"] = {"idea": i["slug"], "estimate": {"tasks": 2, "usd_low": 0.6, "usd_high": 1.8}, "todos": [],
                     "tasks": [{"id": "k1", "title": "Write it", "tier": "warrior", "after": [], "state": "waiting", "commit": "", "error": ""},
                               {"id": "k2", "title": "Test it", "tier": "laborer", "after": ["k1"], "state": "waiting", "commit": "", "error": ""}]}
        self.bump()
        return {"ok": True}

    def start(self, args):
        self.logged("ideas.start", args)
        self.ideas[args["slug"]]["state"] = "working"
        self.ideas[args["slug"]]["plan"]["tasks"][0]["state"] = "running"
        self.bump()
        return {"ok": True}

    def stop(self, args):
        self.logged("ideas.stop", args)
        return {"ok": True}

    def move(self, args):
        self.logged("ideas.move", args)
        order = [i["slug"] for i in self.ordered() if i["slug"] != args["slug"]]
        order.insert(order.index(args["before"]) if args.get("before") else len(order), args["slug"])
        for n, slug in enumerate(order):
            self.ideas[slug]["order"] = n
        self.bump()
        return {"ok": True}

    def todo(self, args):
        self.logged("ideas.todo", args)
        for t in self.todos:
            if t["id"] == args["id"]:
                t["done"] = args["done"]
        self.bump()
        return {"ok": True}


@asynccontextmanager
async def _board(repo: Path, monkeypatch, look: str = ""):
    stub = Stub()
    real = mobile.phone_snapshot
    monkeypatch.setattr(mobile, "phone_snapshot", lambda host: {**(snap := real(host)), "rev": f"{snap['rev']}-{stub.rev}", "focus": "board",
                                                                   "ideas_rev": stub.rev, "needs_you": len(stub.needs),
                                                                   **({"look": look} if look else {})})
    for name in stub.commands():
        monkeypatch.setitem(mobile.COMMANDS, name, None)
    server, task = await _serve(repo)
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
                ctx = await browser.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2, has_touch=True,
                                                ignore_https_errors=True)
                page = await ctx.new_page()
                await page.goto(f"{server.phones.address}/app/#pair={offer['code']}")
                await page.locator(".board").wait_for(timeout=WAIT_MS)
                yield stub, page
            finally:
                await browser.close()
    finally:
        server.stop()
        await asyncio.wait_for(task, 10)


async def _shot(page, name: str) -> None:
    if SHOTS:
        Path(SHOTS).mkdir(parents=True, exist_ok=True)
        await page.screenshot(path=str(Path(SHOTS) / f"{name}.png"))


@pytest.mark.asyncio
async def test_in_focus_the_phone_shows_only_the_board_with_stop_all(fake_repo, monkeypatch):
    async with _board(fake_repo, monkeypatch) as (_, page):
        assert await page.locator(".dock, .camp, .grid, .head").count() == 0          # no town: no bar, no camp, no buildings
        assert await page.get_by_role("button", name="Stop all").is_visible()
        for tab in ("Today", "Ideas", "Drop an idea"):
            assert await page.locator(".board-tabs").get_by_role("button", name=tab).count() == 1
        await page.get_by_role("heading", name="Needs you").wait_for(timeout=WAIT_MS)
        await _shot(page, "today")
        assert await page.evaluate("document.documentElement.scrollWidth <= 390")
        small = await page.evaluate("""() => [...document.querySelectorAll('.board button, .board input, .board textarea')]
            .filter((b) => b.offsetParent).map((b) => [b.textContent || b.getAttribute('aria-label'), b.getBoundingClientRect().height])
            .filter(([, h]) => h < 44)""")
        assert small == []


@pytest.mark.asyncio
async def test_today_needs_you_opens_its_idea_and_the_todos_tick_by_kind(fake_repo, monkeypatch):
    async with _board(fake_repo, monkeypatch) as (stub, page):
        await page.locator(".need").first.wait_for(timeout=WAIT_MS)
        await page.get_by_role("button", name="Confirm the tag").click()                 # confirm: a tap ticks it
        await page.locator(".todo.is-done").wait_for(timeout=WAIT_MS)
        assert ("ideas.todo", {"idea": "seed", "id": "t1", "done": True}) in stub.calls
        secret = page.locator(".todo", has_text="API_KEY")
        assert await secret.locator("input").get_attribute("type") == "password"
        await secret.locator("input").fill("s3cret")
        await secret.get_by_role("button", name="Store it").click()
        await page.locator(".todo.is-done", has_text="API_KEY").wait_for(timeout=WAIT_MS)
        assert ("ideas.todo", {"idea": "seed", "id": "t2", "done": True, "value": "s3cret"}) in stub.calls
        await page.locator(".todo", has_text="Pick a region").get_by_role("button", name="us").click()
        await page.locator(".todo.is-done", has_text="Pick a region").wait_for(timeout=WAIT_MS)
        assert ("ideas.todo", {"idea": "seed", "id": "t3", "done": True, "value": "us"}) in stub.calls
        steps = page.locator(".todo", has_text="Open the console")
        assert await steps.locator("li").all_inner_texts() == ["Log in", "Copy the id"]
        await steps.get_by_role("button", name="Done").click()
        await page.locator(".todo.is-done", has_text="Open the console").wait_for(timeout=WAIT_MS)
        await page.locator(".need").first.click()                                        # Needs you opens its idea
        await page.locator(".idea-page .sec").first.wait_for(timeout=WAIT_MS)
        assert "Seed idea" in await page.locator(".idea-name").inner_text()


@pytest.mark.asyncio
async def test_drop_an_idea_open_it_reorder_take_it_to_work_and_start(fake_repo, monkeypatch):
    async with _board(fake_repo, monkeypatch) as (stub, page):
        tabs = page.locator(".board-tabs")
        await tabs.get_by_role("button", name="Drop an idea").click()
        await page.get_by_label("The idea").fill("Let the phone reorder ideas\nBy a long press.")
        await page.get_by_role("button", name="Drop it").click()
        assert stub.calls[0] == ("ideas.add", {"text": "Let the phone reorder ideas\nBy a long press.", "track": "general"})
        card = page.locator(".idea-card", has_text="Let the phone reorder ideas")        # under General, the Ideas tab
        await card.wait_for(timeout=WAIT_MS)
        assert "General" in await page.locator(".track.is-active").inner_text()
        assert "new" in await card.locator(".state-word").inner_text()
        await _shot(page, "ideas")
        await card.get_by_role("button").click()
        gist = page.locator(".sec", has_text="Gist")
        await gist.wait_for(timeout=WAIT_MS)
        assert await gist.locator(".thesis").inner_text() == "Let the phone reorder ideas"      # the thesis only
        assert await page.locator(".sec-text").count() == 0
        await page.locator(".sec", has_text="Risks").get_by_role("button").first.click()        # a tap opens a section
        await page.locator(".sec-text", has_text="And the Risks at length.").wait_for(timeout=WAIT_MS)
        await _shot(page, "idea-section")
        await page.get_by_role("button", name="Ask about Risks").click()
        ask = page.get_by_label("Ask or answer the Taskmaster")
        assert await ask.get_attribute("placeholder") == "About Risks…"
        await ask.fill("What if it scrolls?")
        await page.get_by_role("button", name="Send").click()
        await page.locator(".turn.you", has_text="What if it scrolls?").wait_for(timeout=WAIT_MS)
        assert ("ideas.say", {"slug": "idea-1", "text": "What if it scrolls?", "section": "Risks"}) in stub.calls
        await page.get_by_role("button", name="Move up").click()                                 # ↑ on the opened card
        for _ in range(50):
            if [i["slug"] for i in stub.ordered()] == ["idea-1", "seed"]:
                break
            await page.wait_for_timeout(100)
        assert [i["slug"] for i in stub.ordered()] == ["idea-1", "seed"]
        assert stub.calls[-1] == ("ideas.move", {"slug": "idea-1", "before": "seed"})
        await page.locator('[aria-label="Move up"][disabled]').wait_for(timeout=WAIT_MS)       # first now: nowhere to go up
        stub.ideas["idea-1"]["state"] = "ready"                                                 # the keeper read it (a batch)
        stub.bump()
        await page.get_by_role("button", name="Take it to work").wait_for(timeout=WAIT_MS)       # a changed ideas_rev refreshes
        await page.get_by_role("button", name="Take it to work").click()
        start = page.get_by_role("button", name="Start · 2 tasks · ~$0.6–1.8")
        await start.wait_for(timeout=WAIT_MS)
        assert await page.locator(".task").count() == 2 and "after Write it" in await page.locator(".task").nth(1).inner_text()
        await _shot(page, "plan")
        await start.click()
        await page.get_by_role("button", name="Stop", exact=True).wait_for(timeout=WAIT_MS)
        assert ("ideas.start", {"slug": "idea-1"}) in stub.calls
        await _shot(page, "working")
        await page.get_by_role("button", name="Back to the board").click()
        assert "working 0/2" in await page.locator(".idea-card", has_text="Let the phone reorder ideas").locator(".state-word").inner_text()


@pytest.mark.asyncio
async def test_a_long_press_drag_reorders_the_ideas(fake_repo, monkeypatch):
    async with _board(fake_repo, monkeypatch) as (stub, page):
        stub.add_idea("b", "Second idea", "raw", "Second")
        stub.add_idea("c", "Third idea", "raw", "Third")
        stub.bump()
        await page.locator(".board-tabs").get_by_role("button", name="Ideas").click()
        await page.locator(".idea-card", has_text="Third idea").wait_for(timeout=WAIT_MS)
        box = await page.locator(".idea-card", has_text="Third idea").bounding_box()
        top = await page.locator(".idea-card", has_text="Seed idea").bounding_box()
        x = box["x"] + box["width"] / 2
        await page.mouse.move(x, box["y"] + box["height"] / 2)
        await page.mouse.down()
        await page.wait_for_timeout(700)                                                          # the hold
        await page.mouse.move(x, top["y"] + 4, steps=6)
        await page.mouse.up()
        for _ in range(50):
            if [i["slug"] for i in stub.ordered()][0] == "c":
                break
            await page.wait_for_timeout(100)
        assert [i["slug"] for i in stub.ordered()] == ["c", "seed", "b"]
        assert stub.calls[-1] == ("ideas.move", {"slug": "c", "before": "seed"})
        assert await page.locator(".idea-page:not([hidden])").count() == 0                         # the drop did not open it


def _seed(stub: Stub) -> None:
    """A few ideas in several states: new, asks you, plan ready with its plan, working 2/5."""
    stub.add_idea("dark", "Dark mode", "plan", "Follow the phone's light or dark\nAnd keep the choice.")
    stub.plan({"slug": "dark"})
    stub.add_idea("export", "Export the week as a report", "asks", "A page of the week\nFor the Monday call.")
    stub.add_idea("sync", "Sync ideas between the phone and the town", "working", "Ideas follow you\nOver the paired link.")
    stub.ideas["sync"]["plan"] = {"idea": "sync", "estimate": {"tasks": 5, "usd_low": 1.2, "usd_high": 3.5}, "todos": [],
                                  "tasks": [{"id": f"k{n}", "title": t, "tier": "warrior", "after": [f"k{n - 1}"] if n > 1 else [], "state": st,
                                             "commit": "9f2c41d7e0" if st == "merged" else "", "error": ""}
                                            for n, (t, st) in enumerate([("Read the sync code", "merged"), ("Add the queue", "merged"),
                                                                         ("Retry on a lost signal", "running"), ("Test it offline", "waiting"),
                                                                         ("Write the notes", "waiting")], 1)]}
    stub.add_idea("offline", "Offline mode for the field days", "raw", "Work with no signal")
    stub.ideas["dark"]["talk"] = [{"who": "you", "text": "Does it follow the system's setting?", "section": "Risks", "at": ""},
                                  {"who": "keeper", "text": "Yes: it reads prefers-color-scheme and keeps your choice.", "section": "Risks", "at": ""}]
    stub.calls.clear()
    stub.bump()


KIT = """() => {
  const cs = (q) => getComputedStyle(document.querySelector(q));
  return { look: document.documentElement.dataset.look, pane: cs('.board .pane:not([hidden])').borderImageSource,
    bar: cs('.board-bar').borderImageSource, tab: cs('.board-tab.is-active').borderImageSource, stop: cs('.board-stop').borderImageSource,
    band: cs('.board .pane:not([hidden]) > h2').borderImageSource, head: cs('.board .pane:not([hidden]) > h2').fontFamily,
    line: cs('.need-text small').fontFamily };
}"""


@pytest.mark.asyncio
@pytest.mark.parametrize("look", ["camp", "office"])
async def test_in_camp_the_phone_board_wears_the_kit_and_in_office_it_does_not(fake_repo, monkeypatch, look):
    async with _board(fake_repo, monkeypatch, look) as (_, page):
        await page.locator(".need").first.wait_for(timeout=WAIT_MS)
        await page.wait_for_function(f"document.documentElement.dataset.look === '{look}'", timeout=WAIT_MS)
        got = await page.evaluate(KIT)
        if look == "camp":                     # the frame, the bar, the foot's tabs, the band, the teal Stop all
            assert "frame" in got["pane"] and "bar" in got["bar"] and "tab-foot-on" in got["tab"] and "btn-teal" in got["stop"]
            assert "band" in got["band"] and "Jersey 15" in got["head"] and "Jersey" not in got["line"]
        else:
            assert got["pane"] == got["bar"] == got["tab"] == got["stop"] == got["band"] == "none"
            assert "Jersey" not in got["head"]
        assert await page.evaluate("document.documentElement.scrollWidth <= 390")
        small = await page.evaluate("""() => [...document.querySelectorAll('.board button, .board input, .board textarea')]
            .filter((b) => b.offsetParent).map((b) => [b.textContent || b.getAttribute('aria-label'), b.getBoundingClientRect().height])
            .filter(([, h]) => h < 44)""")
        assert small == []


@pytest.mark.asyncio
@pytest.mark.skipif(not os.environ.get("BOARD_V4_SHOTS"), reason="the v4 shots are taken on demand")
@pytest.mark.parametrize("look", ["camp", "office"])
async def test_phone_board_v4_shots(fake_repo, monkeypatch, look):
    """docs/design/img/board-v4/phone-<look>-*.png at 390 × 844, density 2: Today, the ideas in several states, a plan
    ready opened with a section unfolded, the work at 2/5."""
    async with _board(fake_repo, monkeypatch, look) as (stub, page):
        _seed(stub)
        await page.wait_for_function(f"document.documentElement.dataset.look === '{look}'", timeout=WAIT_MS)
        await page.locator(".need").first.wait_for(timeout=WAIT_MS)
        V4_SHOTS.mkdir(parents=True, exist_ok=True)
        await page.screenshot(path=str(V4_SHOTS / f"phone-{look}-today.png"))
        await page.locator(".board-tabs").get_by_role("button", name="Ideas").click()
        await page.locator(".idea-card", has_text="Sync ideas").wait_for(timeout=WAIT_MS)
        await page.screenshot(path=str(V4_SHOTS / f"phone-{look}-ideas.png"))
        await page.locator(".idea-card", has_text="Dark mode").get_by_role("button").click()
        await page.get_by_role("button", name="Start · 2 tasks · ~$0.6–1.8").wait_for(timeout=WAIT_MS)
        await page.locator(".sec", has_text="Risks").get_by_role("button").first.click()
        await page.locator(".sec-text").first.wait_for(timeout=WAIT_MS)
        await page.screenshot(path=str(V4_SHOTS / f"phone-{look}-plan.png"))
        await page.get_by_role("button", name="Back to the board").click()
        await page.locator(".idea-card", has_text="Sync ideas").get_by_role("button").click()
        await page.get_by_role("button", name="Stop", exact=True).wait_for(timeout=WAIT_MS)
        await page.evaluate("document.querySelector('.idea-page .plan').scrollIntoView({ block: 'center' })")
        await page.screenshot(path=str(V4_SHOTS / f"phone-{look}-working.png"))
        await page.get_by_role("button", name="Back to the board").click()
        await page.locator(".board-tabs").get_by_role("button", name="Drop an idea").click()
        await page.screenshot(path=str(V4_SHOTS / f"phone-{look}-drop.png"))
