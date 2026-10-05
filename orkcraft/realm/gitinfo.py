"""What the Git Branches building reads: local branches, how far each is from the
base, how much it changed, and its pull request when the GitHub CLI can say.

Everything here is read-only: `git for-each-ref`, `git rev-list`, `git diff --shortstat` and,
when `gh` is installed and logged in, `gh pr list`. No network call is made without `gh`.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

MAX_BRANCHES = 30
GIT_TIMEOUT_S = 10
_STAT = re.compile(r"(\d+) files? changed(?:, (\d+) insertions?\(\+\))?(?:, (\d+) deletions?\(-\))?")


@dataclass
class PR:
    number: int
    state: str            # OPEN | DRAFT | MERGED | CLOSED
    url: str = ""
    title: str = ""
    labels: tuple[str, ...] = ()

    @property
    def badge(self) -> str:
        return {"OPEN": "◯", "DRAFT": "◌", "MERGED": "✓", "CLOSED": "✗"}.get(self.state, "?") + f"#{self.number}"


@dataclass
class Branch:
    name: str
    head: str
    when: str = ""
    subject: str = ""
    current: bool = False
    ahead: int = 0
    behind: int = 0
    files: int = 0
    added: int = 0
    removed: int = 0
    pr: PR | None = None

    @property
    def change(self) -> str:
        return f"+{self.added}−{self.removed}" if self.files else ""


@dataclass
class Snapshot:
    base: str
    branches: list[Branch] = field(default_factory=list)
    error: str = ""
    prs_known: bool = False      # gh answered: a branch without a PR really has none


def _git(repo: Path, *args: str) -> str:
    out = subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True, timeout=GIT_TIMEOUT_S)
    if out.returncode != 0:
        raise RuntimeError(out.stderr.strip() or f"git {args[0]} failed")
    return out.stdout


def base_branch(repo: Path, configured: str = "") -> str:
    if configured:
        return configured
    try:
        ref = _git(repo, "symbolic-ref", "--quiet", "--short", "refs/remotes/origin/HEAD").strip()
        if ref:
            return ref
    except (RuntimeError, OSError, subprocess.SubprocessError):
        pass
    for name in ("main", "master", "trunk", "develop"):
        try:
            _git(repo, "rev-parse", "--verify", "--quiet", f"refs/heads/{name}")
            return name
        except (RuntimeError, OSError, subprocess.SubprocessError):
            continue
    return "HEAD"


def parse_shortstat(text: str) -> tuple[int, int, int]:
    m = _STAT.search(text)
    if not m:
        return 0, 0, 0
    return int(m.group(1)), int(m.group(2) or 0), int(m.group(3) or 0)


def pull_requests(repo: Path, runner=subprocess.run) -> dict[str, PR] | None:
    """head branch → its newest PR, or None when `gh` is missing or cannot answer."""
    if runner is subprocess.run and shutil.which("gh") is None:
        return None
    try:
        out = runner(["gh", "pr", "list", "--state", "all", "--limit", "60",
                      "--json", "number,state,headRefName,url,title,isDraft,labels"],
                     cwd=repo, capture_output=True, text=True, timeout=GIT_TIMEOUT_S)
        if out.returncode != 0:
            return None
        rows = json.loads(out.stdout or "[]")
    except (OSError, ValueError, subprocess.SubprocessError):
        return None
    prs: dict[str, PR] = {}
    for r in rows:
        head, state = str(r.get("headRefName", "")), str(r.get("state", "")).upper()
        if not head or head in prs:            # gh lists the newest first
            continue
        if state == "OPEN" and r.get("isDraft"):
            state = "DRAFT"
        labels = tuple(str((lb or {}).get("name", "")).lower() for lb in r.get("labels") or () if isinstance(lb, dict))
        prs[head] = PR(int(r.get("number", 0)), state, str(r.get("url", "")), str(r.get("title", "")), labels)
    return prs


def snapshot(repo: Path, configured_base: str = "", with_prs: bool = True, pr_runner=subprocess.run) -> Snapshot:
    base = base_branch(repo, configured_base)
    snap = Snapshot(base)
    try:
        rows = _git(repo, "for-each-ref", "--sort=-committerdate", f"--count={MAX_BRANCHES}",
                    "--format=%(refname:short)%09%(objectname:short)%09%(committerdate:relative)%09%(HEAD)%09%(subject)",
                    "refs/heads").splitlines()
    except (RuntimeError, OSError, subprocess.SubprocessError) as e:
        snap.error = str(e)[:200]
        return snap
    for row in rows:
        parts = row.split("\t", 4)
        if len(parts) < 5:
            continue
        name, head, when, star, subject = parts
        b = Branch(name, head, when, subject, star.strip() == "*")
        if name != base and base != "HEAD":
            try:
                behind, ahead = _git(repo, "rev-list", "--left-right", "--count", f"{base}...{name}").split()
                b.ahead, b.behind = int(ahead), int(behind)
                b.files, b.added, b.removed = parse_shortstat(_git(repo, "diff", "--shortstat", f"{base}...{name}"))
            except (RuntimeError, OSError, ValueError, subprocess.SubprocessError):
                pass
        snap.branches.append(b)
    if with_prs:
        prs = pull_requests(repo, pr_runner)
        if prs is not None:
            snap.prs_known = True
            for b in snap.branches:
                b.pr = prs.get(b.name)
    return snap


def changes(before: Snapshot | None, after: Snapshot) -> list[tuple[str, str]]:
    """The events between two looks: (event id, text). The first look only sets the baseline."""
    if before is None or before.error:
        return []
    old = {b.name: b for b in before.branches}
    out: list[tuple[str, str]] = []
    for b in after.branches:
        prev = old.get(b.name)
        if prev is not None and prev.head != b.head:
            out.append(("git.commit", f"{b.name}: {b.subject}"))
        if not after.prs_known or b.pr is None:
            continue
        was = prev.pr if prev is not None else None
        if b.pr.state in ("OPEN", "DRAFT") and (was is None or was.number != b.pr.number):
            out.append(("git.pr_opened", f"{b.name}: #{b.pr.number} {b.pr.title}".rstrip()))
        if b.pr.state == "MERGED" and (was is None or was.state != "MERGED") and before.prs_known:
            out.append(("git.pr_merged", f"{b.name}: #{b.pr.number} {b.pr.title}".rstrip()))
    return out


def detail(repo: Path, base: str, name: str) -> str:
    """The open building's right pane: the last commits and the diff stat against the base."""
    try:
        log = _git(repo, "log", "--format=%h %s (%cr)", "-8", name)
        stat = _git(repo, "diff", "--stat=60", f"{base}...{name}") if name != base and base != "HEAD" else ""
    except (RuntimeError, OSError, subprocess.SubprocessError) as e:
        return str(e)[:200]
    return log.rstrip() + ("\n\n" + stat.rstrip() if stat.strip() else "")
