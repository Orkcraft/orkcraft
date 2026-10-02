"""Unit tests for the data sources behind the windows (no Textual)."""
from __future__ import annotations

import datetime as dt
import json
import time
from pathlib import Path

from orkcraft.sources.agents import collect_agents, scan_runs
from orkcraft.sources.ics import CalendarSource, load_events, load_sources, parse_ics
from orkcraft.sources.systems import discover_systems, scheme_lines

D = dt.date


def _write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


# -- systems & agents ------------------------------------------------------------------

def _system(repo: Path) -> None:
    root = repo / "studio"
    _write(root / "pipelines" / "README.md", "| # | Spec |\n|---|---|\n| 2 | `b.json` |\n| 1 | `a.json` |\n")
    _write(root / "pipelines" / "a.json", json.dumps({
        "name": "a", "description": "first", "defaults": {"model": "gem-pro"},
        "steps": [
            {"id": "x", "agent": "writer", "outputs": ["o"]},
            {"id": "y", "agent": "critic", "model": "claude-x", "outputs": ["o"]},
            {"id": "z", "agent": "writer", "after": ["x", "y"], "outputs": ["o"]},
            {"id": "gate", "run": "make gate", "after": ["loop"]},
        ],
        "groups": [{"id": "loop", "after": ["z"], "items_from": "items.json", "sequential": True,
                    "steps": [{"id": "code", "agent": "coder", "outputs": ["o"]},
                              {"id": "test", "agent": "tester", "after": ["code"], "outputs": ["o"]}],
                    "review_loops": [{"review": "test", "fix": "code", "max_rounds": 2}]}],
        "review_loops": [{"review": "y", "fix": "x", "max_rounds": 2, "on_cap": "stop"}],
    }))
    _write(root / "pipelines" / "b.json", json.dumps({"name": "b", "steps": []}))
    _write(root / ".agents" / "agents" / "writer.md", "<!-- why -->\n---\nname: writer\nmodel: Gemini Flash\n---\nbody")


def test_systems_order_waves_and_scheme(tmp_path: Path):
    _system(tmp_path)
    [sysm] = discover_systems(tmp_path)
    assert [s.name for s in sysm.stages] == ["a", "b"]
    stage = sysm.stages[0]
    waves = [[s.id for s in w] for w in stage.waves()]
    assert waves == [["x", "y"], ["z"], ["loop"], ["gate"]]
    text = "\n".join(scheme_lines(stage))
    assert "wave 1  ∥ parallel" in text
    assert "critic  [agy · claude-x]" in text and "writer  [agy · gem-pro]" in text
    assert "script `make gate`" in text
    assert "for each item of `items.json` (one item at a time)" in text
    assert "⇄ y ↔ x" in text and "⇄ test ↔ code" in text


def test_agents_models_activity_and_queue(tmp_path: Path):
    _system(tmp_path)
    run = tmp_path / "studio" / ".chain" / "a_20260928_101500"
    _write(run / "x.1.brief.md", "b")
    _write(run / "x.1.out.txt", "rc=0")
    _write(run / "y.1.brief.md", "b")  # running: no output yet
    runs = scan_runs(tmp_path / "studio")
    assert runs[0].running == ["y"] and not runs[0].finished

    agents = {a.name: a for a in collect_agents(tmp_path)}
    assert agents["writer"].declared_model == "Gemini Flash"
    assert agents["writer"].models == ["gem-pro"]
    assert agents["critic"].doing == ["a/y"]
    assert agents["writer"].queue == ["a/z"]  # x done, z never started
    assert set(agents["coder"].queue) == {"a/code"}

    (run / "run.md").write_text("# done", encoding="utf-8")
    agents = {a.name: a for a in collect_agents(tmp_path)}
    assert agents["critic"].doing == [] and agents["writer"].queue == []


def test_stale_run_without_summary_is_not_active(tmp_path: Path):
    _system(tmp_path)
    run = tmp_path / "studio" / ".chain" / "a_20260101_000000"
    _write(run / "y.1.brief.md", "b")
    assert scan_runs(tmp_path / "studio", now=time.time() + 13 * 3600)[0].finished


# -- calendar -----------------------------------------------------------------------------

ICS = """BEGIN:VCALENDAR
BEGIN:VEVENT
SUMMARY:Standup\\, daily
DTSTART;TZID=Europe/Berlin:20260928T093000
DTEND;TZID=Europe/Berlin:20260928T094500
RRULE:FREQ=WEEKLY;BYDAY=MO,WE;COUNT=3
EXDATE;TZID=Europe/Berlin:20260930T093000
END:VEVENT
BEGIN:VEVENT
SUMMARY:Holiday
DTSTART;VALUE=DATE:20261003
DTEND;VALUE=DATE:20261004
END:VEVENT
BEGIN:VEVENT
SUMMARY:Cancelled
STATUS:CANCELLED
DTSTART:20260929T100000Z
END:VEVENT
BEGIN:VEVENT
SUMMARY:Long
 folded line
DTSTART:20261001T120000Z
END:VEVENT
END:VCALENDAR
"""


def test_ics_rrule_exdate_allday_cancel_and_folding():
    events = parse_ics(ICS, "cal", D(2026, 9, 28), D(2026, 10, 11))
    by = {}
    for e in events:
        by.setdefault(e.summary, []).append(e)
    standups = by["Standup, daily"]
    # Mon 28, (Wed 30 excluded), Mon 5 — COUNT=3 counts the excluded one too.
    assert [e.day for e in standups] == [D(2026, 9, 28), D(2026, 10, 5)]
    assert by["Holiday"][0].all_day and by["Holiday"][0].day == D(2026, 10, 3)
    assert "Cancelled" not in by
    assert "Longfolded line" in by


def test_calendar_sources_and_cache(tmp_path: Path, monkeypatch):
    ics = _write(tmp_path / "cal.ics", ICS)
    cfg = _write(tmp_path / "calendars.json", json.dumps([{"name": "Local", "path": str(ics)}, {"bad": 1}]))
    monkeypatch.setenv("ORKCRAFT_CALENDARS_FILE", str(cfg))
    assert [s.name for s in load_sources()] == ["Local"]
    events, errors = load_events(D(2026, 9, 28), D(2026, 9, 28))
    assert errors == [] and [e.summary for e in events] == ["Standup, daily"]

    # An unreachable URL with no cache reports an error instead of raising.
    events, errors = load_events(D(2026, 9, 28), D(2026, 9, 28),
                                 [CalendarSource("Net", url="http://127.0.0.1:9/nothing.ics")])
    assert events == [] and errors and errors[0].startswith("Net:")
