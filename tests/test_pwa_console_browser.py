"""The phone as the console, in Chromium at 390 px (docs/design/mobile.md §11–§12): it opens on "since your last
look" over the living camp in v3 with the camera on what waits; an ork's question is answered in one tap, and kept
with no signal; an idea is dropped into the Task board's Ideas lane; 🥩 opens the orks at work with Stop all; the art
at a whole number of device pixels, the signals and taps a finger's size; a first tap is the scroll and the quick
actions, a second the building's sheet; a steward's tap its console, a cart's its history; the carts stop rolling
while the page is hidden."""
from __future__ import annotations

import pytest

pytest.importorskip("playwright.async_api")

from orkcraft.core import buildings  # noqa: E402
from tests.test_pwa_browser import WAIT_MS, _flash, _phone  # noqa: E402


def _dressed(server, asks: str = "", working: str = "", digest: dict | None = None):
    """The town's snapshot as if `asks` (a building id) had an Agent pool ork's question and `working` were at work;
    the phone's greeting `digest`."""
    host = server.host
    real = host.snapshot

    def snapshot():
        s = real()
        for b in s["buildings"]:
            if b["id"] == asks:
                b["state"] = "ASKS"
            if b["id"] == working:
                b["state"] = "WORKING"
        rows = []
        if asks:
            rows.append({"key": f"{asks}/grunt", "name": "Grunt", "state": "asks", "mark": "❓", "word": "Asks",
                         "line": "Grunt asks · «Dark mode»", "building_id": asks, "since_s": 120, "spend": 0.4,
                         "tool": "claude", "cart": "Dark mode", "assumptions": 1,
                         "wait": {"line": "waits for your answer"}, "stop": None,
                         "answer": {"kind": "pool", "building": asks, "task": "t1", "question": "",
                                    "questions": [{"text": "System or switch?", "options": ["System", "Switch"]}]}})
        s["slots"] = {"working": 1 if working else 0, "limit": 4, "asks": 1 if asks else 0, "fire": 0, "rows": rows}
        return s
    host.snapshot = snapshot
    if digest is not None:
        host.last_look.snapshot = lambda now=None, face="gui": digest if face == "phone" else None
    if asks or working:                       # the town changes, so the phone gets the dressed snapshot now
        host.command("hut.move", {"id": asks or working, "x": 0.5, "y": 0.5})


def _raise(server, kind: str, spot=None) -> str:
    host = server.host
    bid = buildings.raise_spec(host.town, buildings.type_spec(host.town, kind)).id
    host._attach(bid, host.town.worker(bid))
    if spot:
        host.command("hut.move", {"id": bid, "x": spot[0], "y": spot[1]})
    return bid


DIGEST = {"since": "", "at": "12:40", "away": "5 h", "empty": False, "headline": "Since 12:40: 1 launched, 1 question.",
          "working": "the orks rest", "built": {"items": [{"kind": "launched", "building": "", "line": "Launched: «v0.4»"}],
                                                "more": 0, "summary": "", "moved": 0},
          "questions": {"items": [{"id": "x", "new": True}], "more": 0}, "problems": {"items": [], "more": 0},
          "cost": [], "cost_known": False}


