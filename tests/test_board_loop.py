"""The whole loop of the board in focus (docs/specs/29a-board-focus.md): an idea dropped, read by the batch, talked
through, planned, started, its task a Claude session whose commit lands on `dev` (made from `main` by the first task) and on origin; `main`
waits for the Review gate (decisions §45). A real Host on a
temp repository with a bare origin; `claude` is a stub on PATH that answers each kind of call."""
from __future__ import annotations

import json
import os
import stat
import subprocess
import sys
import time

import pytest

from orkcraft.gui.host import Host
from orkcraft.realm import checkpoint, ideas

STUB = r'''#!{python}
import json, os, subprocess, sys
argv = sys.argv[1:]
prompt = argv[argv.index("-p") + 1]
if "--permission-mode" in argv:                     # a task's session: it does the work and commits it
    open("feature.txt", "w").write("built by the stub\n")
    subprocess.run(["git", "add", "feature.txt"], check=True)
    subprocess.run(["git", "-c", "user.name=Stub", "-c", "user.email=stub@x", "commit", "-qm", "Add the feature"],
                   check=True)
    out = "Done: feature.txt added."
elif '"gist"' in prompt:                            # the batch
    out = json.dumps({"gist": "Build the feature\nA small file the tests can see.", "why": "It moves the first track",
                      "size": "S", "track": "", "questions": ["Which file name?"]})
elif '"reply"' in prompt:                           # the talk
    out = json.dumps({"reply": "feature.txt it is.", "sections": {"In": "One file, feature.txt."},
                      "decisions": ["The file is feature.txt: the person said so"], "questions": []})
else:                                               # the plan
    out = json.dumps({"tasks": [{"id": "k1", "title": "Add feature.txt", "brief": "Write feature.txt and commit it.",
                                 "tier": "warrior", "after": []}], "todos": []})
print(json.dumps({"result": out, "total_cost_usd": 0.01, "session_id": "stub-session",
                  "usage": {"input_tokens": 10, "output_tokens": 5}}))
'''


def _git(cwd, *args):
    return subprocess.run(["git", *args], cwd=str(cwd), check=True, capture_output=True, text=True).stdout.strip()


@pytest.fixture
def town(fake_repo, tmp_path, monkeypatch):
    tests = fake_repo / "tests"
    tests.mkdir()
    for name in ("test_architecture.py", "test_cli.py", "test_updates.py"):
        (tests / name).write_text("def test_ok():\n    assert True\n")
    _git(fake_repo, "add", ".")
    _git(fake_repo, "commit", "-qm", "critical tests")
    _git(fake_repo, "branch", "-M", "main")
    origin = tmp_path / "origin.git"
    _git(tmp_path, "init", "-q", "--bare", str(origin))
    _git(fake_repo, "remote", "add", "origin", str(origin))
    _git(fake_repo, "push", "-q", "origin", "main")
    bindir = tmp_path / "bin"
    bindir.mkdir()
    stub = bindir / "claude"
    stub.write_text(STUB.replace("{python}", sys.executable))
    stub.chmod(stub.stat().st_mode | stat.S_IEXEC)
    monkeypatch.setenv("PATH", f"{bindir}{os.pathsep}{os.environ['PATH']}")
    checkpoint.ensure(fake_repo)
    host = Host(fake_repo, auto_commit=False)
    yield host, fake_repo, origin
    host.ideas.stop_all()


def _until(host, check, what, seconds=60.0):
    end = time.time() + seconds
    while time.time() < end:
        host.ideas.tick(time.time())
        if check():
            return
        time.sleep(0.05)
    raise AssertionError(f"never: {what}")


def test_an_idea_goes_from_the_phone_to_a_commit_on_dev_and_origin_and_main_waits(town):
    host, repo, origin = town
    state = lambda slug: ideas.state(host.ideas.state_dir, slug)["state"]   # noqa: E731
    slug = host.command("ideas.add", {"text": "a feature file"})["slug"]
    assert state(slug) == "raw"

    host.ideas.keeper.read_one(slug)                     # the batch, as its clock would run it
    _until(host, lambda: state(slug) == "asks", "the batch asks")
    page = host.command("ideas.page", {"slug": slug})
    assert any(s["name"] == "Open questions" and "file name" in s["text"] for s in page["sections"])

    host.command("ideas.say", {"slug": slug, "text": "Call it feature.txt"})
    _until(host, lambda: state(slug) == "ready", "the talk leaves no question")
    page = host.command("ideas.page", {"slug": slug})
    assert "feature.txt" in next(s["text"] for s in page["sections"] if s["name"] == "Decisions")

    host.command("ideas.plan", {"slug": slug})
    _until(host, lambda: state(slug) == "plan", "the plan is ready")
    assert host.command("ideas.page", {"slug": slug})["plan"]["estimate"]["tasks"] == 1

    host.command("ideas.start", {"slug": slug})
    _until(host, lambda: state(slug) == "done", "the idea is done", seconds=120)
    task = ideas.plan(host.ideas.state_dir, slug)["tasks"][0]
    assert task["state"] == "merged" and task["commit"]
    assert _git(repo, "log", "-1", "--format=%s", "dev") == "Add the feature"
    assert _git(origin, "log", "-1", "--format=%s", "dev") == "Add the feature"
    assert _git(repo, "log", "-1", "--format=%s", "main") == "critical tests"     # main waits for the gate
    assert not (repo / "feature.txt").exists()                                    # main is checked out, untouched
    board = host.command("ideas.board")
    assert next(i for i in board["ideas"] if i["slug"] == slug)["progress"] == {"done": 1, "total": 1}

