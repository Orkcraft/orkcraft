"""The night gate (docs/specs/32-night-gate.md): a temp repository with `main`, `dev` and a bare origin, a tiny suite
(one browser file among it), a stub `claude` on PATH. The night tests `dev`'s head, its check fixes on `night/<date>`
and lands on `dev` through the gate; only Pass to main moves `main`, to the exact sha the report was made on."""
from __future__ import annotations

import datetime as dt
import json
import os
import stat
import subprocess
import sys
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

from orkcraft.core import night_gate
from orkcraft.core.night_gate import NightGate
from orkcraft.gui import mobile

# STUB_MODE: fix (VALUE = 2, the failing test passes), wrong (VALUE = 3, still red), none (changes nothing),
# notes (changes nothing, says a spec mismatch it could not fix), slow (sleeps). Each call: a line in STUB_LOG.
STUB = r'''#!{python}
import json, os, subprocess, sys, time
mode = os.environ.get("STUB_MODE", "none")
argv = sys.argv[1:]
branch = subprocess.run(["git", "rev-parse", "--abbrev-ref", "HEAD"], capture_output=True, text=True).stdout.strip()
with open(os.environ["STUB_LOG"], "a") as f:
    f.write(json.dumps({"mode": mode, "branch": branch, "resume": "--resume" in argv, "prompt": argv[argv.index("-p") + 1] if "-p" in argv else ""}) + "\n")
if mode == "slow":
    time.sleep(30)
said = {"summary": "all good", "fixed": [], "not_fixed": []}
if mode in ("fix", "wrong"):
    turns = sum(1 for _ in open(os.environ["STUB_LOG"]))
    open("pkg/thing.py", "w").write("VALUE = %d\n" % (2 if mode == "fix" else 2 + turns))
    subprocess.run(["git", "-c", "user.name=S", "-c", "user.email=s@x", "commit", "-qam", "Night: fix VALUE"], check=True)
    said = {"summary": "fixed VALUE", "fixed": ["VALUE is 2, as the idea says"], "not_fixed": []}
if mode == "notes":
    said = {"summary": "one change misses its idea", "fixed": [], "not_fixed": ["dark-mode: the switch is not saved"]}
print(json.dumps({"result": "I looked.\n" + json.dumps(said), "session_id": "s-night",
                  "total_cost_usd": float(os.environ.get("STUB_COST", "0.10")),
                  "usage": {"input_tokens": 10, "output_tokens": 5}}))
'''


def git(cwd: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True).stdout.strip()


def commit(repo: Path, files: dict[str, str], msg: str) -> str:
    for name, text in files.items():
        (repo / name).parent.mkdir(parents=True, exist_ok=True)
        (repo / name).write_text(text)
    git(repo, "add", *files)
    git(repo, "commit", "-qm", msg)
    return git(repo, "rev-parse", "HEAD")