@pytest.mark.asyncio
async def test_it_opens_on_since_your_last_look_over_the_camp_with_the_camera_on_what_waits(fake_repo):
    async with _phone(fake_repo) as (server, page):
        _raise(server, "pit", (0.0, 0.0))
        for kind, spot in (("signpost", (0.3, 0.0)), ("mill", (0.6, 0.0)), ("horn", (0.0, 0.5)), ("scrolls", (0.3, 0.5)),
                           ("mine", (0.6, 0.5)), ("crag", (0.0, 1.0)), ("forge", (0.3, 1.0)), ("council", (0.6, 1.0))):
            _raise(server, kind, spot)
        far = _raise(server, "catapult")
        _dressed(server, asks=far, digest=DIGEST)
        server.host.command("hut.move", {"id": far, "x": 1.0, "y": 1.0})
        look = page.locator("section.look")
        await look.get_by_text("Since 12:40: 1 launched, 1 question.").wait_for(timeout=WAIT_MS)
        assert "Launched: «v0.4»" in await look.inner_text()
        hut = page.locator(f".camp-hut[data-b='{far}']")
        await hut.wait_for(timeout=WAIT_MS)
        await page.wait_for_function(f"() => document.querySelector('.camp').dataset.focus === '{far}'", timeout=WAIT_MS)
        await page.wait_for_timeout(300)
        # the camera went to it: the building that asks stands inside the camp's view
        inside = await page.evaluate(f"""() => {{
          const v = document.querySelector('.camp-view').getBoundingClientRect();
          const b = document.querySelector(".camp-hut[data-b='{far}']").getBoundingClientRect();
          return b.left >= v.left - 1 && b.right <= v.right + 1 && b.top >= v.top - 1 && b.bottom <= v.bottom + 1; }}""")
        assert inside
        sizes = await page.evaluate(f"""() => {{
          const sig = document.querySelector(".camp-hut[data-b='{far}'] .camp-sig").getBoundingClientRect();
          const hut = document.querySelector(".camp-hut[data-b='{far}']").getBoundingClientRect();
          const art = document.querySelector(".camp-hut[data-b='{far}'] .camp-sprite");
          return [sig.height, hut.width, hut.height, art.getBoundingClientRect().width, art.naturalWidth,
                  getComputedStyle(art).imageRendering]; }}""")
        assert sizes[0] >= 24 and sizes[1] >= 44 and sizes[2] >= 44     # ❓ a finger can see and hit
        assert sizes[3] == sizes[4] and sizes[5] == "pixelated"           # the art at its own pixel (×1 on a 1× screen)
        assert await page.evaluate("document.scrollingElement.scrollWidth") <= 390   # the page never scrolls sideways
        await look.get_by_role("button", name="Back to the camp").click()
        await look.wait_for(state="hidden", timeout=WAIT_MS)


@pytest.mark.asyncio
async def test_nothing_waits_the_camera_is_on_the_work_a_tap_shows_its_scroll_and_a_second_its_sheet(fake_repo):
    async with _phone(fake_repo) as (server, page):
        pit = _raise(server, "pit", (0.1, 0.2))
        _raise(server, "fields", (0.8, 0.8))
        hut = page.locator(f".camp-hut[data-b='{pit}']")
        await hut.wait_for(timeout=WAIT_MS)
        assert await page.evaluate("document.querySelector('.camp').dataset.focus") == ""
        inside = await page.evaluate(f"""() => {{ const v = document.querySelector('.camp-view').getBoundingClientRect();
          const b = document.querySelector(".camp-hut[data-b='{pit}']").getBoundingClientRect();
          return b.right > v.left && b.left < v.right && b.bottom > v.top && b.top < v.bottom; }}""")
        assert inside                                                # the work's start in view, nothing squeezed
        await hut.evaluate("e => e.click()")                         # a first tap: its scroll, its quick actions
        scroll = page.locator(f".camp-scroll[data-b='{pit}']")
        await scroll.wait_for(timeout=WAIT_MS)
        assert await scroll.get_by_role("button", name="Open").count() == 1
        assert await page.locator("dialog.sheet[open]").count() == 0
        await page.locator(f".camp-hut[data-b='{pit}']").evaluate("e => e.click()")   # a second: its card as a sheet
        sheet = page.locator("dialog.sheet[open]")
        await sheet.wait_for(timeout=WAIT_MS)
        assert await sheet.locator(".info-mark img.mark-sprite").count() == 1     # headed by its mark


