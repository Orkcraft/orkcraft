"""orkcraft.quota.codex_quota: the app-server answer, every rollout shape, the plain rows.

No real Codex runs: a fake runner answers recorded JSON-RPC lines, or a tiny script plays app-server.
"""
from __future__ import annotations

import json
import os
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

from orkcraft.quota import codex_quota
from orkcraft.quota.codex_quota import from_rollouts, get_codex_quota, parse_app_server

FIXTURES = Path(__file__).parent / "fixtures"
NOW = datetime(2026, 10, 6, 12, 0, tzinfo=timezone.utc)


def _answer(name: str):
    raw = (FIXTURES / name).read_text(encoding="utf-8")
    seen: list = []

    def runner(cmd, messages, timeout, cwd):
        seen.append((cmd, messages))
        return raw
    return runner, seen


def _rollout(home: Path, fixture: str, day: str = "2026/10/06", name: str = "") -> Path:
    folder = home / "sessions" / day
    folder.mkdir(parents=True, exist_ok=True)
    dest = folder / (name or f"rollout-2026-10-06T10-00-00-{fixture.removesuffix('.jsonl')}.jsonl")
    shutil.copy(FIXTURES / fixture, dest)
    return dest


def test_app_server_answer_gives_each_window(tmp_path):
    runner, seen = _answer("codex_app_server_rate_limits.jsonl")
    rows = get_codex_quota("codex", runner=runner, home=tmp_path, now=NOW)
    cmd, messages = seen[0]
    assert cmd == ["codex", "app-server"]
    assert [m.get("method") for m in messages] == ["initialize", "initialized", "account/rateLimits/read"]
    assert messages[0]["params"]["clientInfo"]["name"] == "orkcraft"
    assert all(r.provider == "codex" and r.error is None for r in rows)
    five, week, astra = rows       # the notifications before the answer are not the answer
    assert (five.window, five.group, five.remaining_fraction) == ("5h", "", pytest.approx(0.62))
    assert five.reset_time == datetime(2026, 10, 6, 15, 0, tzinfo=timezone.utc)
    assert five.note == "plus · credits 120"
    assert (week.window, week.remaining_fraction) == ("weekly", pytest.approx(0.875))
    assert week.reset_time == datetime(2026, 10, 10, 8, 0, tzinfo=timezone.utc)
    assert (astra.window, astra.group, astra.remaining_fraction) == ("", "gpt-6-astra 5h", pytest.approx(0.1))


def test_app_server_without_buckets_reads_rate_limits():
    line = {"id": 2, "result": {"rateLimits": {"primary": {"usedPercent": 50, "windowDurationMins": 120,
                                                          "resetsAt": None}, "secondary": None}}}
    (row,) = parse_app_server(json.dumps(line), now=NOW)
    assert (row.window, row.remaining_fraction, row.reset_time, row.note) == ("2h", 0.5, None, "")


def test_api_key_login_answers_plainly(tmp_path):
    runner, _ = _answer("codex_app_server_apikey.jsonl")
    (row,) = get_codex_quota("codex", runner=runner, home=tmp_path, now=NOW)
    assert row.error == "API key — no plan windows" and row.remaining_fraction is None


def test_api_billing_runs_nothing(tmp_path):
    def runner(*a, **k):
        raise AssertionError("app-server must not run for an API key")
    (row,) = get_codex_quota("codex", runner=runner, home=tmp_path, billing="api")
    assert row.error == codex_quota.API_KEY


def test_not_installed_is_one_plain_row(tmp_path):
    (row,) = get_codex_quota(str(tmp_path / "no-codex-here"), home=tmp_path, timeout=5)
    assert row.error == "not installed"


