"""The app in a phone's browser (gui/static/pwa/), in Chromium at a phone's size: paired from the desktop's
link, over the phone listener, against a real host. What a person sees and taps: the questions first, the bar
at the foot (Ask, Drop, Stop all on a hold while orks work), a building's quick actions, the orkspaces, the look,
the version."""
from __future__ import annotations

import asyncio
import base64
import hashlib
import re
import struct
import zlib
from contextlib import asynccontextmanager
from pathlib import Path

import pytest

pw = pytest.importorskip("playwright.async_api")

from orkcraft import __version__  # noqa: E402
from orkcraft.gui import phone_http, phone_tls, pwa  # noqa: E402
from tests.test_phones import _listening, _serve  # noqa: E402

CHROMIUM = next((p for p in ("/opt/pw-browsers/chromium",) if Path(p).exists()), None)
WAIT_MS = 10_000


def _spki(cert: Path) -> str:
    """The certificate's public key as Chromium names one it trusts: base64 of the SPKI's sha256."""
    from cryptography import x509
    from cryptography.hazmat.primitives import serialization
    key = x509.load_pem_x509_certificate(cert.read_bytes()).public_key()
    der = key.public_bytes(serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo)
    return base64.b64encode(hashlib.sha256(der).digest()).decode()


@asynccontextmanager
async def _phone(repo: Path, scheme: str = "dark", trusted: bool = False):
    """A paired phone's page on the town of `repo`: (server, page). `trusted`: the browser trusts the listener's
    certificate as a phone trusts a *.ts.net one, so its HTTP cache keeps what it gets (it keeps nothing from a
    certificate it only ignores the errors of)."""
    server, task = await _serve(repo)
    try:
        offer = server.host.command("phones.pair")
        await _listening(server)
        async with pw.async_playwright() as p:
            flags = [f"--ignore-certificate-errors-spki-list={_spki(phone_tls.paths(server.phones.cert_folder)[0])}"] \
                if trusted else []
            try:
                browser = await (p.chromium.launch(executable_path=CHROMIUM, args=flags) if CHROMIUM
                                 else p.chromium.launch(args=flags))
            except Exception as e:                         # noqa: BLE001 — no browser here
                pytest.skip(f"no Chromium for Playwright here: {e}")
            try:
                ctx = await browser.new_context(viewport={"width": 390, "height": 844}, ignore_https_errors=not trusted,
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


def _working(server, n: int = 2) -> None:
    """The town as if `n` orks were at work (the fake repo has none): its snapshot says so from now on."""
    real = server.host.snapshot

    def snapshot():
        s = real()
        s["hud"] = {**s["hud"], "agents_working": n, "agents": max(n, s["hud"].get("agents") or 0)}
        return s
    server.host.snapshot = snapshot


@pytest.mark.asyncio
async def test_the_app_pairs_from_its_link_and_says_the_towns_version(fake_repo):
    """Opened from the desktop's link the app pairs, connects and says, quietly by the phone's name, the version
    of Orkline the town runs (`mobile.hello`), at the page's foot, with the look and Unpair here: no More."""
    async with _phone(fake_repo) as (_, page):
        foot = page.locator("p.foot")
        await foot.get_by_text(f"Orkline {__version__}").wait_for(timeout=WAIT_MS)
        assert "This phone: " in await foot.inner_text()
        phone = page.locator("section.phone")
        assert await phone.get_by_role("button", name="Camp").count() == 1
        assert await phone.get_by_role("button", name="Unpair here").count() == 1
        assert await page.locator(".dock").get_by_role("button", name="More").count() == 0


@pytest.mark.asyncio
async def test_stop_all_stops_on_a_hold_or_a_tap_and_a_confirm_never_on_a_tap(fake_repo):
    async with _phone(fake_repo) as (server, page):
        stop = page.locator(".dock .stop")
        await page.locator(".head .ok-res").first.wait_for(timeout=WAIT_MS)
        assert not await stop.is_visible()                  # no ork works: nothing to stop
        _working(server)
        await stop.wait_for(timeout=WAIT_MS)
        halts = []
        real = server.host.commands["halt"]
        server.host.commands["halt"] = lambda a: (halts.append(1), real(a))[1]
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
async def test_office_in_light_paints_the_systems_bar_light_and_camp_its_orkspaces_ground(fake_repo):
    async with _phone(fake_repo, scheme="light") as (server, page):
        color = "() => document.querySelector('meta[name=theme-color]').content"
        server.host.command("you.look", {"look": "office"})
        await page.wait_for_function("() => document.documentElement.dataset.theme === 'office'", timeout=WAIT_MS)
        assert await page.evaluate(color) == "#f4f4f4"
        server.host.command("orkspace.new", {"name": "Lab", "biome": "ice"})    # the town goes to it
        server.host.command("you.look", {"look": "camp"})
        await page.wait_for_function("() => document.documentElement.dataset.theme === 'camp'", timeout=WAIT_MS)
        await page.wait_for_function(f"() => ({color})() === '#070d14'", timeout=WAIT_MS)      # ice's ground
        assert await page.evaluate("getComputedStyle(document.body).backgroundColor") == "rgb(7, 13, 20)"


@pytest.mark.asyncio
async def test_no_answers_while_nobody_asks_and_every_target_is_a_thumbs_size(fake_repo):
    async with _phone(fake_repo) as (_, page):
        await page.locator(".head .ok-res").first.wait_for(timeout=WAIT_MS)
        assert not await page.locator(".asking").is_visible()       # nobody asks: no Answers at all
        buttons = await page.evaluate("""() => [...document.querySelectorAll('button')].filter((b) => b.offsetParent)
            .map((b) => [b.textContent, b.getBoundingClientRect().height, b.className])""")
        assert buttons and [b[0] for b in buttons if b[1] < 44] == []
        # the design system's, but for the map's own pieces: a building on the camp, a cell, 🥩 in the head
        assert [b[0] for b in buttons if "ok-" not in b[2] and b[2].split()[0] not in ("cell", "w-work", "tile-head", "camp-hut", "camp-ork", "camp-cart", "camp-bubble", "meat")] == []


@pytest.mark.asyncio
async def test_the_quiet_buildings_stand_as_a_grid_of_marks_and_a_tap_says_what_one_does(fake_repo):
    async with _phone(fake_repo) as (server, page):
        bid = server.host.command("town.build", {"type": "pit"})
        title = server.host.command("mobile.snapshot")["buildings"]
        title = next(b["title_plain"] for b in title if b["id"] == bid)      # today's word, in either look
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


@pytest.mark.asyncio
async def test_the_grid_stands_in_chains_as_the_work_flows(fake_repo):
    async with _phone(fake_repo) as (_, page):
        groups = await page.evaluate("""async () => {
          const { chains } = await import('/app/links.js');
          return chains(['x', 'c', 'b', 'a', 'd', 'e', 'f'],
            [['a', 'b'], ['b', 'c'], ['a', 'c'], ['d', 'e'], ['e', 'd']]);
        }""")
        assert groups == [{"linked": True, "ids": ["a", "b", "c"]},          # sources first, then as the work flows
                          {"linked": True, "ids": ["d", "e"]},               # a loop keeps the town's order
                          {"linked": False, "ids": ["x", "f"]}]


@pytest.mark.asyncio
async def test_a_long_press_lights_a_buildings_neighbours_and_a_tap_names_them(fake_repo):
    async with _phone(fake_repo) as (_, page):
        await page.evaluate("""async () => {
          const { makeTown } = await import('/app/town.js');
          const b = (id, title) => ({ id, title, type: 'pit', state: '' });
          const s = { look: 'office', alerts: [], roads: [['in', 'mid'], ['mid', 'out']],
            buildings: [b('in', 'Inbox'), b('mid', 'Triage'), b('out', 'Replies'), b('far', 'Notes')] };
          const view = makeTown({ send: async () => ({ ok: true }), rerender: () => view.render(s) });
          const box = document.createElement('div'); box.id = 'probe';
          box.append(...view.parts); document.body.replaceChildren(box); view.render(s);
        }""")
        names = await page.locator("#probe .grid.linked .cell-name").all_inner_texts()
        assert names == ["Inbox", "Triage", "Replies"]
        assert await page.locator("#probe .grid.linked li.fed").count() == 2
        cell = page.locator("#probe .cell", has_text="Triage")
        box = await cell.bounding_box()
        await page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
        await page.mouse.down()
        await page.wait_for_timeout(700)
        assert await page.evaluate("document.documentElement.classList.contains('lighting')")
        near = await page.evaluate("[...document.querySelectorAll('.blocks .is-near')].map((e) => e.textContent)")
        assert sorted(near) == ["Inbox", "Replies"]
        assert "Takes from: Inbox · Sends to: Replies" in await page.locator("#probe .lit").inner_text()
        await page.mouse.up()
        assert not await page.evaluate("document.documentElement.classList.contains('lighting')")
        assert await page.locator("dialog.sheet[open]").count() == 0                  # a press opens no sheet
        await cell.click()
        info = page.locator("dialog.sheet[open]")
        await info.wait_for(timeout=WAIT_MS)
        text = await info.inner_text()
        assert "Takes from: Inbox" in text and "Sends to: Replies" in text


@pytest.mark.asyncio
async def test_away_from_the_town_the_phone_shows_the_last_town_greyed_and_as_of(fake_repo):
    """Opened where the town does not answer (here: a token it never gave), the app shows the town it kept,
    greyed and dated, with how many orks wait in its title, and acts on none of it but Answers: an answer given
    there is kept on the phone and sent when the town answers again (audience.md §2a). The page's foot stays."""
    import json
    async with _phone(fake_repo) as (server, page):
        state = {"look": "camp", "project": "kept town", "hud": {}, "roads": [], "widget": None,
                 "buildings": [{"id": "p", "title": "The Pit", "type": "pit", "state": ""}],
                 "alerts": [{"id": "q", "who": "Grunt", "title": "Proceed?", "options": [["y", "Yes"]], "waited": 5}]}
        ctx = page.context
        away = await ctx.new_page()
        await away.add_init_script(f"""localStorage.setItem('orkcraft.device', JSON.stringify({{ token: '{"x" * 43}', name: 'Phone' }}));
            localStorage.setItem('orkcraft.town', {json.dumps(json.dumps({"at": 0, "state": state}))});""")
        await away.goto(f"{server.phones.address}/app/")
        await away.wait_for_function("() => document.documentElement.classList.contains('offline')", timeout=WAIT_MS)
        assert "As of " in await away.locator(".status").inner_text()
        assert await away.title() == "(1) Orkline"
        assert await away.locator(".head h1", has_text="kept town").count() == 1
        assert await away.evaluate("document.querySelector('.camp').inert") is True
        assert await away.evaluate("document.querySelector('.asking').inert") is False
        assert await away.evaluate("document.querySelector('section.phone').inert") is False   # Unpair here stays
        await away.locator(".asking .question").get_by_role("button", name="Yes").click()
        await away.locator(".asking .warn", has_text="Kept: Yes. It is sent when the signal returns.").wait_for(timeout=WAIT_MS)
        kept = await away.evaluate("JSON.parse(localStorage.getItem('orkcraft.outbox'))")
        assert [(k["name"], k["args"]) for k in kept] == [("orders.answer", {"id": "q", "key": "y"})]


@pytest.mark.asyncio
async def test_an_answer_is_said_at_once_and_the_tile_says_the_ork_goes_on(fake_repo):
    async with _phone(fake_repo) as (_, page):
        await page.evaluate("""async () => {
          const { makeTown } = await import('/app/town.js');
          const s = { look: 'office', roads: [], buildings: [],
            alerts: [{ id: 'q9', who: 'Grunt', title: 'Proceed?', options: [['y', 'Yes'], ['n', 'No']], waited: 3 }] };
          window.flashed = [];
          const view = makeTown({ send: async () => ({ ok: true, result: true }), flash: (t) => window.flashed.push(t),
            rerender: () => view.render(s) });
          const box = document.createElement('div'); box.id = 'probe';
          box.append(...view.parts); document.body.replaceChildren(box); view.render(s);
        }""")
        await page.locator("#probe .question").get_by_role("button", name="Yes").click()
        await page.locator("#probe .done", has_text="Answered: Yes. The ork goes on.").wait_for(timeout=WAIT_MS)
        assert await page.evaluate("window.flashed") == ["Answered: Yes"]


@pytest.mark.asyncio
async def test_a_task_written_on_the_phone_leaves_its_trail_on_the_widget(fake_repo):
    async with _phone(fake_repo) as (server, page):
        server.host.command("town.build", {"type": "fields"})
        widget = page.locator(".widget")
        await widget.get_by_role("button", name="+ Task").wait_for(timeout=WAIT_MS)
        await widget.get_by_role("button", name="+ Task").click()
        write = page.locator("dialog.sheet[open]")
        await write.locator("textarea").fill("Renew the domain")
        await write.get_by_role("button", name="Add").click()
        trail = widget.locator("ol.trail")
        await trail.wait_for(timeout=WAIT_MS)
        text = await trail.inner_text()
        assert "Task added: Renew the domain" in text and "It waits in To Do for an ork." in text


@pytest.mark.asyncio
async def test_a_buildings_sheet_presses_its_quick_actions(fake_repo):
    """A tap on a building opens its sheet with the quick actions its card has: one that does a thing at once is
    pressed on a tap, one that reaches out asks once more, and one that takes text asks for it."""
    async with _phone(fake_repo) as (server, page):
        pressed = []
        server.host.commands["building.input"] = lambda a: (pressed.append((a["input"], a.get("value", ""))), True)[1]
        cat = server.host.command("town.build", {"type": "catapult"})
        title = next(b["title_plain"] for b in server.host.command("mobile.snapshot")["buildings"] if b["id"] == cat)
        await page.locator(".grid .cell", has_text=title).click()
        sheet = page.locator("dialog.sheet[open]")
        await sheet.get_by_role("button", name="Fire").click()
        assert pressed == []                                                    # it reaches out: asked first
        await sheet.locator(".q-form").get_by_role("button", name="Fire").wait_for(timeout=WAIT_MS)
        await sheet.get_by_role("button", name="Cancel").click()
        await sheet.get_by_role("button", name="Close").click()
        wiki = server.host.command("town.build", {"type": "scrolls"})
        title = next(b["title_plain"] for b in server.host.command("mobile.snapshot")["buildings"] if b["id"] == wiki)
        await page.locator(".row-b, .cell", has_text=title).click()           # a row while it has no wiki yet
        await sheet.get_by_role("button", name="Quick note").click()
        await sheet.locator(".q-form textarea").fill("Fix the login page")
        await sheet.locator(".q-form").get_by_role("button", name="Quick note").click()
        for _ in range(50):
            if pressed:
                break
            await page.wait_for_timeout(100)
        assert pressed == [("wiki.note", "Fix the login page")]
        await sheet.locator(".done", has_text="Quick note: done.").wait_for(timeout=WAIT_MS)


@pytest.mark.asyncio
async def test_the_phone_shows_one_orkspace_at_a_time_without_moving_the_desktops(fake_repo):
    """A town of two orkspaces: the phone shows the desktop's open one, its tabs pick another for the phone only,
    and the questions stay the whole town's."""
    async with _phone(fake_repo) as (server, page):
        pit = server.host.command("town.build", {"type": "pit"})
        first = server.host.command("mobile.snapshot")["active_orkspace"]
        server.host.command("orkspace.new", {"name": "Lab", "biome": "ice"})
        lab = server.host.command("mobile.snapshot")["active_orkspace"]
        server.host.command("orkspace.select", {"id": first})
        title = next(b["title_plain"] for b in server.host.command("mobile.snapshot")["buildings"] if b["id"] == pit)
        tabs = page.locator(".spaces .ok-tab")
        await tabs.nth(1).wait_for(timeout=WAIT_MS)
        assert await page.locator(".spaces .ok-tab.is-active").inner_text() != "Lab"
        await page.locator(".grid .cell", has_text=title).wait_for(timeout=WAIT_MS)
        await page.locator(".spaces .ok-tab", has_text="Lab").click()
        await page.locator(".grid .cell", has_text=title).wait_for(state="detached", timeout=WAIT_MS)
        assert await page.evaluate("document.querySelector('meta[name=theme-color]').content") == "#070d14"
        assert server.host.command("mobile.snapshot")["active_orkspace"] == first != lab     # the desktop's stays


def _png(width: int) -> bytes:
    """A PNG `width` pixels wide and one high: what it draws says which bytes the page got."""
    def chunk(kind: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))
    rows = (b"\x00" + b"\x80\x40\x20\xff" * width)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, 1, 8, 6, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(rows)) + chunk(b"IEND", b""))


