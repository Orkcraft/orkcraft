"""⚒️ The Forge in the GUI (docs/design/building-views.md §3): its card, its detail and every act,
through the host, with no window."""
from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

from orkcraft.core import buildings
from orkcraft.core.workers.forge import ForgeWorker, pr_comments
from orkcraft.gui.host import CommandError, Host
from orkcraft.realm import checkpoint, gitinfo, pipes


def git(repo: Path, *a: str) -> str:
    return subprocess.run(["git", *a], cwd=repo, check=True, capture_output=True, text=True).stdout.strip()


def branch(repo: Path, name: str, files: dict[str, str]) -> None:
    git(repo, "checkout", "-q", "-b", name)
    for path, text in files.items():
        (repo / path).write_text(text)
        git(repo, "add", path)
        git(repo, "commit", "-q", "-m", f"{name}: {path}")
    git(repo, "checkout", "-q", "-")


def wait(cond, seconds: float = 10.0) -> None:
    end = time.monotonic() + seconds
    while not cond():
        assert time.monotonic() < end, "timed out"
        time.sleep(0.02)


@pytest.fixture
def forge(fake_repo: Path, monkeypatch):
    monkeypatch.setattr(gitinfo, "pull_requests", lambda repo, runner=None: None)
    branch(fake_repo, "feat", {"src/a.py": "A = 1\n", "src/b.py": "B = 2\n"})
    branch(fake_repo, "clash", {"README.md": "theirs\n"})
    checkpoint.ensure(fake_repo)
    host = Host(fake_repo, auto_commit=False)
    spec = buildings.type_spec(host.town, "forge")
    built = buildings.raise_spec(host.town, spec)
    w = host.town.worker(built.id)
    wait(lambda: w.snap is not None)
    return host, built.id, w


def act(host: Host, bid: str, name: str, **args):
    return host.command("act", {"id": bid, "act": name, "args": args})


def test_the_card_and_the_detail(forge):
    host, bid, w = forge
    card = next(b for b in host.snapshot()["buildings"] if b["id"] == bid)["card"]
    assert card == {"branches": 2, "prs": 0, "merging": "", "asking": "", "last": None}
    d = host.detail(bid)["data"]
    assert [b["name"] for b in d["branches"]][0] == d["base"]             # the base first
    assert {b["name"] for b in d["branches"]} >= {"feat", "clash"} and d["chosen"] is None
    act(host, bid, "pick", branch="feat")
    c = host.detail(bid)["data"]["chosen"]
    assert c["name"] == "feat" and [x["subject"] for x in c["commits"]] == ["feat: src/b.py", "feat: src/a.py"]
    assert {f["path"] for f in c["files"]} == {"src/a.py", "src/b.py"} and c["merges"] == []
    d = act(host, bid, "diff", branch="feat")
    assert "+A = 1" in d["text"] and "feat" in d["title"]
    with pytest.raises(CommandError):
        act(host, bid, "pick", branch="nope")
    with pytest.raises(CommandError):
        act(host, bid, "pr", branch="feat")                                 # no PR


def test_a_merge_its_conflicts_and_the_card(forge):
    host, bid, w = forge
    (host.town.repo_root / "README.md").write_text("ours\n")
    git(host.town.repo_root, "commit", "-qam", "ours")
    act(host, bid, "merge", branch="clash")
    wait(lambda: w.last_merge is not None)
    assert not w.last_merge.ok and w.last_merge.conflicts == ["README.md"]
    act(host, bid, "pick", branch="clash")
    m = host.detail(bid)["data"]["chosen"]["merges"]
    assert m[0]["conflicts"] == ["README.md"] and not m[0]["ok"]
    card = next(b for b in host.snapshot()["buildings"] if b["id"] == bid)["card"]
    assert {k: card["last"][k] for k in ("ok", "branch", "why")} == {"ok": False, "branch": "clash", "why": "conflict"}
    assert len(card["last"]["at"]) == 5                                     # HH:MM: it merged today
    act(host, bid, "merge", branch="feat")
    wait(lambda: w.last_merge.branch == "feat")
    assert w.last_merge.ok and git(host.town.repo_root, "log", "-1", "--format=%s").startswith("squash: feat")
    with pytest.raises(CommandError):
        act(host, bid, "merge", branch=w.base)


def test_tests_settings_and_a_cart_that_asks_first(forge):
    host, bid, w = forge
    with pytest.raises(CommandError):
        act(host, bid, "test", branch="feat")                               # no test command yet
    ok = f"{sys.executable} -c \"print('green')\""
    assert act(host, bid, "settings", test_cmd=ok, confirm=True)
    assert host.detail(bid)["data"]["settings"]["test_cmd"] == ok
    assert act(host, bid, "test", branch="feat")
    wait(lambda: "feat" in w.tests)
    assert w.tests["feat"]["ok"] and "green" in w.tests["feat"]["output"]
    feat = next(b for b in host.detail(bid)["data"]["branches"] if b["name"] == "feat")
    assert feat["tests"] == "passed"
    w.receive(pipes.Payload(pipes.TEXT, "done\n\n_branch:_ `feat`", "camp", "pool.done", "Login"), "", "")
    assert host.detail(bid)["data"]["asking"] == "feat" and w.last_merge is None          # it waits for a yes
    act(host, bid, "decline")
    assert w.asking == ""


def test_pr_comments_come_from_gh():
    data = {"comments": [{"author": {"login": "ann"}, "body": "Looks fine", "createdAt": "2026-10-02T10:00:00Z"}],
            "reviews": [{"author": {"login": "bob"}, "body": "", "state": "COMMENTED", "submittedAt": "x"},
                        {"author": {"login": "cy"}, "body": "Fix the name", "state": "CHANGES_REQUESTED",
                         "submittedAt": "2026-10-01T09:00:00Z"}]}
    got = pr_comments(Path("."), 7, lambda *a, **kw: SimpleNamespace(returncode=0, stdout=json.dumps(data), stderr=""))
    assert [(c["author"], c["state"]) for c in got] == [("cy", "changes_requested"), ("ann", "")]
    assert pr_comments(Path("."), 7, lambda *a, **kw: SimpleNamespace(returncode=1, stdout="", stderr="")) is None


def test_the_worker_registers_itself():
    from orkcraft.core import workers
    assert workers.registry()["forge"] is ForgeWorker