@pytest.mark.parametrize("fixture, left, resets", [
    ("codex_rollout_flat.jsonl", (0.8, 0.45), (None, None)),
    ("codex_rollout_resets_in.jsonl", (0.7, 0.4),
     (datetime(2026, 10, 6, 13, 0, 5, tzinfo=timezone.utc), datetime(2026, 10, 7, 10, 0, 5, tzinfo=timezone.utc))),
    ("codex_rollout_resets_rfc3339.jsonl", (0.55, 0.3),
     (datetime(2026, 10, 6, 14, 0, tzinfo=timezone.utc), datetime(2026, 10, 9, 9, 0, tzinfo=timezone.utc))),
])
def test_rollout_shapes(tmp_path, fixture, left, resets):
    _rollout(tmp_path, fixture)
    rows = from_rollouts(tmp_path, now=NOW)
    assert [r.window for r in rows] == ["5h", "weekly"]
    assert [r.remaining_fraction for r in rows] == [pytest.approx(x) for x in left]
    assert [r.reset_time for r in rows] == list(resets)
    assert all(r.note.startswith("as of ") for r in rows)


def test_rollout_unix_seconds_with_plan(tmp_path):
    _rollout(tmp_path, "codex_rollout.jsonl", day="2026/10/05", name="rollout-2026-10-05T09-00-00-a.jsonl")
    (row,) = from_rollouts(tmp_path, now=datetime(2026, 10, 5, 10, 0, tzinfo=timezone.utc))
    assert (row.window, row.remaining_fraction) == ("5h", pytest.approx(0.96))
    assert row.reset_time == datetime.fromtimestamp(1791200000, timezone.utc)
    assert row.note.startswith("plus · as of ")
    (later,) = from_rollouts(tmp_path, now=NOW)          # the window turned over since
    assert (later.remaining_fraction, later.reset_time) == (1.0, None)


def test_rollout_newest_file_with_limits_wins(tmp_path):
    _rollout(tmp_path, "codex_rollout_flat.jsonl", day="2026/10/05", name="rollout-2026-10-05T10-00-00-old.jsonl")
    newest = tmp_path / "sessions" / "2026" / "10" / "06" / "rollout-2026-10-06T11-00-00-new.jsonl"
    newest.parent.mkdir(parents=True)
    newest.write_text('{"type": "event_msg", "payload": {"type": "token_count", "rate_limits": null}}\n')
    _rollout(tmp_path, "codex_rollout_resets_in.jsonl", name="rollout-2026-10-06T10-00-00-mid.jsonl")
    assert [r.remaining_fraction for r in from_rollouts(tmp_path, now=NOW)] == [pytest.approx(0.7), pytest.approx(0.4)]


def test_rollout_zst_is_read_when_zstandard_is_there(tmp_path):
    zstandard = pytest.importorskip("zstandard")
    folder = tmp_path / "sessions" / "2026" / "10" / "06"
    folder.mkdir(parents=True)
    raw = (FIXTURES / "codex_rollout_flat.jsonl").read_bytes()
    (folder / "rollout-2026-10-06T10-00-00-z.jsonl.zst").write_bytes(zstandard.ZstdCompressor().compress(raw))
    assert [r.remaining_fraction for r in from_rollouts(tmp_path, now=NOW)] == [pytest.approx(0.8), pytest.approx(0.45)]


def test_app_server_failure_falls_back_to_rollouts(tmp_path):
    _rollout(tmp_path, "codex_rollout_flat.jsonl")

    def runner(cmd, messages, timeout, cwd):
        return '{"id": 2, "error": {"code": -32601, "message": "unknown method"}}\n'   # Codex before 0.53
    rows = get_codex_quota("codex", runner=runner, home=tmp_path, now=NOW)
    assert [r.window for r in rows] == ["5h", "weekly"] and rows[0].note.startswith("as of ")


def test_nothing_read_says_why(tmp_path):
    def runner(cmd, messages, timeout, cwd):
        return ""
    (row,) = get_codex_quota("codex", runner=runner, home=tmp_path, now=NOW)
    assert row.error == "no windows read (no answer from codex app-server)"