CACHE = re.search(r'const CACHE = "([^"]+)"', (pwa.ROOT / "sw.js").read_text(encoding="utf-8")).group(1)


async def _until(page, script: str, arg, what: str, seconds: float = 60) -> None:
    """Poll an async `script` in the page until it is true."""
    for _ in range(int(seconds * 10)):
        if await page.evaluate(script, arg):
            return
        await page.wait_for_timeout(100)
    pytest.fail(f"never: {what}")


@pytest.mark.asyncio
async def test_a_changed_sprite_is_drawn_new_on_the_next_open_and_an_unchanged_one_costs_no_request(
        fake_repo, tmp_path, monkeypatch):
    """With the browser's HTTP cache alive (the certificate trusted, as a phone trusts *.ts.net): the precache done,
    one sprite changes on the town (its hash with it); the page, reloaded as a person reopens it, draws the new
    picture, fetched past the HTTP cache (`cache: "reload"` sends no-cache); an open with nothing changed asks the
    town for no sprite at all."""
    name = "icons/res-gold.png"                        # drawn in the head on every open
    sprite = tmp_path / "res-gold.png"
    sprite.write_bytes(_png(3))
    real = pwa.files()
    monkeypatch.setattr(pwa, "files", lambda: {**real, name: sprite})
    seen: list[tuple[str, dict]] = []                 # every request the listener read: (target, headers)
    parse = phone_http._parse_head

    def record(head: bytes):
        got = parse(head)
        if got:
            seen.append((got[1], got[2]))
        return got
    monkeypatch.setattr(phone_http, "_parse_head", record)
    drawn = "(name) => [...document.querySelectorAll(`img[src='${name}']`)].map((i) => i.complete && i.naturalWidth)"

    async with _phone(fake_repo, trusted=True) as (_, page):
        await _until(page, "() => !!navigator.serviceWorker.controller", None, "the worker controls the page")
        hd = re.compile(r"@hd(1|1_5|2)\.webp$")        # a dpr-1 phone precaches the PNGs (app.js precacheCamp)
        wanted = [p for p in pwa._ASSETS if not hd.search(p)]
        await _until(page, """async ([cache, wanted]) => {
            const keys = new Set((await (await caches.open(cache)).keys()).map((r) => new URL(r.url).pathname));
            return wanted.every((p) => keys.has('/app/' + p));
        }""", [CACHE, wanted], "the precache finished")
        assert 3 in await page.evaluate(drawn, name)

        sprite.write_bytes(_png(5))                    # an update: the listener's warm-up hashes anew
        new_hash = pwa.assets()[name]
        seen.clear()
        await page.reload()                            # the open that learns the new map…
        await _until(page, """async ([cache, name, hash]) => {
            const r = await (await caches.open(cache)).match('assets.json');
            return !!r && (await r.json())[name] === hash;
        }""", [CACHE, name, new_hash], "the worker kept the new map")
        await page.reload()                            # …and the next one draws the new picture
        await page.locator(".dock").wait_for(timeout=WAIT_MS)
        try:
            await page.wait_for_function(f"() => ({drawn})({name!r}).includes(5)", timeout=WAIT_MS)
        except pw.TimeoutError:
            pytest.fail(f"the old picture is drawn: widths {await page.evaluate(drawn, name)}")
        assert 3 not in await page.evaluate(drawn, name)
        fetched = [h for target, h in seen if target == "/app/" + name]
        assert fetched, "the new picture never came from the town"
        assert all(h.get("cache-control") == "no-cache" for h in fetched), fetched

        seen.clear()
        await page.reload()                            # nothing changed: no sprite asked of the town
        await page.locator(".dock").wait_for(timeout=WAIT_MS)
        await page.wait_for_function(f"() => ({drawn})({name!r}).includes(5)", timeout=WAIT_MS)
        await page.wait_for_timeout(500)
        assert [t for t, _ in seen if pwa.is_cache_first(t.removeprefix(pwa.PREFIX).split("?")[0])] == []


