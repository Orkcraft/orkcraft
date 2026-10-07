"""Machine settings: what onboarding asks once per machine (tools, billing, the quiet hours)."""
from __future__ import annotations

import json
from pathlib import Path

from orkcraft import schedule, scroll, settings


def test_defaults_when_there_is_no_file(tmp_path: Path):
    s = settings.load(tmp_path / "none.json")
    assert not s.onboarded and s.quiet is None
    assert set(s.tools) == set(settings.TOOLS)
    assert all(not c.enabled and c.billing == "subscription" for c in s.tools.values())


def test_round_trip(tmp_path: Path):
    f = tmp_path / "deep" / "settings.json"
    s = settings.MachineSettings(onboarded=True, quiet=schedule.DEFAULT_QUIET)
    s.tools["claude"] = settings.ToolChoice(enabled=True, billing="api")
    settings.save(s, f)
    back = settings.load(f)
    assert back.onboarded and back.quiet == schedule.DEFAULT_QUIET
    assert back.tools["claude"].enabled and back.tools["claude"].billing == "api"
    assert not back.tools["agy"].enabled


def test_broken_or_unknown_values_fall_back(tmp_path: Path):
    f = tmp_path / "settings.json"
    f.write_text("{not json", encoding="utf-8")
    assert not settings.load(f).onboarded
    f.write_text('{"tools": {"claude": {"enabled": true, "billing": "barter"}, "gpt": {}}}', encoding="utf-8")
    s = settings.load(f)
    assert s.tools["claude"].enabled and s.tools["claude"].billing == "subscription"
    assert "gpt" not in s.tools


def test_path_follows_env(tmp_path: Path, monkeypatch):
    monkeypatch.delenv("ORKCRAFT_SETTINGS_FILE")
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    assert settings.path() == tmp_path / "orkcraft" / "settings.json"
    monkeypatch.setenv("ORKCRAFT_SETTINGS_FILE", str(tmp_path / "x.json"))
    assert settings.path() == tmp_path / "x.json"


def test_a_new_scroll_has_no_look():
    assert "mode" not in scroll._default_preferences()


def test_the_old_look_and_office_hours_load_and_are_not_written_again(tmp_path: Path):
    f = tmp_path / "settings.json"
    f.write_text(json.dumps({"mode": "shift", "onboarded": True, "office": {"start": "09:00", "end": "18:00"},
                             "office_days": [0, 1, 2], "quiet": {"start": "23:00", "end": "08:00"}}),
                 encoding="utf-8")
    s = settings.load(f)
    assert s.onboarded and s.quiet == schedule.DEFAULT_QUIET
    assert not hasattr(s, "mode") and not hasattr(s, "office") and not hasattr(s, "office_days")
    settings.save(s, f)
    assert not {"mode", "office", "office_days"} & set(json.loads(f.read_text(encoding="utf-8")))
