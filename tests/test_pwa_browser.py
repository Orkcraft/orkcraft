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
        summary = page.locator(".answers .summary")
        await summary.wait_for(timeout=WAIT_MS)
        assert (await summary.inner_text()) == "No ork is waiting on you."
        await page.locator(".dock").get_by_role("button", name="More").click()
        small = await page.evaluate("""() => [...document.querySelectorAll('button')]
            .filter((b) => b.offsetParent && b.getBoundingClientRect().height < 44).map((b) => b.textContent)""")
        assert small == []