@pytest.mark.asyncio
async def test_an_orks_question_is_answered_in_one_tap_with_its_pinned_context(fake_repo):
    async with _phone(fake_repo) as (server, page):
        pool = _raise(server, "barracks")
        sent = []
        server.host.commands["act"] = (lambda real: lambda a: (sent.append(a), "")[1] if a.get("act") == "answer"
                                       else real(a))(server.host.commands["act"])
        import orkcraft.gui.mobile as mobile
        real_allowed = mobile._pool_question
        mobile._pool_question = lambda host, bid, args: (args or {}).get("task") == "t1"
        try:
            _dressed(server, asks=pool)
            q = page.locator(".asking .question.pool")
            await q.wait_for(timeout=WAIT_MS)
            assert "On: Dark mode" in await q.inner_text() and "System or switch?" in await q.inner_text()
            await q.get_by_role("button", name="System").click()
            await page.locator(".asking .done", has_text="Answered: System. The ork goes on.").wait_for(timeout=WAIT_MS)
            assert sent == [{"id": pool, "act": "answer", "args": {"task": "t1", "text": "System"}}]
            # the camp's building opens to the same question: home screen to answer in two taps
            await page.locator(f".camp-hut[data-b='{pool}'] .camp-sig").wait_for(timeout=WAIT_MS)
        finally:
            mobile._pool_question = real_allowed


@pytest.mark.asyncio
async def test_an_idea_drops_into_the_task_boards_ideas_lane(fake_repo):
    async with _phone(fake_repo) as (server, page):
        board = _raise(server, "fields")
        idea = page.locator(".dock .idea")
        await idea.wait_for(timeout=WAIT_MS)
        await idea.click()
        await page.locator("#idea").fill("A recap in one line")
        assert "Ideas" in await page.locator("dialog.sheet[open] .hint").inner_text()
        await page.get_by_role("button", name="Drop it").click()
        await _flash(page, "Idea dropped into")
        w = server.host.town.worker(board)
        lane = w.note_lanes()[0]
        assert [c.column for c in w.cards if "recap" in (c.title + c.body).lower()] == [lane]


@pytest.mark.asyncio
async def test_meat_opens_the_orks_at_work_with_stop_all_first(fake_repo):
    async with _phone(fake_repo) as (server, page):
        pool = _raise(server, "barracks")
        _dressed(server, asks=pool)
        await page.locator(".head .meat").click()
        sheet = page.locator("dialog.sheet[open]", has_text="Orks at work")
        await sheet.wait_for(timeout=WAIT_MS)
        await sheet.get_by_text("its question waits in Answers").wait_for(timeout=WAIT_MS)
        halts = []
        server.host.commands["halt"] = lambda a: (halts.append(1), 0)[1]
        stop = sheet.get_by_role("button", name="Stop all")
        await stop.click()
        assert halts == []                                           # a first tap only arms it
        await sheet.get_by_role("button", name="Stop every ork").click()
        await _flash(page, "Stopped")
        assert halts == [1]


@pytest.mark.asyncio
async def test_what_was_given_with_no_signal_is_sent_when_the_town_answers(fake_repo):
    async with _phone(fake_repo) as (server, page):
        answered = []
        server.host.commands["orders.answer"] = lambda a: (answered.append(a), True)[1]
        await page.evaluate("""() => localStorage.setItem('orkcraft.outbox', JSON.stringify([
          { key: 'k1', name: 'orders.answer', args: { id: 'q1', key: 'y' }, label: 'Grunt: Yes', at: 0 }]))""")
        await page.reload()
        await _flash(page, "Sent: Grunt: Yes")
        assert answered == [{"id": "q1", "key": "y"}]
        assert await page.evaluate("JSON.parse(localStorage.getItem('orkcraft.outbox'))") == []


@pytest.mark.asyncio
async def test_a_working_buildings_steward_thinks_over_its_roof_and_a_tap_opens_its_console(fake_repo):
    async with _phone(fake_repo) as (server, page):
        board = _raise(server, "fields")
        _dressed(server, working=board)
        bubble = page.locator(".camp-bubble")
        await bubble.wait_for(timeout=WAIT_MS)
        await bubble.evaluate("e => e.click()")                     # its steward's console, as a sheet from the foot
        sheet = page.locator("dialog.sheet[open]", has_text="Taskmaster")
        await sheet.wait_for(timeout=WAIT_MS)
        await sheet.get_by_text("terminal to show").wait_for(timeout=WAIT_MS)   # what is not known, said plainly
        await page.evaluate("""() => { Object.defineProperty(document, 'visibilityState', { value: 'hidden', configurable: true });
          document.dispatchEvent(new Event('visibilitychange')); }""")
        assert await page.evaluate("document.querySelector('.camp').classList.contains('is-hidden')")   # carts paused
