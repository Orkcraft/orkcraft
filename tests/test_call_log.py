"""The Test bench's log of model calls (realm/call_log.py): kept only inside a bench run, a line and the call each."""
from __future__ import annotations

import dataclasses
import datetime as dt
import io
import json
import threading
import urllib.error
import urllib.request
import zipfile

import pytest

from orkcraft.realm import call_log, day_log, jobs, road_agents

ENVELOPE = json.dumps({"result": "done", "total_cost_usd": 0.03, "session_id": "s1",
                       "usage": {"input_tokens": 900, "output_tokens": 100, "cache_read_input_tokens": 4000}})


@pytest.fixture
def tool(monkeypatch):
    seen = {}

    def run_proc(cmd, cwd, env, stdin, wait, harness=""):
        seen["env"] = env
        return seen.get("code", 0), seen.get("out", ENVELOPE), "a warning"

    monkeypatch.setattr(road_agents, "run_proc", run_proc)
    return seen


def test_outside_a_bench_run_no_call_is_kept(tmp_path, tool):
    jobs.run_work("claude", "do it", tmp_path, threading.Event())
    assert not list(tmp_path.rglob(call_log.LINES))


def test_a_call_in_a_bench_run_keeps_its_line_and_itself(tmp_path, tool):
    with call_log.kept(tmp_path / "calls", "building"):
        jobs.run_work("claude", "fix the tests", tmp_path, threading.Event(), "sonnet",
                      env={"ORKCRAFT_ORC": "pool/Grub", "SECRET_KEY": "x"})
    jobs.run_work("claude", "after the run", tmp_path, threading.Event())          # no longer kept
    [line] = call_log.read(tmp_path / "calls")
    assert (line["side"], line["who"], line["mode"], line["tool"], line["model"]) == \
        ("building", "Grub", "work", "claude", "sonnet")
    assert (line["code"], line["cost"], line["tokens"]) == (0, 0.03, 5000)
    assert line["usage"] == {"input_tokens": 900, "output_tokens": 100, "cache_read_input_tokens": 4000}
    raw = call_log.raw(tmp_path / "calls", line)
    assert raw["prompt"] == "fix the tests" and raw["stdout"] == ENVELOPE and raw["stderr"] == "a warning"
    assert "SECRET_KEY" not in (tmp_path / "calls" / call_log.LINES).read_text()


def test_a_call_that_fails_is_kept_too(tmp_path, tool):
    tool.update(code=1, out="not logged in")
    with call_log.kept(tmp_path / "calls", "bare"), pytest.raises(RuntimeError):
        jobs.run_read("claude", "read it", tmp_path, threading.Event())
    [line] = call_log.read(tmp_path / "calls")
    assert (line["side"], line["who"], line["mode"], line["code"], line["tokens"]) == ("bare", "", "read", 1, None)


def test_the_calls_add_up_by_side_who_and_purpose(tmp_path, tool):
    with call_log.kept(tmp_path / "calls", "building"):
        for who in ("Grub", "Grub", "steward"):
            jobs.run_work("claude", "x", tmp_path, threading.Event(), env={"ORKCRAFT_ORC": f"pool/{who}"})
    with call_log.kept(tmp_path / "calls", "bare"):                   # a second block goes on numbering
        jobs.run_work("claude", "x", tmp_path, threading.Event())
    lines = call_log.read(tmp_path / "calls")
    assert [x["n"] for x in lines] == [1, 2, 3, 4] and len({x["raw"] for x in lines}) == 4
    rows = {(t["side"], t["who"]): t for t in call_log.totals(lines)}
    assert rows[("building", "Grub")]["calls"] == 2 and rows[("building", "Grub")]["tokens"] == 10000
    assert rows[("building", "Grub")]["usage"]["input_tokens"] == 1800
    assert rows[("bare", "")]["calls"] == 1


def test_the_usage_is_read_from_an_envelope_or_the_last_event():
    assert call_log.usage_of(ENVELOPE)["output_tokens"] == 100
    lines = "\n".join(json.dumps(e) for e in ({"type": "turn.completed", "usage": {"input_tokens": 1}},
                                              {"type": "turn.completed", "usage": {"input_tokens": 7, "output_tokens": 2}}))
    assert call_log.usage_of(lines) == {"input_tokens": 7, "output_tokens": 2}
    assert call_log.usage_of("plain text") == {}


# -- the town's day logs (realm/day_log.py, gui/day_logs.py) --------------------------------------------------

@pytest.fixture(autouse=True)
def no_day_log():
    call_log.keep_days(None)
    yield
    call_log.keep_days(None)


def test_outside_a_bench_run_a_call_goes_to_its_buildings_day(tmp_path, tool):
    call_log.keep_days(tmp_path)
    jobs.run_work("claude", "fix it", tmp_path, threading.Event(), env={"ORKCRAFT_ORC": "pool/Grub"})
    road_agents.run_agent("claude", "sort it", tmp_path, {"ORKCRAFT_ORC": "pool/steward"}, threading.Event())
    jobs.run_read("claude", "nobody's", tmp_path, threading.Event())
    today = dt.date.today().isoformat()
    lines = call_log.read(call_log.day_folder(tmp_path, today, "pool"))
    assert [(x["who"], x["side"], x["mode"]) for x in lines] == [("Grub", "", "work"), ("steward", "", "agent")]
    assert [x["who"] for x in call_log.read(call_log.day_folder(tmp_path, today, call_log.TOWN))] == ["agent"]