@pytest.fixture
def town(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> SimpleNamespace:
    origin, repo = tmp_path / "origin.git", tmp_path / "repo"
    subprocess.run(["git", "init", "--bare", "-b", "main", str(origin)], check=True, capture_output=True)
    repo.mkdir()
    git(repo, "init", "-b", "main")
    git(repo, "config", "user.email", "t@x")
    git(repo, "config", "user.name", "T")
    ok = "def test_ok():\n    assert True\n"
    commit(repo, {".gitignore": ".orkcraft/\n__pycache__/\n.pytest_cache/\n", "conftest.py": "", "pkg/__init__.py": "",
                  "pkg/thing.py": "VALUE = 2\n", "tests/test_architecture.py": ok, "tests/test_cli.py": ok,
                  "tests/test_updates.py": ok, "tests/test_ui_browser.py": ok,
                  "tests/test_thing.py": "from pkg.thing import VALUE\n\ndef test_value():\n    assert VALUE == 2\n"},
           "start")
    git(repo, "remote", "add", "origin", str(origin))
    git(repo, "push", "-q", "origin", "main")
    git(repo, "checkout", "-qb", "dev")
    commit(repo, {"pkg/extra.py": "X = 1\n"}, "Add extra")
    git(repo, "push", "-q", "origin", "dev")
    git(repo, "checkout", "-q", "main")
    bindir = tmp_path / "bin"
    bindir.mkdir()
    stub = bindir / "claude"
    stub.write_text(STUB.replace("{python}", sys.executable))
    stub.chmod(stub.stat().st_mode | stat.S_IEXEC)
    monkeypatch.setenv("PATH", f"{bindir}{os.pathsep}{os.environ['PATH']}")
    log = tmp_path / "stub.jsonl"
    monkeypatch.setenv("STUB_LOG", str(log))
    state = repo / ".orkcraft"
    (state / "ideas").mkdir(parents=True)
    page = repo / "llm-wiki" / "general" / "pages" / "ideas" / "dark-mode.md"
    page.parent.mkdir(parents=True)
    page.write_text("---\nowner: board\n---\n# Dark mode\n\n## Gist\nA dark mode that stays.\n")
    return SimpleNamespace(repo=repo, origin=origin, state=state, log=log)


def gate_of(town, **settings) -> tuple[NightGate, list]:
    events: list = []
    bus = SimpleNamespace(publish=lambda topic, **data: events.append((topic, data)))
    return NightGate(town.repo, town.state, lambda: settings, bus), events


def calls(town) -> list[dict]:
    return [json.loads(ln) for ln in town.log.read_text().splitlines()] if town.log.exists() else []


def on_dev(town, files: dict[str, str], msg: str) -> str:
    git(town.repo, "checkout", "-q", "dev")
    sha = commit(town.repo, files, msg)
    git(town.repo, "checkout", "-q", "main")
    return sha


TODAY = dt.date.today().isoformat()


def night(gate: NightGate) -> dict:
    assert gate.start(TODAY, wait=True)
    return gate.report(TODAY)


def test_green_night_reports_and_pass_to_main_fast_forwards_and_pushes(town):
    gate, events = gate_of(town)
    dev, main = git(town.repo, "rev-parse", "dev"), git(town.repo, "rev-parse", "main")
    rep = night(gate)
    assert rep["green"] is True and rep["dev"] == dev and rep["main"] == main and not rep["running"]
    assert [s["name"] for s in rep["steps"]] == [night_gate.SUITE, night_gate.BROWSER, night_gate.CHECK]
    assert rep["steps"][0]["summary"].startswith("4 passed") and rep["steps"][1]["summary"].startswith("1 passed")
    assert [c["subject"] for c in rep["commits"]] == ["Add extra"] and rep["cost"] == pytest.approx(0.10)
    assert rep["budget"] == 2.0 and rep["finished"]
    assert git(town.repo, "rev-parse", "main") == main                 # the night never touches main
    assert calls(town)[0]["branch"] == f"night/{TODAY}" and "$2.00" in calls(town)[0]["prompt"]
    assert (town.state / "gate" / "night" / f"{TODAY}.json").is_file() and events
    out = gate.pass_night(TODAY)
    assert out["ok"] and git(town.repo, "rev-parse", "main") == dev
    assert git(town.origin, "rev-parse", "main") == dev
    rep = gate.report(TODAY)
    assert rep["passed_by"] == "you" and rep["passed_at"]
    assert "went to main already" in gate.pass_night(TODAY)["error"]


def test_the_check_reads_the_commits_with_their_ideas_and_the_pages(town):
    sha = on_dev(town, {"pkg/dark.py": "ON = True\n"}, "Dark mode switch")
    base = git(town.repo, "rev-parse", f"{sha}~1")
    (town.state / "ideas" / "merged.jsonl").write_text(json.dumps(
        {"idea": "dark-mode", "task": "k1", "title": "t", "commit": sha, "base": base, "subject": "Dark mode switch"}) + "\n")
    gate, _ = gate_of(town)
    rep = night(gate)
    assert [(c["subject"], c["idea"]) for c in rep["commits"]] == [("Add extra", ""), ("Dark mode switch", "dark-mode")]
    prompt = calls(town)[0]["prompt"]
    assert "(idea: dark-mode)" in prompt and "A dark mode that stays." in prompt and "Quartermaster" in prompt


def test_dev_unchanged_since_the_last_night_does_nothing(town, monkeypatch):
    monkeypatch.delenv("ORKCRAFT_NIGHT_ROUND", raising=False)
    gate, _ = gate_of(town, night_hour=3)
    assert not gate.tick(dt.datetime(2026, 10, 18, 14, 0))             # not the hour
    assert gate.tick(dt.datetime(2026, 10, 18, 3, 0))
    gate.join(60)
    assert gate.report("2026-10-18")["green"]
    assert not gate.tick(dt.datetime(2026, 10, 18, 3, 5))              # once a night
    assert not gate.tick(dt.datetime(2026, 10, 19, 3, 0))              # dev did not move
    assert gate.report("2026-10-19") is None and len(calls(town)) == 1
    on_dev(town, {"pkg/more.py": "Y = 2\n"}, "More")
    assert gate.tick(dt.datetime(2026, 10, 20, 3, 0))
    gate.join(60)
    assert gate.report("2026-10-20") is not None


def test_the_clock_is_off_in_tests_and_in_the_demo(town):
    gate, _ = gate_of(town, night_hour=3)
    assert not gate.tick(dt.datetime(2026, 10, 18, 3, 0))              # ORKCRAFT_NIGHT_ROUND=0, as the Night round
    demo = NightGate(town.repo, town.state, lambda: {}, demo=True)
    with pytest.raises(RuntimeError):
        demo.run_now()


def test_a_red_step_the_check_cannot_fix_is_red_and_not_passed(town, monkeypatch):
    monkeypatch.setenv("STUB_MODE", "none")
    on_dev(town, {"pkg/thing.py": "VALUE = 1\n"}, "Break VALUE")
    gate, _ = gate_of(town)
    main = git(town.repo, "rev-parse", "main")
    rep = night(gate)
    assert rep["green"] is False
    assert rep["steps"][0]["ok"] is False and rep["steps"][0]["failed"] == ["tests/test_thing.py::test_value"]
    assert rep["not_fixed"] == ["tests/test_thing.py::test_value"] and rep["fixed"] == []
    assert "red night" in gate.pass_night(TODAY)["error"]
    assert git(town.repo, "rev-parse", "main") == main
    from orkcraft.gui.night_gate import Night
    assert Night.red(None, gate.card())                                  # it stands in Needs you


def test_a_spec_mismatch_the_check_could_not_fix_makes_the_night_red(town, monkeypatch):
    monkeypatch.setenv("STUB_MODE", "notes")
    rep = night(gate_of(town)[0])
    assert rep["green"] is False and rep["not_fixed"] == ["dark-mode: the switch is not saved"]
    assert rep["steps"][2]["ok"] is False and rep["steps"][2]["summary"] == "one change misses its idea"


def test_the_check_fixes_a_failing_test_on_its_branch_and_it_lands_on_dev_through_the_gate(town, monkeypatch):
    monkeypatch.setenv("STUB_MODE", "fix")
    broke = on_dev(town, {"pkg/thing.py": "VALUE = 1\n"}, "Break VALUE")
    main = git(town.repo, "rev-parse", "main")
    gate, _ = gate_of(town)
    rep = night(gate)
    dev = git(town.repo, "rev-parse", "dev")
    assert dev != broke and git(town.repo, "log", "-1", "--format=%s", "dev") == "Night: fix VALUE"
    assert git(town.origin, "rev-parse", "dev") == dev                  # pushed, as a task lands
    assert rep["green"] is True and rep["dev"] == dev and rep["dev_start"] == broke
    assert "tests/test_thing.py::test_value" in rep["fixed"] and rep["not_fixed"] == []
    assert rep["steps"][0]["ok"] and "after the night's fix" in rep["steps"][0]["summary"]
    assert git(town.repo, "rev-parse", "main") == main                  # never main
    assert gate.pass_night(TODAY)["ok"] and git(town.repo, "rev-parse", "main") == dev


def test_the_check_stops_at_its_budget(town, monkeypatch):
    monkeypatch.setenv("STUB_MODE", "wrong")                            # its fix stays red: it would try again
    monkeypatch.setenv("STUB_COST", "0.30")
    on_dev(town, {"pkg/thing.py": "VALUE = 1\n"}, "Break VALUE")
    dev = git(town.repo, "rev-parse", "dev")
    rep = night(gate_of(town, night_budget_usd=0.25)[0])
    assert len(calls(town)) == 1                                        # no second turn past the budget
    assert rep["cost"] == pytest.approx(0.30) and rep["budget"] == 0.25
    assert rep["green"] is False and rep["steps"][2]["summary"] == "stopped at its budget, $0.25"
    assert git(town.repo, "rev-parse", "dev") == dev                    # a red fix never lands


def test_a_red_fix_gets_one_more_turn_within_the_budget(town, monkeypatch):
    monkeypatch.setenv("STUB_MODE", "wrong")
    on_dev(town, {"pkg/thing.py": "VALUE = 1\n"}, "Break VALUE")
    rep = night(gate_of(town, night_budget_usd=5)[0])
    assert [c["resume"] for c in calls(town)] == [False, True, True]   # CHECK_TURNS, the same session
    assert rep["green"] is False and rep["cost"] == pytest.approx(0.30)


def test_dev_moved_after_the_night_refuses_pass(town):
    gate, _ = gate_of(town)
    night(gate)
    on_dev(town, {"pkg/late.py": "Z = 1\n"}, "Late")
    main = git(town.repo, "rev-parse", "main")
    assert gate.pass_night(TODAY)["error"] == "dev moved since the night; run again"
    assert git(town.repo, "rev-parse", "main") == main and gate.card()["stale"] is True


def test_main_with_commits_of_its_own_gets_a_merge_commit(town):
    gate, _ = gate_of(town)
    night(gate)
    commit(town.repo, {"HOTFIX": "critical\n"}, "Critical release")      # main is checked out in the root
    out = gate.pass_night(TODAY)
    assert out["ok"]
    assert git(town.repo, "log", "-1", "--format=%s", "main") == f"Night gate {TODAY}: dev into main"
    assert git(town.repo, "merge-base", "--is-ancestor", "dev", "main") == "" and (town.repo / "pkg" / "extra.py").exists()


def test_stop_all_stops_the_night_run(town, monkeypatch):
    monkeypatch.setenv("STUB_MODE", "slow")
    gate, _ = gate_of(town)
    main, dev = git(town.repo, "rev-parse", "main"), git(town.repo, "rev-parse", "dev")
    assert gate.start(TODAY)
    end = time.time() + 60
    while time.time() < end and not calls(town):
        time.sleep(0.1)
    gate.stop_all()
    gate.join(20)
    assert not gate.running()
    rep = gate.report(TODAY)
    assert rep["error"] == night_gate.STOPPED and rep["green"] is False and not rep["running"]
    assert git(town.repo, "rev-parse", "main") == main and git(town.repo, "rev-parse", "dev") == dev
    assert not (town.repo / ".orkcraft" / "worktrees" / f"night-{TODAY}").exists()


def test_a_report_cut_off_by_a_closed_town_is_not_green(town):
    folder = town.state / "gate" / "night"
    folder.mkdir(parents=True)
    (folder / f"{TODAY}.json").write_text(json.dumps({"date": TODAY, "dev": "x", "green": True, "running": True}))
    card = NightGate(town.repo, town.state).card()
    assert card["green"] is False and card["running"] is False and "cut off" in card["error"]


def test_outcome_and_verdict_read_pytest_and_the_check():
    out = "F.\nFAILED tests/a.py::test_x - assert 1\n1 failed, 1 passed in 0.1s\n"
    assert night_gate.outcome(1, out) == {"ok": False, "summary": "1 failed, 1 passed in 0.1s",
                                          "failed": ["tests/a.py::test_x"]}
    assert night_gate.outcome(5, "no tests ran")["ok"] is True
    assert night_gate.verdict('blah\n{"summary": "s", "fixed": ["a"], "not_fixed": [1]}') == \
        {"summary": "s", "fixed": ["a"], "not_fixed": ["1"]}
    assert night_gate.verdict("no json") == {"summary": "", "fixed": [], "not_fixed": []}


def test_a_red_night_pushes_once_and_a_green_one_does_not():
    def snap(**night):
        return {"alerts": [], "episodes": [], "idea_states": [], "hud": {}, "night": mobile._night(night) if night else None}
    red = dict(date="2026-10-18", green=False, running=False, passed=False, count=2)
    assert mobile.news(snap(), snap(**{**red, "running": True})) == []
    got = mobile.news(snap(**{**red, "running": True}), snap(**red))
    assert got == [{"kind": "idea", "slug": "night/2026-10-18", "title": "Night report · 2026-10-18", "state": "failed"}]
    assert mobile.news(snap(**red), snap(**red)) == []
    assert mobile.news(snap(), snap(**{**red, "green": True})) == []


def test_a_fix_that_cannot_land_leaves_dev_and_the_night_red(town, monkeypatch):
    monkeypatch.setenv("STUB_MODE", "fix")
    on_dev(town, {"pkg/thing.py": "VALUE = 1\n"}, "Break VALUE")
    dev = git(town.repo, "rev-parse", "dev")
    gate, _ = gate_of(town)

    def moved(*_a, **_k):
        raise night_gate.Conflict("conflicts with dev in pkg/thing.py")
    monkeypatch.setattr(gate.git, "land", moved)
    rep = night(gate)
    assert git(town.repo, "rev-parse", "dev") == dev and rep["green"] is False
    assert rep["steps"][0]["ok"] is False and "after the night's fix" not in rep["steps"][0]["summary"]
    assert any("did not land on dev" in n for n in rep["not_fixed"])


def test_no_claude_here_records_the_check_and_the_night_is_red(town, monkeypatch):
    monkeypatch.setattr(night_gate.harnesses, "need", lambda _id: (_ for _ in ()).throw(RuntimeError("Claude Code is not installed")))
    rep = night(gate_of(town)[0])
    assert rep["steps"][2]["summary"] == "not run: Claude Code is not installed" and rep["green"] is False
    assert rep["error"] == ""
