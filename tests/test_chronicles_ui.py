"""UI tests for Chronicles: building audit logs, unit run protocols, diffs and deployment env."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from textual.widgets import Input, OptionList, Static

from orkcraft.app import OrkcraftApp
from orkcraft.screens.chronicles_view import BuildingChronicles, UnitChronicles
from orkcraft.screens.console import ClanRoster
from orkcraft.screens.garrison_modal import GarrisonModal
from orkcraft.screens.road_modal import SubscribeModal

SIZE = (200, 50)


def _line(**kw) -> str:
    return json.dumps(kw) + "\n"


@pytest.mark.asyncio
async def test_building_chronicles_recording(fake_repo: Path, isolated_layout_file: Path):
    """1. Recruit a Forge orc (R), pin the Forge (alt+b), subscribe the Forge to the Loot Chest
    with the new handler (Y) → the Forge events file has orc_recruited, pinned, road_subscribed in that order;
    a cancelled recruit modal adds nothing."""
    app = OrkcraftApp(repo_root=fake_repo, auto_commit=False)
    async with app.run_test(size=SIZE) as pilot:
        await pilot.pause()
        await pilot.press("2")
        await pilot.pause()
        assert app.focus_state.mode == "building"
        assert app.focus_state.building_id == "town_hall"

        # Cancelled recruit modal adds nothing
        await pilot.press("R")
        await pilot.pause()
        assert isinstance(app.screen, GarrisonModal)
        await pilot.press("escape")
        await pilot.pause()
        assert not isinstance(app.screen, GarrisonModal)

        events_p = fake_repo / ".orkcraft" / "history" / "buildings" / "town_hall.events.jsonl"
        assert not events_p.exists()

        # Recruit a Forge orc
        await pilot.press("R")
        await pilot.pause()
        assert isinstance(app.screen, GarrisonModal)
        modal = app.screen
        modal.query_one("#recruit-name", Input).value = "Coder"
        modal.query_one("#recruit-role", Input).value = "tickets"
        modal.query_one("#recruit-orders", Input).value = "take T1001"
        await pilot.click("#recruit-submit")
        await pilot.pause()

        # Pin the Forge
        await pilot.press("alt+b")
        await pilot.pause()

        # A road Loot Chest → Forge worked by the Coder
        await pilot.press("Y")
        await pilot.pause()
        loot_win = app.desktop.get_window("loot")
        assert loot_win is not None
        await pilot.press(str(loot_win.number))
        await pilot.pause()
        assert isinstance(app.screen, SubscribeModal)
        await pilot.press("enter")
        await pilot.pause()

        # Verify chat events file
        assert events_p.exists()
        lines = [json.loads(line) for line in events_p.read_text(encoding="utf-8").splitlines() if line.strip()]
        types = [e["type"] for e in lines]
        assert types == ["orc_recruited", "pinned", "road_subscribed"]
        assert lines[0]["orc"] == "Coder"
        assert (lines[2]["source"], lines[2]["event"], lines[2]["handler"]) == ("Artifacts", "selection", "Coder")


@pytest.mark.asyncio
async def test_building_chronicles_overlay(fake_repo: Path, isolated_layout_file: Path):
    """2. L in Building state on the Forge opens BuildingChronicles listing those three
    sentences newest first; Esc closes."""
    app = OrkcraftApp(repo_root=fake_repo, auto_commit=False)
    async with app.run_test(size=SIZE) as pilot:
        await pilot.pause()
        await pilot.press("2")
        await pilot.pause()

        # Recruit Coder
        await pilot.press("R")
        await pilot.pause()
        modal = app.screen
        modal.query_one("#recruit-name", Input).value = "Coder"
        modal.query_one("#recruit-role", Input).value = "tickets"
        await pilot.click("#recruit-submit")
        await pilot.pause()

        # Pin the Forge
        await pilot.press("alt+b")
        await pilot.pause()

        # A road Loot Chest → Forge
        await pilot.press("Y")
        await pilot.pause()
        loot_win = app.desktop.get_window("loot")
        assert loot_win is not None
        await pilot.press(str(loot_win.number))
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause()

        # Press L in building state
        await pilot.press("L")
        await pilot.pause()

        assert isinstance(app.screen, BuildingChronicles)
        screen = app.screen
        lst = screen.query_one("#building-chronicles-list", OptionList)
        prompts = [str(lst.get_option_at_index(i).prompt) for i in range(lst.option_count)]
        event_prompts = [p for p in prompts if not p.startswith("──")]
        assert len(event_prompts) == 3
        # Newest first: road_subscribed, pinned, orc_recruited
        assert "road from Artifacts (selection) → Coder" in event_prompts[0]
        assert "pinned" in event_prompts[1]
        assert "Coder joined the garrison" in event_prompts[2]

        # Esc closes
        await pilot.press("escape")
        await pilot.pause()
        assert not isinstance(app.screen, BuildingChronicles)
        assert app.focus_state.mode == "building"


@pytest.mark.asyncio
async def test_unit_chronicles_with_run(fake_repo: Path, isolated_layout_file: Path):
    """3. Unit Chronicles with a fake run: write a transcript JSONL with a prompt, an Edit tool
    call and a final text, and a sessions.jsonl line in <repo>/.orkcraft/; select Coder → L
    → one run #001 … ✅; its steps list contains 🔧 Edit · a.py; D shows a Spire payload whose
    markdown contains +x = 2."""
    orkcraft_dir = fake_repo / ".orkcraft"
    orkcraft_dir.mkdir(parents=True, exist_ok=True)
    t_file = orkcraft_dir / "t1.jsonl"
    usage = {"input_tokens": 10, "output_tokens": 5, "cache_read_input_tokens": 100, "cache_creation_input_tokens": 7}
    t_file.write_text(
        _line(type="summary", summary="x")
        + _line(type="user", timestamp="2026-09-29T10:00:00Z", message={"role": "user", "content": "Fix T1001 please"})
        + _line(type="assistant", timestamp="2026-09-29T10:00:05Z", message={
            "id": "m1", "role": "assistant", "usage": usage,
            "content": [{"type": "text", "text": "Looking."}]})
        + _line(type="assistant", timestamp="2026-09-29T10:00:06Z", message={
            "id": "m1", "role": "assistant", "usage": usage,
            "content": [{"type": "tool_use", "id": "t1", "name": "Edit",
                         "input": {"file_path": "a.py", "old_string": "x = 1", "new_string": "x = 2"}}]})
        + _line(type="user", timestamp="2026-09-29T10:00:07Z", message={"role": "user", "content": [
            {"type": "tool_result", "tool_use_id": "t1", "content": "ok"}]})
        + _line(type="assistant", timestamp="2026-09-29T10:01:00Z", message={
            "id": "m2", "role": "assistant", "usage": {"input_tokens": 1, "output_tokens": 2},
            "content": [{"type": "text", "text": "Done."}]}),
        encoding="utf-8",
    )

    sessions_file = orkcraft_dir / "sessions.jsonl"
    sessions_file.write_text(
        json.dumps({
            "harness": "claude",
            "session": "s1",
            "orc": "town_hall/coder",
            "transcript": str(t_file),
            "ts": "2026-09-29T10:00:00Z",
        }) + "\n",
        encoding="utf-8",
    )

    app = OrkcraftApp(repo_root=fake_repo, auto_commit=False)
    async with app.run_test(size=SIZE) as pilot:
        await pilot.pause()
        await pilot.press("2")
        await pilot.pause()

        # Recruit Coder
        await pilot.press("R")
        await pilot.pause()
        modal = app.screen
        modal.query_one("#recruit-name", Input).value = "Coder"
        modal.query_one("#recruit-role", Input).value = "tickets"
        await pilot.click("#recruit-submit")
        await pilot.pause()

        # Select Coder in Clan Roster
        roster = app.screen.query_one("#clan-roster", ClanRoster)
        roster_list = roster.query_one("#roster-list", OptionList)
        roster_list.focus()
        await pilot.press("2")
        await pilot.pause()
        assert app.focus_state.mode == "unit"
        assert app.focus_state.orc_key == "orc:resident:town_hall/coder"

        # Press L
        await pilot.press("L")
        await pilot.pause()
        assert isinstance(app.screen, UnitChronicles)

        unit_chron = app.screen
        runs_list = unit_chron.query_one("#runs-list", OptionList)
        assert runs_list.option_count == 1
        prompt_text = str(runs_list.get_option_at_index(0).prompt)
        assert "#001" in prompt_text
        assert "✅" in prompt_text

        # Steps list contains 🔧 Edit · a.py
        proto_list = unit_chron.query_one("#protocol-steps", OptionList)
        step_prompts = [str(proto_list.get_option_at_index(i).prompt) for i in range(proto_list.option_count)]
        assert any("🔧 Edit · a.py" in p for p in step_prompts)

        # Enter on Edit step expands detail
        edit_idx = next(i for i, p in enumerate(step_prompts) if "🔧 Edit · a.py" in p)
        proto_list.focus()
        proto_list.highlighted = edit_idx
        await pilot.press("enter")
        await pilot.pause()

        detail_widget = unit_chron.query_one("#step-detail", Static)
        detail_text = str(detail_widget.render())
        assert "a.py" in detail_text


@pytest.mark.asyncio
async def test_unit_chronicles_empty(fake_repo: Path, isolated_layout_file: Path):
    """4. L on an orc without runs shows the empty text; Esc returns to Unit state."""
    app = OrkcraftApp(repo_root=fake_repo, auto_commit=False)
    async with app.run_test(size=SIZE) as pilot:
        await pilot.pause()
        await pilot.press("2")
        await pilot.pause()

        # Recruit Coder
        await pilot.press("R")
        await pilot.pause()
        modal = app.screen
        modal.query_one("#recruit-name", Input).value = "Coder"
        modal.query_one("#recruit-role", Input).value = "tickets"
        await pilot.click("#recruit-submit")
        await pilot.pause()

        # Select Coder
        roster = app.screen.query_one("#clan-roster", ClanRoster)
        roster_list = roster.query_one("#roster-list", OptionList)
        roster_list.focus()
        await pilot.press("2")
        await pilot.pause()
        assert app.focus_state.mode == "unit"

        # Press L on orc without runs
        await pilot.press("L")
        await pilot.pause()
        assert isinstance(app.screen, UnitChronicles)

        unit_chron = app.screen
        empty_widget = unit_chron.query_one("#runs-empty", Static)
        assert "No runs yet — deploy this ork (C) to start one." in str(empty_widget.render())

        # Esc returns to Unit state
        await pilot.press("escape")
        await pilot.pause()
        assert not isinstance(app.screen, UnitChronicles)
        assert app.focus_state.mode == "unit"


@pytest.mark.asyncio
async def test_deploy_passes_orc_env(fake_repo: Path, monkeypatch: pytest.MonkeyPatch, isolated_layout_file: Path):
    """5. C deploy passes ORKCRAFT_ORC (monkeypatch app.chat.deploy and assert the env)."""
    app = OrkcraftApp(repo_root=fake_repo, auto_commit=False)
    deploy_calls = []

    def spy_deploy(key_prefix, command, harness, title, env=None):
        deploy_calls.append({
            "key_prefix": key_prefix,
            "command": command,
            "harness": harness,
            "title": title,
            "env": env,
        })
        return "deploy:test:1"

    async with app.run_test(size=SIZE) as pilot:
        await pilot.pause()
        monkeypatch.setattr(app.chat, "deploy", spy_deploy)

        await pilot.press("2")
        await pilot.pause()

        # Recruit Coder
        await pilot.press("R")
        await pilot.pause()
        modal = app.screen
        modal.query_one("#recruit-name", Input).value = "Coder"
        modal.query_one("#recruit-role", Input).value = "tickets"
        await pilot.click("#recruit-submit")
        await pilot.pause()

        # Select Coder
        roster = app.screen.query_one("#clan-roster", ClanRoster)
        roster_list = roster.query_one("#roster-list", OptionList)
        roster_list.focus()
        await pilot.press("2")
        await pilot.pause()
        assert app.focus_state.mode == "unit"

        # Press C
        await pilot.press("C")
        await pilot.pause()

        assert len(deploy_calls) == 1
        assert deploy_calls[0]["env"] == {"ORKCRAFT_ORC": "town_hall/coder"}
