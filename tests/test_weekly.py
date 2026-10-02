"""🗓 The weekly self-audit (T1108 stage 9): a heavy model's report, ticked items applied as checkpoints."""
from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

import pytest

from orkcraft.realm import checkpoint, metrics, weekly

ORDERS = ("Read every incoming event carefully, summarise it in plain words, list what changed, flag anything "
          "risky and end with a one-line verdict for the operator. Be thorough and careful.")


def _report(**extra) -> dict:
    return {"summary": "The hall's agent talks too much; the crag window is too wide.",
            "items": [
                {"title": "Shorter orders", "why": "same job", "change": "shrink", "building": "town_hall",
                 "target": "orc:seer", "prompt": "Summarise, flag risk, verdict."},
                {"title": "A day of bars", "why": "a week is noise", "change": "set_config", "building": "crag",
                 "key": "window", "value": "24h"},
                {"title": "Bad window", "why": "x", "change": "set_config", "building": "crag", "key": "window",
                 "value": "forever"},
                {"title": "Drop the loot road", "why": "nobody reads it", "change": "remove_road",
                 "building": "town_hall", "road": "nope"},
                {"title": "Think about mail", "why": "advice", "change": "note", "building": ""},
            ], **extra}


@pytest.mark.asyncio
async def test_the_weekly_report_is_checked_ticked_and_applied(fake_repo: Path, monkeypatch):
    from orkcraft import app as app_mod
    from orkcraft import scroll as ts
    from orkcraft.app import OrkcraftApp
    from orkcraft.screens.weekly_modal import WeeklyReportModal

    prompts = []
    monkeypatch.setattr(app_mod, "WEEKLY_RUNNER", lambda p: (prompts.append(p) or json.dumps(_report()), 1.2))
    app = OrkcraftApp(repo_root=fake_repo, auto_commit=False)
    async with app.run_test(size=(180, 50)) as pilot:
        await pilot.pause()
        assert app.build_from_type("crag")
        ts.add_handler(app.scroll, "town_hall", "Seer", kind="agent", orders=ORDERS)
        app.desktop.save()
        metrics.record_run(fake_repo, "town_hall", "done", 0.3, 9000)
        app.open_weekly()
        for _ in range(60):
            await pilot.pause(0.05)
            if isinstance(app.screen, WeeklyReportModal):
                break
        modal = app.screen
        assert isinstance(modal, WeeklyReportModal)
        assert "9000 tokens" in prompts[0] and "[orc:seer] prompt" in prompts[0] and "## crag" in prompts[0]
        report = modal.report
        assert [i.applicable for i in report.items] == [True, True, False, False, False]
        assert "window" in report.items[2].problems[0] and "no road" in report.items[3].problems[0]
        await pilot.press("ctrl+s")
        await pilot.pause()
        assert app.scroll.building("town_hall").garrison.handler("seer").orders == "Summarise, flag risk, verdict."
        assert app.custom_specs["crag"]["config"]["window"] == "24h"
        assert checkpoint.history(fake_repo, "crag")[0].message.startswith("weekly(crag): set window")
        assert checkpoint.history(fake_repo, "town_hall")[0].message.startswith("weekly(town_hall): shrink orc:seer")
        saved = weekly.latest(fake_repo)
        assert saved.applied == [1, 2] and saved.cost_usd == 1.2
        assert app.apply_weekly(saved, [1, 2]) == []                         # applied once, never twice
        assert app.revert_building("crag") and app.custom_specs["crag"].get("config", {}).get("window") != "24h"


def test_a_broken_answer_is_an_error(tmp_path: Path):
    from types import SimpleNamespace as NS

    scroll = NS(buildings=[], building=lambda bid: None)
    assert "JSON" in weekly.run(tmp_path, scroll, {}, lambda p: ("no idea", None)).error
    assert "claude" in weekly.run(tmp_path, scroll, {}, lambda p: (_ for _ in ()).throw(RuntimeError("claude missing"))).error
    assert weekly.latest(tmp_path) is None
    weekly.mark_run(tmp_path, dt.datetime(2026, 10, 4, 5, 0))
    assert weekly.latest(tmp_path) is None and weekly.last_run(tmp_path).hour == 5   # last.json is not a report


