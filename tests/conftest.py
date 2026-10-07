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
    monkeypatch.setenv("ORKCRAFT_ONBOARDING", "0")      # test_onboarding.py opts in
    monkeypatch.setenv("ORKCRAFT_SETTINGS_FILE", str(tmp_path / "orkcraft-settings.json"))
    monkeypatch.setenv("ORKCRAFT_LOGINS_FILE", str(tmp_path / "orkcraft-logins.json"))   # never the keychain
    # No real claude/agy calls and no personal calendars in tests.
    monkeypatch.setenv("ORKCRAFT_LIMITS", "0")
    monkeypatch.setenv("ORKCRAFT_COUNCIL_LLM", "0")      # the Council's Fast Path: rules only
    monkeypatch.setenv("ORKCRAFT_WIKI_AUTO", "0")        # no librarian starts by itself (test_wiki.py opts in)
    monkeypatch.setenv("ORKCRAFT_CALENDARS_FILE", str(tmp_path / "calendars.json"))
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))
    monkeypatch.setenv("ORKCRAFT_NO_USAGE", "1")         # no usage stats leave a test (test_usage.py opts in)
    monkeypatch.setenv("ORKCRAFT_NO_UPDATE", "1")        # no test reads the list of updates (test_updates.py opts in)
    # agy's global hooks file stays the test's own: `hooks install` / `uninstall` never touch ~/.gemini.
    from orkcraft.hooks import install as hooks_install
    monkeypatch.setattr(hooks_install, "agy_global_file", lambda: tmp_path / "gemini" / "config" / "hooks.json")
    # The window-manager tests predate the town view (T1102): they run in tiles; test_town.py opts in.
    from orkcraft import scroll
    monkeypatch.setattr(scroll, "DEFAULT_VIEW", "tiles")
    # They also predate the camp that starts with the Town Hall alone (T1107): every preset stands.
    monkeypatch.setattr(scroll, "STARTING", None)
    return path


@pytest.fixture(autouse=True)
def fresh_spend_ledger():
    """The side 🪙 ledger is process-wide: every test starts from an empty one."""
    from orkcraft.sources import telemetry
    telemetry.reset_charges()
    yield
    telemetry.reset_charges()


@pytest.fixture(autouse=True)
def fresh_halt_registry():
    """🛑 Halt All's registry is process-wide: every test starts with nothing running and no halt."""
    from orkcraft.realm import halt
    halt.reset()
    yield
    halt.reset()


@pytest.fixture
def codex_limits(monkeypatch):
    """`codex_limits(billing=...)`: the real `fetch_limits`, with claude and agy answering a sample and
    Codex its recorded app-server reply (tests/fixtures/codex_app_server_rate_limits.jsonl) at 12:00 UTC."""
    return lambda billing="subscription": _codex_beside_claude_and_agy(monkeypatch, billing)


def _codex_beside_claude_and_agy(monkeypatch, billing: str) -> None:
    from datetime import datetime, timezone

    from orkcraft import tools
    from orkcraft.quota import codex_quota
    from orkcraft.quota.models import QuotaStatus
    from orkcraft.sources import limits

    soon = datetime.now(timezone.utc).replace(microsecond=0)
    raw = (Path(__file__).parent / "fixtures" / "codex_app_server_rate_limits.jsonl").read_text(encoding="utf-8")
    monkeypatch.setenv("ORKCRAFT_LIMITS", "1")
    monkeypatch.setattr("orkcraft.quota.claude_quota.get_claude_quota",
                        lambda **k: [QuotaStatus("claude", "session", "session", 0.86, soon)])
    monkeypatch.setattr("orkcraft.quota.agy_quota.get_agy_quota",
                        lambda **k: [QuotaStatus("agy", "pro", "daily", 0.4, soon)])
    monkeypatch.setattr(limits, "which", lambda name: "/usr/bin/codex" if name == "codex" else None)
    monkeypatch.setattr(tools, "codex_login", lambda path: (True, billing))
    monkeypatch.setattr(codex_quota, "_converse", lambda cmd, messages, timeout, cwd: raw)
    monkeypatch.setattr(codex_quota, "datetime", type("D", (datetime,), {"now": staticmethod(
        lambda tz=None: datetime(2026, 10, 6, 12, 0, tzinfo=timezone.utc))}))


# -- the live bench (tests/live/, docs/testing.md) ----------------------------------------------------

def pytest_addoption(parser):
    parser.addoption("--live", action="store_true", help="run tests/live/ on real models (they cost money)")
    parser.addoption("--refresh-fixtures", action="store_true",
                     help="with --live: write what the real tools printed to tests/fixtures/")


def pytest_collection_modifyitems(config, items):
    if config.getoption("--live"):
        return
    skip = pytest.mark.skip(reason="a real model: run with --live")
    for item in items:
        if "live" in item.keywords:
            item.add_marker(skip)
