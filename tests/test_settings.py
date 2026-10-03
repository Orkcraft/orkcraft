"""Machine settings: what onboarding asks once per machine (tools, billing, mode)."""
from __future__ import annotations

from pathlib import Path

from orkcraft import schedule, scroll, settings


def test_defaults_when_there_is_no_file(tmp_path: Path):
    s = settings.load(tmp_path / "none.json")
    assert s.mode == "camp" and not s.onboarded and s.quiet is None
    assert set(s.tools) == set(settings.TOOLS)
    assert all(not c.enabled and c.billing == "subscription" for c in s.tools.values())


def test_round_trip(tmp_path: Path):
    f = tmp_path / "deep" / "settings.json"
    s = settings.MachineSettings(mode="shift", onboarded=True, quiet=schedule.DEFAULT_QUIET)
    s.tools["claude"] = settings.ToolChoice(enabled=True, billing="api")
    settings.save(s, f)
    back = settings.load(f)
    assert back.mode == "shift" and back.onboarded and back.quiet == schedule.DEFAULT_QUIET
    assert back.tools["claude"].enabled and back.tools["claude"].billing == "api"
    assert not back.tools["agy"].enabled


def test_broken_or_unknown_values_fall_back(tmp_path: Path):
    f = tmp_path / "settings.json"
    f.write_text("{not json", encoding="utf-8")
    assert settings.load(f).mode == "camp"
    f.write_text('{"mode": "neon", "tools": {"claude": {"enabled": true, "billing": "barter"}, "gpt": {}}}',
                 encoding="utf-8")
    s = settings.load(f)
    assert s.mode == "camp" and s.tools["claude"].enabled and s.tools["claude"].billing == "subscription"
    assert "gpt" not in s.tools


def test_path_follows_env(tmp_path: Path, monkeypatch):
    monkeypatch.delenv("ORKCRAFT_SETTINGS_FILE")
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    assert settings.path() == tmp_path / "orkcraft" / "settings.json"
    monkeypatch.setenv("ORKCRAFT_SETTINGS_FILE", str(tmp_path / "x.json"))
    assert settings.path() == tmp_path / "x.json"


def test_a_new_scroll_leaves_the_mode_to_the_machine():
    assert "mode" not in scroll._default_preferences()


def test_the_old_mode_names_still_load(tmp_path: Path):
    f = tmp_path / "settings.json"
    f.write_text('{"mode": "plain"}', encoding="utf-8")
    assert settings.load(f).mode == "office"
    f.write_text('{"mode": "immersion"}', encoding="utf-8")
    assert settings.load(f).mode == "camp"


def test_the_hidden_mode_of_main_reads_as_office():
    assert settings.MachineSettings.from_dict({"mode": "hidden"}).mode == "office"
    assert settings.MachineSettings.from_dict({"mode": "nonsense"}).mode == settings.DEFAULT_MODE