@pytest.mark.asyncio
async def test_the_phones_camp_draws_without_town_hall_and_hall_notices_reach_home(fake_repo):
    """Spec 13, round 2: the phone loads camp/layout.js, so its Camp loses the hall too.
    The phone's Camp still draws without error and has no Town Hall."""
    async with _phone(fake_repo) as (server, page):
        server.host.command("you.look", {"look": "camp"})
        await page.wait_for_function("() => document.documentElement.dataset.theme === 'camp'", timeout=WAIT_MS)
        camp = page.locator(".camp")
        await camp.wait_for(timeout=WAIT_MS)
        # Camp draws without error and has no Town Hall hut
        assert await camp.locator(".camp-hut[data-b='town_hall']").count() == 0
        # The phone loads camp/layout.js: order and lay exclude town_hall
        res = await page.evaluate("""async () => {
            const { lay, order } = await import('/app/camp/layout.js');
            const bs = [{ id: 'town_hall', type: 'town_hall' }, { id: 'pool', type: 'barracks' }];
            const roads = [{ id: 'r1', from: 'town_hall', to: 'pool' }];
            const ord = order(bs, roads);
            const L = lay(bs, roads, { b: 1, s: 1 }, () => [64, 64], () => false, 'homes/kin.png');
            return {
                has_hall_in_order: ord.some(b => b.id === 'town_hall'),
                has_hall_in_buildings: 'town_hall' in L.buildings,
                has_home: Boolean(L.home)
            };
        }""")
        assert not res["has_hall_in_order"]
        assert not res["has_hall_in_buildings"]
        assert res["has_home"]