@pytest.mark.asyncio
async def test_the_audit_removes_and_adds_buildings_then_offers_a_restart(fake_repo: Path, monkeypatch):
    from orkcraft import app as app_mod
    from orkcraft.app import OrkcraftApp
    from orkcraft.screens.dialogs import Confirm
    from orkcraft.screens.weekly_modal import WeeklyReportModal

    answer = {"summary": "The lake is unused; a crag would show the spend.", "restart": True, "items": [
        {"title": "Drop the lake", "why": "no runs in a week", "change": "remove_building", "building": "lake"},
        {"title": "A spend crag", "why": "see the week's spend", "change": "add_building", "building": "spend",
         "type": "crag", "title": "Spend", "config": {"source": "spend"}},
        {"title": "No hall", "why": "x", "change": "remove_building", "building": "town_hall"},
        {"title": "A workshop", "why": "x", "change": "add_building", "building": "ws", "type": "workshop"}]}
    prompts = []
    monkeypatch.setattr(app_mod, "WEEKLY_RUNNER", lambda p: (prompts.append(p) or json.dumps(answer), 0.5))
    app = OrkcraftApp(repo_root=fake_repo, auto_commit=False)
    async with app.run_test(size=(180, 50)) as pilot:
        await pilot.pause()
        assert app.build_from_type("lake")
        app.open_weekly()
        for _ in range(60):
            await pilot.pause(0.05)
            if isinstance(app.screen, WeeklyReportModal):
                break
        report = app.screen.report
        assert "camp types:" in prompts[0] and "crag" in prompts[0]
        assert [i.applicable for i in report.items] == [True, True, False, False] and report.restart
        await pilot.press("ctrl+s")
        for _ in range(40):
            await pilot.pause(0.05)
            if isinstance(app.screen, Confirm):
                break
        assert app.desktop.get_window("lake").hidden and app.custom_specs["spend"]["config"] == {"source": "spend"}
        assert checkpoint.history(fake_repo, "lake")[0].message.startswith("weekly(lake): remove")
        assert isinstance(app.screen, Confirm)
        exits = []
        monkeypatch.setattr(app, "exit", lambda result=None, **k: exits.append(result))
        await pilot.press("enter")
        await pilot.pause()
        assert exits == ["restart"]


@pytest.mark.asyncio
async def test_the_settings_window(fake_repo: Path):
    from textual.widgets import Input

    from orkcraft.app import OrkcraftApp
    from orkcraft.realm import fastpath
    from orkcraft.screens.settings_modal import SettingsModal

    app = OrkcraftApp(repo_root=fake_repo, auto_commit=False)
    async with app.run_test(size=(160, 45)) as pilot:
        await pilot.pause()
        app.open_settings()
        await pilot.pause()
        modal = app.screen
        assert isinstance(modal, SettingsModal) and modal.query_one("#set-weekly_model", Input).value == "opus"
        modal.query_one("#set-weekly_at", Input).value = "on sundays"
        await pilot.press("ctrl+s")
        await pilot.pause()
        assert app.screen is modal and "not a schedule" in str(modal.query_one("#set-errors").render())
        modal.query_one("#set-weekly_at", Input).value = "weekly sat 05:10"
        modal.query_one("#set-weekly_model", Input).value = "sonnet"
        await pilot.press("ctrl+s")
        await pilot.pause()
        s = fastpath.settings(fake_repo)
        assert (s["weekly_at"], s["weekly_model"]) == ("weekly sat 05:10", "sonnet")


def test_the_cli_starts_again_on_restart(fake_repo: Path, monkeypatch):
    from orkcraft import cli

    runs = []

    class Fake:
        def __init__(self, **kw):
            runs.append(kw)

        def run(self):
            return "restart" if len(runs) == 1 else None

    monkeypatch.setattr(cli, "OrkcraftApp", Fake)
    monkeypatch.chdir(fake_repo)
    assert cli.main([]) == 0 and len(runs) == 2
