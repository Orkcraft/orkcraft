"""🪙 and ⏳ for Hermes, pi and Cursor (sources/telemetry.py, quota/hermes_quota.py, quota/cursor_quota.py)."""
from __future__ import annotations

import datetime as dt
import io
import json
import sqlite3
from pathlib import Path

from orkcraft.quota import cursor_quota, hermes_quota
from orkcraft.sources import telemetry


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


def test_cursor_plan_is_read_with_the_stored_login_only(tmp_path: Path):
    (tmp_path / ".config" / "cursor").mkdir(parents=True)
    (tmp_path / ".config" / "cursor" / "auth.json").write_text('{"accessToken": "tok"}')
    sent = []

    class Resp(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def opener(req, timeout=0):
        sent.append(req)
        return Resp(json.dumps({"billingCycleEnd": "1798761600000",
                                "planUsage": {"totalPercentUsed": 25, "apiPercentUsed": 10}}).encode())
    rows = cursor_quota.get_cursor_quota(env={}, home=tmp_path, opener=opener)
    assert [(r.window, r.remaining_fraction) for r in rows] == [("month", 0.75), ("month · API", 0.9)]
    assert rows[0].reset_time.year == 2027 and sent[0].get_header("Authorization") == "Bearer tok"
    assert cursor_quota.get_cursor_quota(env={"CURSOR_API_KEY": "k"}, home=tmp_path, opener=opener)[0].note
    assert len(sent) == 1                                            # never with a key in place of the login
