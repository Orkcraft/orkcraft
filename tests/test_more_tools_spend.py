"""🪙 and ⏳ for Hermes, pi and Cursor (sources/telemetry.py, quota/hermes_quota.py, sources/limits.py)."""
from __future__ import annotations

import datetime as dt
import json
import sqlite3
from pathlib import Path

from orkcraft.quota import hermes_quota
from orkcraft.sources import limits, telemetry


def _log(repo: Path, *entries: dict) -> None:
    (repo / ".orkcraft").mkdir(exist_ok=True)
    (repo / ".orkcraft" / "sessions.jsonl").write_text("".join(json.dumps(e) + "\n" for e in entries))


def test_pi_and_hermes_sessions_count_their_own_price(tmp_path: Path, monkeypatch):
    run, started = "a" * 32, dt.datetime.now().astimezone() - dt.timedelta(minutes=5)
    later = (started + dt.timedelta(minutes=1)).isoformat()
    pi = tmp_path / "pi.jsonl"
    pi.write_text("\n".join(json.dumps(e) for e in (
        {"type": "session", "version": 3, "id": "p1"},
        {"type": "message", "id": "m0", "timestamp": "2020-01-01T00:00:00Z", "message": {"role": "assistant",
         "usage": {"input": 1, "cost": {"total": 9.0}}}},
        {"type": "message", "id": "m1", "timestamp": later, "message": {"role": "assistant", "model": "sonnet",
         "usage": {"input": 100, "cacheRead": 50, "cacheWrite": 0, "cost": {"total": 0.25}}}},
))
    + "\n")
    home = tmp_path / "hermes"
    home.mkdir()
    con = sqlite3.connect(home / "state.db")
    con.execute("CREATE TABLE sessions (id TEXT PRIMARY KEY, estimated_cost_usd REAL, started_at REAL, model TEXT,"
                " input_tokens INTEGER, cache_read_tokens INTEGER)")
    con.execute("INSERT INTO sessions VALUES ('h1', 0.5, ?, 'm', 10, 5)", (started.timestamp() + 1,))
    con.commit()
    con.close()
    monkeypatch.setenv("HERMES_HOME", str(home))
    _log(tmp_path, {"run": run, "terminal": "t1", "harness": "pi", "session": "p1", "transcript": str(pi)},
         {"run": run, "terminal": "t2", "harness": "hermes", "session": "h1"},
         {"run": run, "terminal": "t3", "harness": "cursor", "session": "c1"})
    telemetry.reset_charges()
    snap = telemetry.Telemetry(tmp_path, run, started).refresh()
    assert round(snap.spent_usd, 4) == 0.75                         # the old message of pi is not this run's
    assert snap.cost_by_terminal == {"t1": 0.25, "t2": 0.5} and snap.context_by_terminal["t1"] == 150
    assert snap.unpriced == {"cursor"}


def test_hermes_usage_becomes_windows():
    data = {"provider": "openai-codex", "title": "ChatGPT", "plan": "plus",
            "windows": [{"label": "5h", "used_percent": 40, "resets_at": "2026-10-07T18:00:00Z"}]}
    rows = hermes_quota.get_hermes_quota(runner=lambda cmd, timeout=0: json.dumps(data))
    assert [(r.group, r.window, r.remaining_fraction, r.note) for r in rows] == [("ChatGPT", "5h", 0.6, "plus")]
    assert hermes_quota.parse({"windows": [], "unavailable_reason": "no OAuth"})[0].error == "no OAuth"


def test_cursor_sign_in_token_is_never_read(tmp_path: Path, monkeypatch):
    """decisions-2026-10.md §5: Cursor's stored login is not read and its private API not called."""
    import importlib.util
    assert importlib.util.find_spec("orkcraft.quota.cursor_quota") is None
    src = Path(limits.__file__).read_text(encoding="utf-8")
    assert "auth.json" not in src and "cursor.sh" not in src
    monkeypatch.setattr(limits, "_on_path", lambda h: "/bin/cursor-agent" if h == "cursor" else None)
    rows = limits._cursor(timeout=1)
    assert len(rows) == 1 and rows[0].remaining_fraction is None and "not read" in rows[0].note
    monkeypatch.setattr(limits, "_on_path", lambda h: None)
    assert limits._cursor(timeout=1) == []
