"""The app in a phone's browser (gui/static/pwa/), in Chromium at a phone's size: paired from the desktop's
link, over the phone listener, against a real host. What a person sees and taps: the questions first, the bar
at the foot (Ask, Drop, More, Stop all on a hold), the look, the version."""
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

import pytest

pw = pytest.importorskip("playwright.async_api")

from orkcraft import __version__  # noqa: E402
from tests.test_phones import _listening, _serve  # noqa: E402

CHROMIUM = next((p for p in ("/opt/pw-browsers/chromium",) if Path(p).exists()), None)
WAIT_MS = 10_000


@asynccontextmanager
async def _phone(repo: Path, scheme: str = "dark"):
    """A paired phone's page on the town of `repo`: (server, page)."""
    server, task = await _serve(repo)
    try:
        offer = server.host.command("phones.pair")
        await _listening(server)
        async with pw.async_playwright() as p:
            try:
                browser = await (p.chromium.launch(executable_path=CHROMIUM) if CHROMIUM else p.chromium.launch())
            except Exception as e:                         # noqa: BLE001 — no browser here
                pytest.skip(f"no Chromium for Playwright here: {e}")
            try:
                ctx = await browser.new_context(viewport={"width": 390, "height": 844}, ignore_https_errors=True,
                                                has_touch=True, color_scheme=scheme)
                page = await ctx.new_page()
                await page.goto(f"{server.phones.address}/app/#pair={offer['code']}")
                await page.locator(".dock").wait_for(timeout=WAIT_MS)
                yield server, page
            finally:
                await browser.close()
    finally:
        server.stop()
        await asyncio.wait_for(task, 10)


async def _flash(page, text: str) -> None:
    await page.locator(".flash", has_text=text).wait_for(timeout=WAIT_MS)


@pytest.mark.asyncio
async def test_the_app_pairs_from_its_link_and_says_the_towns_version(fake_repo):
    """Opened from the desktop's link the app pairs, connects and says, quietly by the phone's name, the version
    of Orkcraft the town runs (`mobile.hello`): at the page's foot and in More."""
    async with _phone(fake_repo) as (_, page):
        foot = page.locator("p.foot")
        await foot.get_by_text(f"Orkcraft {__version__}").wait_for(timeout=WAIT_MS)
        assert "This phone: " in await foot.inner_text()
        await page.locator(".dock").get_by_role("button", name="More").click()
        more = page.locator("dialog.sheet[open]")
        assert f"Orkcraft {__version__}" in await more.inner_text()
        assert await more.get_by_role("button", name="Camp").count() == 1


@pytest.mark.asyncio
async def test_stop_all_stops_on_a_hold_or_a_tap_and_a_confirm_never_on_a_tap(fake_repo):
    async with _phone(fake_repo) as (server, page):
        halts = []
        real = server.host.commands["halt"]
        server.host.commands["halt"] = lambda a: (halts.append(1), real(a))[1]
        stop = page.locator(".dock .stop")
        await stop.click()                                  # a tap asks first
        sheet = page.locator("dialog.sheet[open]", has_text="Stop every ork")
        await sheet.wait_for(timeout=WAIT_MS)
        assert halts == []
        await sheet.get_by_role("button", name="Close").click()
        await sheet.wait_for(state="hidden", timeout=WAIT_MS)
        assert halts == []
        await stop.click()
        await sheet.get_by_role("button", name="Stop every ork").click()
        await _flash(page, "Stopped:")
        assert halts == [1]
        box = await stop.bounding_box()                     # held: it stops without asking
        await page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
        await page.mouse.down()
        await page.wait_for_timeout(1500)
        await page.mouse.up()
        for _ in range(50):
            if len(halts) == 2:
                break
            await page.wait_for_timeout(100)
        assert halts == [1, 1] and await page.locator("dialog.sheet[open]").count() == 0
        await page.mouse.down()                             # let go early: nothing
        await page.wait_for_timeout(300)
        await page.mouse.up()
        await page.locator("dialog.sheet[open]", has_text="Stop every ork").wait_for(timeout=WAIT_MS)
        assert halts == [1, 1]


@pytest.mark.asyncio
async def test_office_in_light_paints_the_systems_bar_light_and_camp_stays_dark(fake_repo):
    async with _phone(fake_repo, scheme="light") as (server, page):
        color = "() => document.querySelector('meta[name=theme-color]').content"
        server.host.command("you.look", {"look": "office"})
        await page.wait_for_function("() => document.documentElement.dataset.look === 'office'", timeout=WAIT_MS)
        assert await page.evaluate(color) == "#f4f4f4"
        server.host.command("you.look", {"look": "camp"})
        await page.wait_for_function("() => document.documentElement.dataset.look === 'camp'", timeout=WAIT_MS)
        assert await page.evaluate(color) == "#172a0a"