def test_a_claude_call_keeps_how_it_worked_from_its_transcript(tmp_path, tool, monkeypatch):
    monkeypatch.setenv("CLAUDE_HOME", str(tmp_path / "claude"))
    from orkcraft.sources import sessions
    work = tmp_path / "wt"
    work.mkdir()
    transcript = sessions.claude_projects_dir(work) / "s1.jsonl"
    transcript.parent.mkdir(parents=True)
    transcript.write_text('{"type": "assistant", "message": {"content": [{"type": "thinking", "thinking": "hmm"}]}}\n')
    with call_log.kept(tmp_path / "calls", "building"):
        jobs.run_work("claude", "fix it", work, threading.Event())                   # its session from the output
    [first] = call_log.read(tmp_path / "calls")
    assert first["session"] == "s1" and '"thinking": "hmm"' in call_log.raw(tmp_path / "calls", first)["trail"]
    assert call_log.trail("claude", "../s1", work) == ""                         # a session id, never a path
    assert call_log.trail("codex", "s1", work) == ""                             # its output holds how it went


def _day(root, day, building, asked=False):
    folder = call_log.day_folder(root, day, building)
    folder.mkdir(parents=True)
    (folder / call_log.LINES).write_text("{}\n")
    if asked:
        (folder / day_log.ASKED).touch()
    return folder


def test_a_day_nobody_asked_for_and_nobody_disliked_is_cleared_the_next_morning(tmp_path):
    today = dt.date(2026, 10, 12)
    kept = [_day(tmp_path, "2026-10-11", "asked", asked=True), _day(tmp_path, "2026-10-11", "disliked"),
            _day(tmp_path, "2026-10-12", "today")]
    gone = [_day(tmp_path, "2026-10-11", "plain"), _day(tmp_path, "2026-09-20", "old", asked=True)]
    removed = day_log.clear(tmp_path, today, lambda b, day: b == "disliked" and day == "2026-10-11")
    assert sorted(removed) == ["2026-09-20/old", "2026-10-11/plain"]
    assert all(f.is_dir() for f in kept) and not any(f.exists() for f in gone)
    assert not (tmp_path / call_log.DAYS / "2026-09-20").exists()
    assert day_log.days(tmp_path, "asked") == ["2026-10-11"]


def test_a_buildings_day_is_one_zip_and_asking_for_it_keeps_it(tmp_path, tool):
    call_log.keep_days(tmp_path)
    jobs.run_work("claude", "fix the tests", tmp_path, threading.Event(), env={"ORKCRAFT_ORC": "pool/Grub"})
    today = dt.date.today().isoformat()
    data = day_log.pack(tmp_path, "pool", today, "Agent pool",
                        [{"at": f"{today}T10:00:00", "action": "hire", "orc": "Grub", "why": "first"}])
    z = zipfile.ZipFile(io.BytesIO(data))
    assert sorted(z.namelist()) == ["README.md", "calls.jsonl", "calls/001-Grub.json", "decisions.jsonl"]
    readme = z.read("README.md").decode()
    assert "# Agent pool" in readme and "Grub · work: 1 call" in readme and "hire: Grub — first" in readme
    assert json.loads(z.read("calls/001-Grub.json"))["prompt"] == "fix the tests"
    assert (call_log.day_folder(tmp_path, today, "pool") / day_log.ASKED).exists()


def test_the_town_serves_a_buildings_day_and_clears_by_its_dislikes(fake_repo, isolated_layout_file, tool):
    from orkcraft.gui.host import Host
    from orkcraft.gui.server import Server
    from orkcraft.realm import checkpoint, feedback
    checkpoint.ensure(fake_repo)
    host = Host(fake_repo, auto_commit=False)
    try:
        jobs.run_work("claude", "hall work", fake_repo, threading.Event(), env={"ORKCRAFT_ORC": "town_hall/Chief"})
        server = Server(host)
        server.start_thread()
        try:
            base = f"{server.origin}/api/logs/town_hall"
            with urllib.request.urlopen(f"{base}?t={server.token}", timeout=5) as r:
                assert r.headers["Content-Type"] == "application/zip" and "attachment" in r.headers["Content-Disposition"]
                assert "calls/001-Chief.json" in zipfile.ZipFile(io.BytesIO(r.read())).namelist()
            for bad in (f"{base}?t=nope", f"{server.origin}/api/logs/nobody?t={server.token}",
                        f"{base}?t={server.token}&day=../x"):
                with pytest.raises(urllib.error.HTTPError):
                    urllib.request.urlopen(bad, timeout=5)
        finally:
            server.stop()
        today = dt.date.today()
        yesterday = (today - dt.timedelta(days=1)).isoformat()
        _day(fake_repo, yesterday, "liked_one")
        _day(fake_repo, yesterday, "town_hall")
        incident = feedback.Incident(f"{yesterday}T12:00:00", "town_hall", "logic", "", "")
        feedback._append(feedback._dir(fake_repo) / "incidents.jsonl", dataclasses.asdict(incident))
        host.day_logs.cleared = ""
        host.day_logs.tick(today)
        assert call_log.day_folder(fake_repo, yesterday, "town_hall").is_dir()
        assert not call_log.day_folder(fake_repo, yesterday, "liked_one").exists()
    finally:
        host.close()
