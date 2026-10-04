"""One sandbox per landing-page class: a single orkspace with that class's eight buildings,
built with the showcase's own builder (orkcraft.demo.build) and seeded with class data."""
from __future__ import annotations

import datetime as dt
import json
import os
import subprocess
from pathlib import Path

from orkcraft import demo
from orkcraft.demo import scenarios
from orkcraft.demo.dashboard import typed

NOW = dt.datetime.now().replace(second=0, microsecond=0)
GRID = [(0.0, 0.0, 0.24, 0.46), (0.25, 0.0, 0.24, 0.46), (0.5, 0.0, 0.24, 0.46), (0.75, 0.0, 0.24, 0.46),
        (0.0, 0.54, 0.24, 0.46), (0.25, 0.54, 0.24, 0.46), (0.5, 0.54, 0.24, 0.46), (0.75, 0.54, 0.24, 0.46)]


def git(root: Path, *args: str, env: dict | None = None) -> str:
    e = dict(os.environ, GIT_AUTHOR_NAME="Orc Smith", GIT_AUTHOR_EMAIL="smith@orkcraft.invalid",
             GIT_COMMITTER_NAME="Orc Smith", GIT_COMMITTER_EMAIL="smith@orkcraft.invalid", **(env or {}))
    return subprocess.run(["git", *args], cwd=root, check=True, capture_output=True, text=True, env=e).stdout


def write(root: Path, rel: str, text: str) -> None:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def scenario(cid: str, name: str, icon: str, buildings: list[dict], files: dict, roads=()) -> dict:
    return {"id": cid, "name": name, "icon": icon, "biome": "void", "git": {"enabled": False},
            "segment": name, "story": name, "nodes": [], "files": files, "buildings": buildings,
            "layout": GRID[:len(buildings)], "roads": list(roads), "payloads": {}}


def build(root: Path, sc: dict) -> Path:
    scenarios.SETS[sc["id"]] = [sc]
    root = demo.build(root, reset=True, set_name=sc["id"])
    write(root, ".gitignore", ".orkcraft/\n.orkcraft.json\n.orkcraft-demo\n")
    git(root, "init", "-q", "-b", "main")
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", "camp founded", env={"GIT_AUTHOR_DATE": (NOW - dt.timedelta(days=3)).isoformat(),
                                                         "GIT_COMMITTER_DATE": (NOW - dt.timedelta(days=3)).isoformat()})
    return root


def branch(root: Path, name: str, files: dict[str, str], msg: str, hours_ago: float = 2) -> None:
    git(root, "checkout", "-q", "-b", name, "main")
    for rel, text in files.items():
        write(root, rel, text)
    git(root, "add", "-A")
    when = (NOW - dt.timedelta(hours=hours_ago)).isoformat()
    git(root, "commit", "-q", "-m", msg, env={"GIT_AUTHOR_DATE": when, "GIT_COMMITTER_DATE": when})
    git(root, "checkout", "-q", "main")


def fake_gh(bindir: Path, prs: list[dict]) -> None:
    """A stand-in `gh` on PATH that lists these pull requests (the sandbox has no GitHub)."""
    bindir.mkdir(parents=True, exist_ok=True)
    data = bindir / "prs.json"
    data.write_text(json.dumps(prs), encoding="utf-8")
    gh = bindir / "gh"
    gh.write_text(f"#!/bin/sh\n[ \"$1 $2\" = \"pr list\" ] && cat '{data}' && exit 0\n[ \"$1\" = \"api\" ] && echo '[]' && exit 0\nexit 1\n", encoding="utf-8")
    gh.chmod(0o755)


def barracks(root: Path, bid: str, orcs, queue, tasks, decisions, stats=None) -> None:
    from orkcraft.realm import barracks as bk
    st = bk.Barracks(root / ".orkcraft" / "barracks" / bid)
    st.orcs, st.queue, st.tasks = orcs, queue, tasks
    st.stats = stats or {}
    st.save()
    for d in decisions:
        st.log(d)


def council(root: Path, bid: str, topic: str, turns, rnd: int, spent: float, outcome="running", draft="") -> None:
    from orkcraft.realm import team as tm
    d = tm.new(topic, topic)
    d.started, d.outcome, d.round, d.spent, d.draft = NOW.isoformat(), outcome, rnd, spent, draft
    d.turns = [tm.Turn(*t) for t in turns]
    tm.save(root / ".orkcraft" / "council" / bid, d)


def ledger(root: Path, runs) -> None:
    from orkcraft.realm import metrics
    for i, (b, cost, tok) in enumerate(runs):
        metrics.record_run(root, b, "done", cost, tok, now=NOW - dt.timedelta(hours=20 - 1.2 * i, minutes=i))


def signals(root: Path, bid: str, rows) -> None:
    p = root / ".orkcraft" / "watchtower" / bid / "signals.jsonl"
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
