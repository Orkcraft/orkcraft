"""The idea runner (docs/specs/29a-board-focus.md §5): a temp repository with a bare origin, a stub `claude` on PATH."""
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

from orkcraft.core import idea_runner
from orkcraft.core.idea_runner import IdeaRunner

# What the stub does is chosen per task: STUB_MODE="k1=edit,k2=fail_once". Its calls go to STUB_LOG.
STUB = r'''#!{python}
import json, os, subprocess, sys, time
argv = sys.argv[1:]
resume = "--resume" in argv
branch = subprocess.run(["git", "rev-parse", "--abbrev-ref", "HEAD"], capture_output=True, text=True).stdout.strip()
tid = branch.rsplit("/", 1)[-1]
modes = dict(p.split("=", 1) for p in os.environ.get("STUB_MODE", "").split(",") if "=" in p)
mode = modes.get(tid, modes.get("*", "edit"))
start = time.time()

def git(*a):
    subprocess.run(["git", *a], check=True, capture_output=True)

def commit(path, text, msg):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    open(path, "w").write(text)
    git("add", "-A")
    git("-c", "user.name=Stub", "-c", "user.email=stub@x", "commit", "-m", msg)

if mode == "limit":
    print("Claude AI usage limit reached", file=sys.stderr)
    sys.exit(1)
if mode == "slow":
    time.sleep(30)
if mode == "env":
    commit(f"{tid}.txt", os.environ.get("API_KEY", "none"), f"{tid}: key")
elif mode in ("fail_once", "fail_always"):
    if not resume:
        commit("pkg/thing.py", "VALUE = 1\n", f"{tid}: thing")
        commit("tests/test_thing.py", "from pkg.thing import VALUE\n\ndef test_value():\n    assert VALUE == 2\n",
               f"{tid}: its test")
    elif mode == "fail_once":
        commit("pkg/thing.py", "VALUE = 2\n", f"{tid}: fix the value")
elif mode == "conflict":
    commit("shared.txt", "the task's line\n", f"{tid}: shared")
    root = os.environ["STUB_ROOT"]
    open(os.path.join(root, "shared.txt"), "w").write("main's line\n")
    subprocess.run(["git", "-C", root, "-c", "user.name=O", "-c", "user.email=o@x", "commit", "-am", "main moved"],
                   check=True, capture_output=True)
elif mode == "nocommit":
    pass
elif mode == "uncommitted":                         # edits a file, runs no git (acceptEdits allows no Bash)
    open(f"{tid}.txt", "w").write(f"done by {tid}\n")
else:
    time.sleep(float(os.environ.get("STUB_SLEEP", "0")))
    commit(f"{tid}.txt", f"done by {tid}\n", f"{tid}: add {tid}.txt")
with open(os.environ["STUB_LOG"], "a") as f:
    f.write(json.dumps({"tid": tid, "resume": resume, "start": start, "end": time.time()}) + "\n")
print(json.dumps({"result": "done", "session_id": f"s-{tid}", "total_cost_usd": 0.01,
                  "usage": {"input_tokens": 10, "output_tokens": 5}}))
'''


def git(cwd: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True).stdout.strip()


