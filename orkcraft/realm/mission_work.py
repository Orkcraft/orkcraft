"""Mission 1's real work, read only (docs/design/first-mission.md §3, quest 4): what waits for the person in their own
project, as cards to be. No model, no write: `gh` reads GitHub with the person's own login, `git grep` reads the files.

    found(repo_root)        → ("github" | "todo" | "", [Item, …]): GitHub first, else the TODO and FIXME lines
    github(repo_root)       → this repository's notifications for the person, then the issues assigned to them,
                              then its newest open issues
    todos(repo_root)        → the TODO and FIXME lines of the tracked files, FIXME first

Sorted by rules: a review asked of the person, a mention or an assignment first; FIXME before TODO. At most `LIMIT`.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

LIMIT = 8
TIMEOUT_S = 20
REASONS = ("review_requested", "mention", "assign", "author", "comment", "subscribed")   # first to last
TODO = re.compile(r"\b(FIXME|TODO)\b[:\s-]*(.*)")


@dataclass(frozen=True)
class Item:
    title: str
    body: str
    rank: int = 0       # lower first


def _run(runner, cmd: list[str], cwd: Path) -> str:
    try:
        out = runner(cmd, cwd=str(cwd), capture_output=True, text=True, timeout=TIMEOUT_S)
    except (OSError, subprocess.SubprocessError):
        return ""
    return out.stdout if out.returncode == 0 else ""


def _json(text: str):
    try:
        return json.loads(text) if text.strip() else None
    except ValueError:
        return None


def github(repo_root: Path, repo: str, runner=subprocess.run) -> list[Item]:
    """`repo` is `owner/name`. Read only: `gh api` GETs and `gh issue list`."""
    out: list[Item] = []
    seen: set[str] = set()
    notes = _json(_run(runner, ["gh", "api", f"repos/{repo}/notifications?per_page=20"], repo_root)) or []
    for n in notes if isinstance(notes, list) else []:
        subject = n.get("subject") or {}
        title = str(subject.get("title") or "").strip()
        reason = str(n.get("reason") or "")
        if not title or title in seen:
            continue
        seen.add(title)
        rank = REASONS.index(reason) if reason in REASONS else len(REASONS)
        out.append(Item(title, f"From GitHub ({reason.replace('_', ' ') or 'a notification'}): "
                               f"{subject.get('type') or 'item'} in {repo}.", rank))
    for who, rank in (("@me", 2), ("", len(REASONS) + 1)):
        args = ["gh", "issue", "list", "--repo", repo, "--state", "open", "--limit", str(LIMIT),
                "--json", "number,title,url,body"] + (["--assignee", who] if who else [])
        issues = _json(_run(runner, args, repo_root)) or []
        for i in issues if isinstance(issues, list) else []:
            title = str(i.get("title") or "").strip()
            if not title or title in seen:
                continue
            seen.add(title)
            body = str(i.get("body") or "").strip()[:1500]
            out.append(Item(title, f"GitHub issue #{i.get('number')}: {i.get('url') or ''}\n\n{body}".strip(), rank))
        if len(out) >= LIMIT:
            break
    return sorted(out, key=lambda x: x.rank)[:LIMIT]


def todos(repo_root: Path, runner=subprocess.run) -> list[Item]:
    text = _run(runner, ["git", "grep", "-n", "-I", "-E", r"\b(TODO|FIXME)\b"], repo_root)
    out = []
    for line in text.splitlines():
        path, _, rest = line.partition(":")
        num, _, code = rest.partition(":")
        m = TODO.search(code)
        if not m or path.startswith(".orkcraft"):
            continue
        what = " ".join(m.group(2).split())[:70] or "(no words)"
        out.append(Item(f"{m.group(1)} in {path}: {what}",
                        f"{path}:{num}\n\n{code.strip()[:300]}", 0 if m.group(1) == "FIXME" else 1))
    return sorted(out, key=lambda x: x.rank)[:LIMIT]


def found(repo_root: Path, runner=subprocess.run, which=shutil.which) -> tuple[str, list[Item]]:
    from orkcraft.realm import quickadd
    host, repo = quickadd.origin(repo_root, runner)
    if host == "github.com" and repo and which("gh"):
        items = github(repo_root, repo, runner)
        if items:
            return "github", items
    items = todos(repo_root, runner)
    return ("todo", items) if items else ("", [])