@pytest.mark.asyncio
async def test_the_questions_come_first_and_every_target_is_a_thumbs_size(fake_repo):
    async with _phone(fake_repo) as (_, page):
        summary = page.locator(".asking .summary")
        await summary.wait_for(timeout=WAIT_MS)
        assert (await summary.inner_text()) == "No ork is waiting on you."
        await page.locator(".dock").get_by_role("button", name="More").click()
        small = await page.evaluate("""() => [...document.querySelectorAll('button')]
            .filter((b) => b.offsetParent && b.getBoundingClientRect().height < 44).map((b) => b.textContent)""")
        assert small == []


@pytest.mark.asyncio
async def test_the_quiet_buildings_stand_as_a_grid_of_marks_and_a_tap_says_what_one_does(fake_repo):
    async with _phone(fake_repo) as (server, page):
        bid = server.host.command("town.build", {"type": "pit"})
        title = server.host.command("mobile.snapshot")["buildings"]
        title = next(b["title"] for b in title if b["id"] == bid)
        cell = page.locator(".grid .cell", has_text=title)
        await cell.wait_for(timeout=WAIT_MS)
        assert await cell.locator("img.mark-sprite").get_attribute("src") == "sprites/pit.png"     # Camp: the sprite
        await cell.click()
        info = page.locator("dialog.sheet[open]")
        await info.wait_for(timeout=WAIT_MS)
        assert await info.locator("h2").text_content() == title and "Quiet" in await info.inner_text()
        await info.get_by_role("button", name="Close").click()
        server.host.command("you.look", {"look": "office"})
        await page.locator(".grid .cell svg.mark-line").first.wait_for(timeout=WAIT_MS)       # Office: the line icon


@pytest.mark.asyncio
async def test_what_asks_stands_as_tiles_one_open_the_longest_waiting_first(fake_repo):
    """The tiles (town.js) on a town of three questions: two of one building, one of no building the phone
    knows; the longest waiting opens, a tap opens another and closes it, and a tile of one building's question
    says who asks once."""
    async with _phone(fake_repo) as (_, page):
        await page.evaluate("""async () => {
          const { makeTown } = await import('/app/town.js');
          const q = (id, who, waited, building) => ({ id, who, waited, building, title: `Proceed ${id}?`,
            options: [['y', 'Yes'], ['n', 'No']], context: ['line'] });
          const s = { look: 'camp', buildings: [
              { id: 'b1', title: 'The Forge', type: 'forge', state: 'ASKS', alert: 'q1' },
              { id: 'b2', title: 'Inbox', type: 'watchtower', state: 'ERROR' },
              { id: 'b3', title: 'Notes', type: 'fields', state: '' }],
            alerts: [q('q1', 'Grunt', 30, 'b1'), q('q2', 'Peon', 900, ''), q('q3', 'Grunt', 20, 'b1')] };
          const view = makeTown({ send: async () => ({ ok: true }), rerender: () => view.render(s) });
          const box = document.createElement('div'); box.id = 'probe';
          box.append(...view.parts); document.body.replaceChildren(box); view.render(s);
        }""")
        tiles = page.locator("#probe .tile")
        assert await tiles.count() == 2
        assert await page.locator("#probe .tile.is-open").count() == 1
        first = tiles.nth(0)
        assert "Peon" in await first.inner_text() and "15 min" in await first.inner_text()      # the longest wait
        assert await page.locator("#probe .summary.long").count() == 1
        await tiles.nth(1).locator(".tile-head").click()
        assert await page.locator("#probe .tile.is-open").count() == 1
        forge = page.locator("#probe .tile.is-open")
        assert "The Forge" in await forge.inner_text() and await forge.locator(".question").count() == 2
        assert await page.locator("#probe .rows .row-b.trouble", has_text="Inbox").count() == 1
        assert await page.locator("#probe .grid .cell", has_text="Notes").count() == 1


@pytest.mark.asyncio
async def test_task_fields_stands_open_and_takes_a_to_do_written_on_the_phone(fake_repo):
    async with _phone(fake_repo) as (server, page):
        server.host.command("town.build", {"type": "fields"})
        widget = page.locator(".widget")
        await widget.locator("h3", has_text="My to-dos 0/0").wait_for(timeout=WAIT_MS)
        await widget.get_by_role("button", name="+ To-do").click()
        write = page.locator("dialog.sheet[open]")
        assert "A to-do is yours: it starts nothing." in await write.inner_text()
        await write.locator("textarea").fill("Buy milk")
        await write.get_by_role("button", name="Add").click()
        await _flash(page, "To-do added.")
        await widget.locator("li", has_text="Buy milk").wait_for(timeout=WAIT_MS)
        await widget.get_by_role("button", name="+ Task").click()
        assert "The task waits in To Do for an ork to take it." in await page.locator("dialog.sheet[open]").inner_text()
        await page.locator("dialog.sheet[open]").get_by_role("button", name="Close").click()
        assert await widget.locator(".w-lanes").count() == 0                     # the orks' lanes: a tap away
        await widget.locator(".w-work").click()
        assert await widget.locator(".w-work").get_attribute("aria-expanded") == "true"
