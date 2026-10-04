"""🛑 Halt All and the run's 🪙 limit reach the buildings that call models on their own."""
from __future__ import annotations

import threading
from pathlib import Path

import pytest

from orkcraft.app import OrkcraftApp
from orkcraft.realm import masonry

SIZE = (200, 46)


def _specs(repo: Path) -> None:
    for s in ({"id": "camp", "title": "Barracks", "icon": "🏕", "orc": {"name": "Grunts"}, "type": "barracks"},
              {"id": "fire", "title": "Clan Fire", "icon": "🪔", "orc": {"name": "Chieftain"}, "type": "council",
               "config": {"members": ["Planner:claude"]}},
              {"id": "grinder", "title": "Mill", "icon": "⚙️", "orc": {"name": "Miller"}, "type": "mill",
               "config": {"steps": ["agent: shorten it"]}}):
        assert masonry.save_spec(repo, s) == []


@pytest.mark.asyncio
async def test_halt_all_stops_the_barracks_the_clan_fire_and_the_mill(fake_repo: Path):
    from orkcraft.screens.typed.mill_view import MillView
    from orkcraft.screens.typed.pool_view import PoolView
    from orkcraft.screens.typed.team_view import TeamView
    _specs(fake_repo)
    app = OrkcraftApp(repo_root=fake_repo, auto_commit=False)
    async with app.run_test(size=SIZE) as pilot:
        await pilot.pause()
        camp = app.desktop.get_window("camp").query_one(PoolView)
        fire = app.desktop.get_window("fire").query_one(TeamView)
        mill = app.desktop.get_window("grinder").query_one(MillView)
        orc_run, review = threading.Event(), threading.Event()
        camp._cancels["Grub"] = orc_run
        fire._cancel, fire._busy = review, True
        mill.running, milling = True, mill.cancel
        app.action_halt()
        assert orc_run.is_set() and review.is_set() and milling.is_set()
        assert camp.state.paused and not mill.cancel.is_set()          # the next cart mills again


@pytest.mark.asyncio
async def test_out_of_gold_no_task_is_hired_and_no_agent_step_runs(fake_repo: Path, monkeypatch):
    from orkcraft.screens.typed.mill_view import MillView
    from orkcraft.screens.typed.pool_view import PoolView
    _specs(fake_repo)
    app = OrkcraftApp(repo_root=fake_repo, auto_commit=False)
    monkeypatch.setattr(app, "gold_exhausted", lambda: True)
    async with app.run_test(size=SIZE) as pilot:
        await pilot.pause()
        camp = app.desktop.get_window("camp").query_one(PoolView)
        task = camp.add_task("Write the changelog", "for v0.2")
        assert task in camp.state.queue and not camp.state.orcs and task.decided.startswith("budget")
        mill = app.desktop.get_window("grinder").query_one(MillView)
        with pytest.raises(RuntimeError, match="budget exhausted"):
            mill._agent()("shorten it", "a long text")
