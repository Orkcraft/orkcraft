"""The Night report on the phone's Today (docs/specs/32-night-gate.md §3; gui/static/pwa/night.js): Chromium at
390 × 844, paired over the phone listener, against a stub board, both looks. Green → Pass to main asks once in a sheet
naming the count; red → in Needs you, counted on the Today tab, no Pass. Screenshots to docs/design/img/night-gate/ when
NIGHT_GATE_SHOTS is set."""
from __future__ import annotations

import asyncio
import json
from contextlib import asynccontextmanager
from pathlib import Path

import pytest

pwa = pytest.importorskip("playwright.async_api")

from orkcraft.gui import mobile, phone_tls  # noqa: E402
from tests.test_night_gate_browser import GREEN, RED, SHOTS, TAKE  # noqa: E402
from tests.test_phones import _listening, _serve  # noqa: E402
from tests.test_pwa_board_browser import Stub  # noqa: E402
from tests.test_pwa_browser import CHROMIUM, WAIT_MS, _spki  # noqa: E402


class PhoneStub(Stub):
    def __init__(self, night: dict) -> None:
        super().__init__()
        self.needs = []
        self.todos = []
        self.night = json.loads(json.dumps(night))

    def commands(self) -> dict:
        return {**super().commands(), "gate.pass_night": self.pass_night, "gate.run_night": self.run_night}

    def board(self, args):
        got = super().board(args)
        got["today"]["night"] = self.night
        return got

    def pass_night(self, args):
        self.logged("gate.pass_night", args)
        self.night["passed_at"] = "2026-10-17T08:12:00"
        self.bump()
        return {"ok": True}

    def run_night(self, args):
        self.logged("gate.run_night", args)
        self.night["running"] = True
        self.bump()
        return {"ok": True}


@asynccontextmanager
async def _phone(repo: Path, monkeypatch, look: str, night: dict):
    stub = PhoneStub(night)
    real = mobile.phone_snapshot
    monkeypatch.setattr(mobile, "phone_snapshot", lambda host: {**(snap := real(host)), "rev": f"{snap['rev']}-{stub.rev}",
                                                                   "focus": "board", "ideas_rev": stub.rev, "look": look})
    for name in stub.commands():
        monkeypatch.setitem(mobile.COMMANDS, name, None)
    server, task = await _serve(repo)
    server.host.commands.update(stub.commands())
    try:
        offer = server.host.command("phones.pair")
        await _listening(server)
        async with pwa.async_playwright() as p:
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
                await page.locator(".board .night").wait_for(timeout=WAIT_MS)
                await page.wait_for_function(f"document.documentElement.dataset.look === '{look}'", timeout=WAIT_MS)
                yield stub, page
            finally:
                await browser.close()
    finally:
        server.stop()
        await asyncio.wait_for(task, 10)


async def _fits(page) -> None:
    assert await page.evaluate("document.documentElement.scrollWidth <= 390")
    small = await page.evaluate("""() => [...document.querySelectorAll('.board .night button')]
        .filter((b) => b.offsetParent).map((b) => [b.textContent, b.getBoundingClientRect().height]).filter(([, h]) => h < 44)""")
    assert small == []


async def _phone_shot(page, name: str) -> None:
    if TAKE:
        SHOTS.mkdir(parents=True, exist_ok=True)
        await page.screenshot(path=str(SHOTS / f"{name}.png"))


@pytest.mark.asyncio
@pytest.mark.parametrize("look", ["camp", "office"])
async def test_the_phone_green_card_passes_after_one_ask(fake_repo, monkeypatch, look):
    async with _phone(fake_repo, monkeypatch, look, GREEN) as (stub, page):
        card = page.locator(".board .night")
        assert "2 changes ready for main" in await card.inner_text()
        assert await page.locator(".board-tab", has_text="Today").locator(".q-dot").is_hidden()
        await _fits(page)
        await card.get_by_role("button", name="Details").click()
        assert "Dark mode switch" in await card.locator(".night-details").inner_text()
        await _phone_shot(page, f"phone-{look}-green")
        await card.get_by_role("button", name="Pass to main").click()
        sheet = page.locator("dialog.sheet[open]")
        assert "Pass 2 changes to main?" in await sheet.inner_text()
        await _phone_shot(page, f"phone-{look}-confirm")
        assert not [c for c in stub.calls if c[0] == "gate.pass_night"]
        await sheet.get_by_role("button", name="Pass 2 changes").click()
        await page.locator(".board .night").wait_for(state="detached", timeout=WAIT_MS)
        assert ("gate.pass_night", {"date": "2026-10-17"}) in stub.calls


@pytest.mark.asyncio
@pytest.mark.parametrize("look", ["camp", "office"])
async def test_the_phone_red_card_stands_in_needs_you(fake_repo, monkeypatch, look):
    async with _phone(fake_repo, monkeypatch, look, RED) as (stub, page):
        card = page.locator(".board .night.night-red")
        await card.wait_for(timeout=WAIT_MS)
        assert await page.evaluate("""() => { const h = [...document.querySelectorAll('.board .pane h2')].find((x) => x.textContent === 'Needs you');
            return h.nextElementSibling === document.querySelector('.board .night'); }""")
        assert await page.locator(".board-tab", has_text="Today").locator(".q-dot").inner_text() == "1"
        assert "test_queue_survives_a_restart" in await card.locator(".night-notfixed").inner_text()
        assert await card.get_by_role("button", name="Pass to main").count() == 0
        await _fits(page)
        await _phone_shot(page, f"phone-{look}-red")
        await card.get_by_role("button", name="Run now").click()
        await page.locator(".board .night.night-running").wait_for(timeout=WAIT_MS)
        assert ("gate.run_night", {}) in stub.calls
