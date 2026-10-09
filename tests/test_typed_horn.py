"""📯 The Horn: a sound per incoming event, mute, quiet hours, cooldown, the hut line."""
from __future__ import annotations

import datetime as dt
import wave
from pathlib import Path

import pytest

from orkcraft.realm import horn, catalog


def test_the_table_picks_the_most_precise_line():
    table, problems = horn.parse(["mail.received: chime", "gate_pit: ding", "gate_pit/pit.link: alarm", "*: drum",
                                   "nonsense", "x.y: kazoo", "pool.failed: sounds/fail.mp3"])
    assert len(problems) == 2 and table["pool.failed"] == "sounds/fail.mp3"
    assert horn.pick(table, "gate_pit", "pit.link") == ("alarm", "gate_pit/pit.link")
    assert horn.pick(table, "gate_pit", "pit.text") == ("ding", "gate_pit")
    assert horn.pick(table, "inbox", "mail.received") == ("chime", "mail.received")
    assert horn.pick(table, "forge", "git.commit") == ("drum", "*")
    assert horn.pick({}, "forge", "git.commit", "ding") == ("ding", "")
    assert horn.put(["a.b: horn", "*: none"], "a.b", "chime") == ["a.b: chime", "*: none"]
    assert horn.put(["a.b: horn"], "*", "ding") == ["a.b: horn", "*: ding"]
    assert [horn.next_sound(s) for s in ("horn", "none")] == ["chime", "horn"]


def test_quiet_hours_run_over_midnight():
    at = lambda h, m=0: dt.datetime(2026, 10, 3, h, m)
    assert horn.in_quiet("22:00-08:00", at(23)) and horn.in_quiet("22:00-08:00", at(7, 59))
    assert not horn.in_quiet("22:00-08:00", at(8)) and not horn.in_quiet("", at(3))
    assert horn.in_quiet("13:00-14:00", at(13, 30)) and not horn.in_quiet("13:00-14:00", at(14))
    assert horn.quiet_ok("") and not horn.quiet_ok("late") and not horn.quiet_ok("25:00-08:00")


@pytest.mark.parametrize("name", [s for s in horn.SOUNDS if s not in (horn.BELL, horn.NONE)])
def test_the_built_in_sounds_are_short_wav_files(tmp_path: Path, name: str):
    path = horn.sound_file(tmp_path, name)
    assert path is not None and path.parent == tmp_path / ".orkcraft/horn/sounds"
    with wave.open(str(path)) as w:
        secs = w.getnframes() / w.getframerate()
    assert 0.2 < secs < 1.5 and w.getnchannels() == 1
    assert horn.sound_file(tmp_path, "bell") is None and horn.sound_file(tmp_path, "missing.wav") is None


def test_the_spec_is_checked():
    spec = {"id": "b", "title": "Horn", "icon": "📯", "orc": {"name": "Hornblower"}, "type": "horn",
            "config": {"sounds": ["mail.received: kazoo"], "default": "loud", "quiet": "night", "cooldown": 9000}}
    errors = catalog.validate(spec)
    assert any("kazoo" in e for e in errors) and any("default" in e for e in errors)
    assert any("quiet" in e for e in errors) and any("cooldown" in e for e in errors)
    spec["config"] = {"sounds": ["mail.received: chime", "*: none"], "default": "ding", "quiet": "22:00-08:00"}
    assert catalog.validate(spec) == []


def test_without_a_player_the_terminal_bell_rings(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(horn.shutil, "which", lambda cmd: None)
    monkeypatch.setattr(horn.sys, "platform", "linux")
    assert horn.player() is None and not horn.play(tmp_path / "x.wav", None)