@pytest.fixture
def town(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> SimpleNamespace:
    origin = tmp_path / "origin.git"
    repo = tmp_path / "repo"
    subprocess.run(["git", "init", "--bare", "-b", "main", str(origin)], check=True, capture_output=True)
    repo.mkdir()
    git(repo, "init", "-b", "main")
    git(repo, "config", "user.email", "t@x")
    git(repo, "config", "user.name", "T")
    (repo / ".gitignore").write_text(".orkcraft/\n__pycache__/\n.pytest_cache/\n")
    (repo / "CLAUDE.md").write_text("# Rules\n\n- write ork, never orc\n")
    (repo / "shared.txt").write_text("first\n")
    (repo / "tests").mkdir()
    for name in ("test_architecture.py", "test_cli.py", "test_updates.py"):
        (repo / "tests" / name).write_text("def test_ok():\n    assert True\n")
    (repo / "pkg").mkdir()
    (repo / "pkg" / "__init__.py").write_text("")
    (repo / "conftest.py").write_text("")
    git(repo, "add", "-A")
    git(repo, "commit", "-m", "start")
    git(repo, "remote", "add", "origin", str(origin))
    git(repo, "push", "origin", "main")
    bindir = tmp_path / "bin"
    bindir.mkdir()
    stub = bindir / "claude"
    stub.write_text(STUB.replace("{python}", sys.executable))
    stub.chmod(stub.stat().st_mode | stat.S_IEXEC)
    monkeypatch.setenv("PATH", f"{bindir}{os.pathsep}{os.environ['PATH']}")
    log = tmp_path / "stub.jsonl"
    monkeypatch.setenv("STUB_LOG", str(log))
    monkeypatch.setenv("STUB_ROOT", str(repo))
    state = repo / ".orkcraft"
    page = repo / "llm-wiki" / "general" / "pages" / "ideas" / "demo.md"
    page.parent.mkdir(parents=True)
    page.write_text("---\nowner: board\n---\n# Demo\n\n## Gist\nA demo idea.\n")
    return SimpleNamespace(repo=repo, origin=origin, state=state, log=log)


def plan_of(town, tasks: list[dict], todos: list[dict] | None = None, slug: str = "demo") -> None:
    d = town.state / "ideas" / slug
    d.mkdir(parents=True, exist_ok=True)
    full = [{"id": t["id"], "title": t.get("title", t["id"]), "brief": t.get("brief", "do " + t["id"]),
             "tier": t.get("tier", "laborer"), "after": t.get("after", []), "state": "waiting", "branch": "",
             "commit": "", "session": "", "cost": None, "tokens": None, "started": "", "finished": "", "error": "",
             "note": ""} for t in tasks]
    (d / "plan.json").write_text(json.dumps({"idea": slug, "made_at": "x", "passed_at": "y", "todos": todos or [],
                                             "tasks": full}))
    (d / "state.json").write_text(json.dumps({"state": "plan"}))


def runner_of(town, limits=None, **ideas) -> tuple[IdeaRunner, list]:
    events = []
    bus = SimpleNamespace(publish=lambda topic, **data: events.append((topic, data)))
    settings = SimpleNamespace(ideas={"max_parallel": 1, "merge_into": "main", "push": True, **ideas})
    return IdeaRunner(town.repo, town.state, settings, bus, limits=limits or (lambda: [])), events


def wait_idle(runner: IdeaRunner, slug: str = "demo", timeout: float = 90) -> dict:
    end = time.time() + timeout
    while time.time() < end:
        runner.tick()
        state = json.loads((runner.state_dir / "ideas" / slug / "state.json").read_text())
        if not runner.busy() and state["state"] in ("done", "failed"):
            return state
        time.sleep(0.1)
    raise AssertionError("the runner did not finish")


def tasks_of(town, slug: str = "demo") -> dict:
    plan = json.loads((town.state / "ideas" / slug / "plan.json").read_text())
    return {t["id"]: t for t in plan["tasks"]}


def calls(town) -> list[dict]:
    return [json.loads(ln) for ln in town.log.read_text().splitlines()] if town.log.exists() else []


def test_tasks_run_in_order_of_after_and_land_on_main_and_origin(town):
    plan_of(town, [{"id": "k2", "after": ["k1"]}, {"id": "k1"}, {"id": "k3", "after": ["k2"]}])
    runner, events = runner_of(town)
    runner.start("demo")
    assert wait_idle(runner)["state"] == "done"
    assert [c["tid"] for c in calls(town)] == ["k1", "k2", "k3"]
    tasks = tasks_of(town)
    assert all(t["state"] == "merged" for t in tasks.values())
    assert tasks["k3"]["commit"] == git(town.repo, "rev-parse", "main")
    assert tasks["k1"]["branch"] == "idea/demo/k1" and tasks["k1"]["session"] == "s-k1"
    assert tasks["k1"]["cost"] == pytest.approx(0.01)
    assert git(town.origin, "rev-parse", "main") == git(town.repo, "rev-parse", "main")
    assert (town.repo / "k3.txt").read_text() == "done by k3\n"      # main is checked out: its files moved too
    assert ("ideas.changed", {"slug": "demo"}) in events
    assert not list((town.repo / ".orkcraft" / "worktrees").glob("*"))   # the worktrees went


def test_the_prompt_holds_the_page_the_brief_the_tasks_before_and_the_rules(town):
    plan_of(town, [{"id": "k1", "brief": "first brief"}, {"id": "k2", "brief": "second brief"}])
    runner, _ = runner_of(town)
    plan = runner.plan("demo")
    plan["tasks"][0].update(state="merged", subjects=["k1: add k1.txt"])
    prompt = runner._prompt("demo", plan, plan["tasks"][1])
    assert "A demo idea." in prompt and "second brief" in prompt and "first brief" in prompt
    assert "k1: add k1.txt" in prompt and "write ork, never orc" in prompt


def test_max_parallel_runs_that_many_at_once(town, monkeypatch):
    monkeypatch.setenv("STUB_SLEEP", "1.5")
    plan_of(town, [{"id": "k1"}, {"id": "k2"}, {"id": "k3"}])
    runner, _ = runner_of(town, max_parallel=2)
    runner.start("demo")
    assert wait_idle(runner)["state"] == "done"
    spans = sorted((c["start"], c["end"]) for c in calls(town))
    assert spans[1][0] < spans[0][1]                         # two at once …
    assert spans[2][0] >= min(spans[0][1], spans[1][1]) - 0.05   # … never three
    assert sorted(t["state"] for t in tasks_of(town).values()) == ["merged"] * 3


def test_one_at_a_time_by_default(town, monkeypatch):
    monkeypatch.setenv("STUB_SLEEP", "0.5")
    plan_of(town, [{"id": "k1"}, {"id": "k2"}])
    runner, _ = runner_of(town)
    runner.start("demo")
    wait_idle(runner)
    a, b = sorted((c["start"], c["end"]) for c in calls(town))
    assert b[0] >= a[1]


def test_a_red_gate_gets_one_more_turn_on_the_same_session(town, monkeypatch):
    monkeypatch.setenv("STUB_MODE", "k1=fail_once")
    plan_of(town, [{"id": "k1"}])
    runner, _ = runner_of(town)
    runner.start("demo")
    assert wait_idle(runner)["state"] == "done"
    assert [c["resume"] for c in calls(town)] == [False, True]
    assert "VALUE = 2" in git(town.repo, "show", "main:pkg/thing.py")


def test_a_gate_still_red_fails_and_main_stays(town, monkeypatch):
    monkeypatch.setenv("STUB_MODE", "k1=fail_always")
    plan_of(town, [{"id": "k1"}, {"id": "k2", "after": ["k1"]}])
    before = git(town.repo, "rev-parse", "main")
    runner, _ = runner_of(town)
    runner.start("demo")
    state = wait_idle(runner)
    assert state["state"] == "failed" and "gate" in state["error"]
    tasks = tasks_of(town)
    assert tasks["k1"]["state"] == "failed" and tasks["k2"]["state"] == "waiting"
    assert len(calls(town)) == 2
    assert git(town.repo, "rev-parse", "main") == before == git(town.origin, "rev-parse", "main")


def test_no_commit_is_a_red_gate(town, monkeypatch):
    monkeypatch.setenv("STUB_MODE", "k1=nocommit")
    plan_of(town, [{"id": "k1"}])
    runner, _ = runner_of(town)
    runner.start("demo")
    assert wait_idle(runner)["state"] == "failed"
    assert "changed no file" in tasks_of(town)["k1"]["error"]


def test_what_the_session_left_uncommitted_is_committed_under_the_tasks_title_and_lands(town, monkeypatch):
    monkeypatch.setenv("STUB_MODE", "k1=uncommitted")
    plan_of(town, [{"id": "k1"}])
    runner, _ = runner_of(town)
    runner.start("demo")
    assert wait_idle(runner)["state"] == "done"
    assert tasks_of(town)["k1"]["state"] == "merged"
    assert git(town.origin, "log", "-1", "--format=%an", "main") == "Orkline"
    assert git(town.origin, "show", "main:k1.txt") == "done by k1"


def test_a_rebase_conflict_fails_and_main_keeps_its_own_line(town, monkeypatch):
    monkeypatch.setenv("STUB_MODE", "k1=conflict")
    plan_of(town, [{"id": "k1"}])
    runner, _ = runner_of(town)
    runner.start("demo")
    state = wait_idle(runner)
    assert state["state"] == "failed"
    assert "conflict" in tasks_of(town)["k1"]["error"] and "shared.txt" in tasks_of(town)["k1"]["error"]
    assert git(town.repo, "show", "main:shared.txt") == "main's line"
    assert git(town.repo, "log", "-1", "--format=%s", "main") == "main moved"


def test_main_not_checked_out_moves_by_its_ref_only(town):
    git(town.repo, "checkout", "-b", "elsewhere")
    plan_of(town, [{"id": "k1"}])
    runner, _ = runner_of(town)
    runner.start("demo")
    assert wait_idle(runner)["state"] == "done"
    assert git(town.repo, "rev-parse", "--abbrev-ref", "HEAD") == "elsewhere"
    assert not (town.repo / "k1.txt").exists()
    assert git(town.repo, "show", "main:k1.txt") == "done by k1"
    assert git(town.origin, "rev-parse", "main") == git(town.repo, "rev-parse", "main")


def test_push_off_keeps_origin_where_it_was(town):
    before = git(town.origin, "rev-parse", "main")
    plan_of(town, [{"id": "k1"}])
    runner, _ = runner_of(town, push=False)
    runner.start("demo")
    assert wait_idle(runner)["state"] == "done"
    assert git(town.origin, "rev-parse", "main") == before != git(town.repo, "rev-parse", "main")


def test_a_nearly_spent_window_holds_the_task_until_its_reset(town):
    reset = dt.datetime.now() + dt.timedelta(hours=2)
    limits = [SimpleNamespace(provider="claude", remaining=0.03, reset=reset)]
    plan_of(town, [{"id": "k1"}])
    runner, _ = runner_of(town, limits=lambda: limits)
    runner.start("demo")
    runner.tick()
    task = tasks_of(town)["k1"]
    assert task["state"] == "held" and task["note"] == f"after {reset:%H:%M}"
    assert calls(town) == []
    limits.clear()                                  # the window came back …
    runner._until[("demo", "k1")] = time.time() - 1
    assert wait_idle(runner)["state"] == "done"     # … and it runs


def test_the_tool_saying_its_limit_is_hit_holds_the_task(town, monkeypatch):
    monkeypatch.setenv("STUB_MODE", "k1=limit")
    plan_of(town, [{"id": "k1"}])
    runner, _ = runner_of(town)
    runner.start("demo")
    end = time.time() + 30
    while time.time() < end and (runner.busy() or tasks_of(town)["k1"]["state"] != "held"):
        time.sleep(0.1)
    task = tasks_of(town)["k1"]
    assert task["state"] == "held" and task["note"].startswith("after ")
    state = json.loads((town.state / "ideas" / "demo" / "state.json").read_text())
    assert state["state"] == "working"


def test_stop_ends_the_running_task_and_the_idea_needs_you(town, monkeypatch):
    monkeypatch.setenv("STUB_MODE", "k1=slow")
    plan_of(town, [{"id": "k1"}])
    before = git(town.repo, "rev-parse", "main")
    runner, _ = runner_of(town)
    runner.start("demo")
    end = time.time() + 10
    while time.time() < end and not runner.busy():
        time.sleep(0.05)
    time.sleep(0.5)
    runner.stop("demo")
    state = wait_idle(runner, timeout=20)
    assert state["state"] == "failed" and "stopped" in state["error"]
    assert tasks_of(town)["k1"]["state"] == "failed" and "stopped" in tasks_of(town)["k1"]["error"]
    assert git(town.repo, "rev-parse", "main") == before


def test_stop_all_stops_every_idea(town, monkeypatch):
    monkeypatch.setenv("STUB_MODE", "*=slow")
    plan_of(town, [{"id": "k1"}])
    plan_of(town, [{"id": "k1"}], slug="other")
    runner, _ = runner_of(town, max_parallel=2)
    runner.start("demo")
    runner.start("other")
    time.sleep(1)
    runner.stop_all()
    for slug in ("demo", "other"):
        assert wait_idle(runner, slug, timeout=20)["state"] == "failed"


def test_a_secret_todo_reaches_the_session_only_by_its_environment(town, monkeypatch):
    monkeypatch.setenv("STUB_MODE", "k1=env")
    (town.state).mkdir(parents=True, exist_ok=True)
    (town.state / "secrets.json").write_text(json.dumps({"ideas/demo/t1": "s3cret"}))
    todos = [{"id": "t1", "title": "Add API_KEY", "kind": "secret", "why": "", "choices": [], "steps": [],
              "for": ["k1"], "done": False, "value": None}]
    plan_of(town, [{"id": "k1"}], todos)
    runner, _ = runner_of(town)
    runner.start("demo")
    runner.tick()
    assert tasks_of(town)["k1"]["state"] == "waiting"       # its to-do is not done
    plan = json.loads((town.state / "ideas" / "demo" / "plan.json").read_text())
    plan["todos"][0].update(done=True, value="stored")
    (town.state / "ideas" / "demo" / "plan.json").write_text(json.dumps(plan))
    assert wait_idle(runner)["state"] == "done"
    assert git(town.repo, "show", "main:k1.txt") == "s3cret"
    prompt = runner._prompt("demo", runner.plan("demo"), runner.plan("demo")["tasks"][0])
    assert "s3cret" not in prompt and "API_KEY" in prompt


def test_a_restart_goes_on_with_working_ideas(town):
    plan_of(town, [{"id": "k1"}])
    (town.state / "ideas" / "demo" / "state.json").write_text(json.dumps({"state": "working"}))
    plan = json.loads((town.state / "ideas" / "demo" / "plan.json").read_text())
    plan["tasks"][0]["state"] = "running"
    (town.state / "ideas" / "demo" / "plan.json").write_text(json.dumps(plan))
    runner, _ = runner_of(town)
    assert wait_idle(runner)["state"] == "done"


def test_settings_are_read_however_they_are_carried():
    assert idea_runner.setting(SimpleNamespace(ideas={"max_parallel": 3}), "max_parallel") == 3
    assert idea_runner.setting({"ideas": {"push": False}}, "push") is False
    assert idea_runner.setting(SimpleNamespace(), "merge_into") == "main"
    assert idea_runner.setting(SimpleNamespace(ideas_max_parallel=2), "max_parallel") == 2