@pytest.mark.skipif(os.name == "nt", reason="a POSIX script plays codex")
def test_real_conversation_with_a_fake_app_server(tmp_path):
    """The stdio exchange itself: answers come one request at a time, the server never exits by itself."""
    answer = (FIXTURES / "codex_app_server_rate_limits.jsonl").read_text(encoding="utf-8").splitlines()
    fake = tmp_path / "codex"
    fake.write_text(f"""#!{sys.executable}
import json, sys, time
assert sys.argv[1:] == ["app-server"]
answer = {answer!r}
for line in sys.stdin:
    msg = json.loads(line)
    if msg.get("method") == "initialize":
        print(answer[0], flush=True)
    elif msg.get("method") == "account/rateLimits/read":
        assert msg["id"] == 2
        print("\\n".join(answer[1:]), flush=True)
time.sleep(60)
""")
    fake.chmod(0o755)
    rows = get_codex_quota(str(fake), timeout=20, home=tmp_path, now=NOW)
    assert [r.remaining_fraction for r in rows] == [pytest.approx(0.62), pytest.approx(0.875), pytest.approx(0.1)]


@pytest.mark.skipif(os.name == "nt", reason="a POSIX script plays codex")
def test_silent_app_server_times_out(tmp_path):
    fake = tmp_path / "codex"
    fake.write_text(f"#!{sys.executable}\nimport time\ntime.sleep(60)\n")
    fake.chmod(0o755)
    (row,) = get_codex_quota(str(fake), timeout=1, home=tmp_path, now=NOW)
    assert row.error == "no windows read (app-server timed out after 1s)"


# --- sources.limits: the Codex row next to claude and agy ----------------------------------------

def _no_others(monkeypatch):
    monkeypatch.setenv("ORKCRAFT_LIMITS", "1")
    monkeypatch.setattr("orkcraft.quota.claude_quota.get_claude_quota", lambda **k: [])
    monkeypatch.setattr("orkcraft.quota.agy_quota.get_agy_quota", lambda **k: [])


def test_limits_say_codex_is_not_installed(monkeypatch, tmp_path):
    from orkcraft.sources import limits
    _no_others(monkeypatch)
    monkeypatch.setattr(limits, "which", lambda name: None)
    assert limits.fetch_limits(tmp_path) == [limits.Limit("codex", "", "", None, None, "not installed")]


def test_limits_say_codex_runs_on_an_api_key(monkeypatch, tmp_path):
    from orkcraft import tools
    from orkcraft.sources import limits
    _no_others(monkeypatch)
    monkeypatch.setattr(limits, "which", lambda name: "/usr/bin/codex" if name == "codex" else None)
    monkeypatch.setattr(tools, "codex_login", lambda path: (True, "api"))
    monkeypatch.setattr(codex_quota, "_converse", lambda *a: pytest.fail("no app-server for an API key"))
    (row,) = limits.fetch_limits(tmp_path)
    assert (row.provider, row.error) == ("codex", "API key — no plan windows")


def test_limits_carry_codex_windows(monkeypatch, tmp_path):
    from orkcraft import tools
    from orkcraft.sources import limits
    _no_others(monkeypatch)
    raw = (FIXTURES / "codex_app_server_rate_limits.jsonl").read_text(encoding="utf-8")
    monkeypatch.setattr(limits, "which", lambda name: "/usr/bin/codex" if name == "codex" else None)
    monkeypatch.setattr(tools, "codex_login", lambda path: (True, "subscription"))
    monkeypatch.setattr(codex_quota, "_converse", lambda cmd, messages, timeout, cwd: raw)
    parse = codex_quota.parse_app_server        # read at the fixture's hour, not the clock's: its 5h window resets at 15:00
    monkeypatch.setattr(codex_quota, "parse_app_server", lambda out, *a, **k: parse(out, *a, **{**k, "now": NOW}))
    rows = limits.fetch_limits(tmp_path)
    assert [(r.provider, r.window, r.group) for r in rows] == [
        ("codex", "5h", ""), ("codex", "weekly", ""), ("codex", "", "gpt-6-astra 5h")]
    assert rows[0].note == "plus · credits 120" and rows[0].reset.tzinfo is None
    assert limits.PROVIDERS == ("claude", "agy", "codex", "hermes", "pi", "cursor")
