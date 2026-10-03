"""🎺 The Bugle: a sound per incoming event, mute, quiet hours, cooldown, the hut line."""
from __future__ import annotations

import datetime as dt
import wave
from pathlib import Path

import pytest

from orkcraft.app import OrkcraftApp
from orkcraft.realm import bugle, catalog, masonry
from orkcraft.realm.pipes import Payload
from orkcraft.screens.dialogs import TextBlock
from orkcraft.screens.typed.bugle_view import BugleView


def test_the_table_picks_the_most_precise_line():
    table, problems = bugle.parse(["mail.received: chime", "gate_pit: ding", "gate_pit/pit.link: alarm", "*: drum",
                                   "nonsense", "x.y: kazoo", "pool.failed: sounds/fail.mp3"])
    assert len(problems) == 2 and table["pool.failed"] == "sounds/fail.mp3"
    assert bugle.pick(table, "gate_pit", "pit.link") == ("alarm", "gate_pit/pit.link")
    assert bugle.pick(table, "gate_pit", "pit.text") == ("ding", "gate_pit")
    assert bugle.pick(table, "inbox", "mail.received") == ("chime", "mail.received")
    assert bugle.pick(table, "forge", "git.commit") == ("drum", "*")
    assert bugle.pick({}, "forge", "git.commit", "ding") == ("ding", "")
    assert bugle.put(["a.b: horn", "*: none"], "a.b", "chime") == ["a.b: chime", "*: none"]
    assert bugle.put(["a.b: horn"], "*", "ding") == ["a.b: horn", "*: ding"]
    assert [bugle.next_sound(s) for s in ("horn", "none")] == ["chime", "horn"]


def test_quiet_hours_run_over_midnight():
    at = lambda h, m=0: dt.datetime(2026, 10, 3, h, m)
    assert bugle.in_quiet("22:00-08:00", at(23)) and bugle.in_quiet("22:00-08:00", at(7, 59))
    assert not bugle.in_quiet("22:00-08:00", at(8)) and not bugle.in_quiet("", at(3))
    assert bugle.in_quiet("13:00-14:00", at(13, 30)) and not bugle.in_quiet("13:00-14:00", at(14))
    assert bugle.quiet_ok("") and not bugle.quiet_ok("late") and not bugle.quiet_ok("25:00-08:00")


@pytest.mark.parametrize("name", [s for s in bugle.SOUNDS if s not in (bugle.BELL, bugle.NONE)])
def test_the_built_in_sounds_are_short_wav_files(tmp_path: Path, name: str):
    path = bugle.sound_file(tmp_path, name)
    assert path is not None and path.parent == tmp_path / ".orkcraft/bugle/sounds"
    with wave.open(str(path)) as w:
        secs = w.getnframes() / w.getframerate()
    assert 0.2 < secs < 1.5 and w.getnchannels() == 1
    assert bugle.sound_file(tmp_path, "bell") is None and bugle.sound_file(tmp_path, "missing.wav") is None


def test_the_spec_is_checked():
    spec = {"id": "b", "title": "Bugle", "icon": "🎺", "orc": {"name": "Bugler"}, "type": "bugle",
            "config": {"sounds": ["mail.received: kazoo"], "default": "loud", "quiet": "night", "cooldown": 9000}}
    errors = catalog.validate(spec)
    assert any("kazoo" in e for e in errors) and any("default" in e for e in errors)
    assert any("quiet" in e for e in errors) and any("cooldown" in e for e in errors)
    spec["config"] = {"sounds": ["mail.received: chime", "*: none"], "default": "ding", "quiet": "22:00-08:00"}
    assert catalog.validate(spec) == []


@pytest.mark.asyncio
async def test_the_bugle_sounds_what_comes_down_its_roads(fake_repo: Path, monkeypatch):
    for s in ({"id": "gate_pit", "title": "The Pit", "icon": "🕳️", "orc": {"name": "Scavenger"}, "type": "pit"},
              {"id": "horn", "title": "The Bugle", "icon": "🎺", "orc": {"name": "Bugler"}, "type": "bugle",
               "config": {"sounds": ["pit.link: alarm"], "cooldown": 0}}):
        assert masonry.save_spec(fake_repo, s) == []
    played: list[tuple[str, str]] = []
    monkeypatch.setattr(BugleView, "player", staticmethod(lambda path, sound: played.append((sound, path.name)) or "player"))
    app = OrkcraftApp(repo_root=fake_repo, auto_commit=False)
    async with app.run_test(size=(200, 46)) as pilot:
        await pilot.pause()
        app.add_road("horn", "gate_pit", "pit.link", None)
        app.add_road("horn", "gate_pit", "pit.text", None)
        view = app.desktop.get_window("horn").query_one(BugleView)
        view.refresh_data()
        assert view.rows == [("gate_pit", "pit.link"), ("gate_pit", "pit.text"), ("", "*")]
        view.receive(Payload("text", "https://x", "gate_pit", "pit.link", "a link"), "a link", "")
        view.receive(Payload("text", "hello", "gate_pit", "pit.text", "a paste"), "a paste", "")
        assert played == [("alarm", "alarm.wav"), ("horn", "horn.wav")]
        assert view.hut_lines([8]) == ["♪ horn"] and [c.sound for c in view.calls] == ["horn", "alarm"]

        assert view.cycle("gate_pit", "pit.text") == "chime"              # Enter: the next sound, heard at once
        assert app.custom_specs["horn"]["config"]["sounds"] == ["pit.link: alarm", "pit.text: chime"]
        assert played[-1][0] == "chime"
        view.save_config({"sounds": ["gate_pit/pit.link: drum", "pit.link: alarm", "pit.text: chime"]})
        assert view.sound_of("gate_pit", "pit.link") == "drum"            # the road's own line decides…
        assert view.cycle("gate_pit", "pit.link") == "ding"               # …and Enter changes that line
        assert app.custom_specs["horn"]["config"]["sounds"][:2] == ["gate_pit/pit.link: ding", "pit.link: alarm"]
        view.save_config({"sounds": ["pit.link: alarm", "pit.text: chime"]})

        view.save_config({"cooldown": 60})
        view.receive(Payload("text", "1", "gate_pit", "pit.text", "one"), "one", "")
        view.receive(Payload("text", "2", "gate_pit", "pit.text", "two"), "two", "")
        assert [c.played for c in view.calls[:2]] == ["cooldown", "player"]

        assert view.quick_action("bugle.mute") and view.muted
        n = len(played)
        view.receive(Payload("text", "x", "gate_pit", "pit.link", "muted"), "muted", "")
        assert len(played) == n and view.calls[0].played == "muted" and view.hut_lines([8]) == ["🔇 muted"]
        assert view.quick_action("bugle.mute") and not view.muted

        app.desktop.focus_window(app.desktop.get_window("horn"))
        await pilot.pause()
        await pilot.press("e")
        await pilot.pause()
        assert isinstance(app.screen, TextBlock)
        app.screen.query_one("#block-text").text = "gate_pit: ding\n*: none"
        await pilot.press("ctrl+s")
        await pilot.pause()
        assert app.custom_specs["horn"]["config"]["sounds"] == ["gate_pit: ding", "*: none"]


def test_without_a_player_the_terminal_bell_rings(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(bugle.shutil, "which", lambda cmd: None)
    monkeypatch.setattr(bugle.sys, "platform", "linux")
    assert bugle.player() is None and not bugle.play(tmp_path / "x.wav", None)
