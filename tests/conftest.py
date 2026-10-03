"""Test fixtures: a plain git project, isolated layout and caches."""
from __future__ import annotations

import subprocess
from pathlib import Path
import pytest

@pytest.fixture
def fake_repo(tmp_path: Path) -> Path:
    """A plain git project, as orkcraft finds it anywhere: a README, some code, docs, loot."""
    repo = tmp_path / "project"
    (repo / "src").mkdir(parents=True)
    (repo / "docs").mkdir()
    (repo / "loot").mkdir()
    (repo / "README.md").write_text("# Demo project\n\nA small project for the tests.\n", encoding="utf-8")
    (repo / "src" / "app.py").write_text("print('hello')\n", encoding="utf-8")
    (repo / "docs" / "notes.md").write_text("# Notes\n\n- first note\n", encoding="utf-8")
    (repo / "loot" / "report.md").write_text("# Report\n", encoding="utf-8")
    subprocess.run(["git", "init"], cwd=str(repo), check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@orkcraft.local"], cwd=str(repo), check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test Runner"], cwd=str(repo), check=True, capture_output=True)
    subprocess.run(["git", "add", "."], cwd=str(repo), check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Initial test commit"], cwd=str(repo), check=True, capture_output=True)
    return repo


@pytest.fixture(autouse=True)
def isolated_layout_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Keep window layouts written by the TUI out of the real ~/.config."""
    path = tmp_path / "orkcraft-layout.json"
    monkeypatch.setenv("ORKCRAFT_LAYOUT_FILE", str(path))
    monkeypatch.setenv("ORKCRAFT_SETTINGS_FILE", str(tmp_path / "orkcraft-settings.json"))
    # No real claude/agy calls and no personal calendars in tests.
    monkeypatch.setenv("ORKCRAFT_LIMITS", "0")
    monkeypatch.setenv("ORKCRAFT_COUNCIL_LLM", "0")      # the Council's Fast Path: rules only
    monkeypatch.setenv("ORKCRAFT_CALENDARS_FILE", str(tmp_path / "calendars.json"))
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))
    # The window-manager tests predate the town view (T1102): they run in tiles; test_town.py opts in.
    from orkcraft import scroll
    monkeypatch.setattr(scroll, "DEFAULT_VIEW", "tiles")
    # They also predate the camp that starts with the Town Hall alone (T1107): every preset stands.
    monkeypatch.setattr(scroll, "STARTING", None)
    return path
