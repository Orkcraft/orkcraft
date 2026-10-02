"""⚒️ The Forge's merge: test a branch, then squash it into the base.

    1. checks   the base is a branch; if it is checked out here, the working tree is clean
    2. tests    `test_cmd` (when set) runs in a throw-away worktree of the branch — red stops it
    3. merge    `git merge-tree --write-tree` builds the merged tree without touching any
                checkout; conflicts stop it and name the files
    4. squash   one commit on the base (`squash: <branch>` + the branch's commit subjects); the
                base moves by fast-forward when it is checked out here, else by `update-ref`
                with the old value checked (nothing is lost if someone moved it meanwhile)

The branch itself is left as it is. Every git call has fixed arguments, no shell.
"""
from __future__ import annotations

import shlex
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

GIT_TIMEOUT_S = 60
TEST_TIMEOUT_S = 900


@dataclass
class Result:
    ok: bool
    branch: str
    base: str
    commit: str = ""
    message: str = ""
    conflicts: list[str] = field(default_factory=list)
    tests: str = ""          # the test command's output tail
    error: str = ""

    def text(self) -> str:
        if self.ok:
            return f"{self.branch} → {self.base}: {self.commit[:10]}\n\n{self.message}"
        if self.conflicts:
            return f"{self.branch} → {self.base}: conflicts in\n" + "\n".join(f"- {c}" for c in self.conflicts)
        return f"{self.branch} → {self.base}: {self.error}" + (f"\n\n```\n{self.tests}\n```" if self.tests else "")


def _git(repo: Path, *args: str, check: bool = False) -> subprocess.CompletedProcess:
    out = subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True, timeout=GIT_TIMEOUT_S)
    if check and out.returncode != 0:
        raise RuntimeError((out.stderr or out.stdout).strip()[:300] or f"git {args[0]} failed")
    return out


def current_branch(repo: Path) -> str:
    return _git(repo, "symbolic-ref", "--quiet", "--short", "HEAD").stdout.strip()


def run_tests(repo: Path, branch: str, cmd: str, timeout_s: int = TEST_TIMEOUT_S) -> tuple[bool, str]:
    """The test command in a detached worktree of `branch`; (passed, the output's tail)."""
    argv = shlex.split(cmd)
    if not argv:
        return True, ""
    with tempfile.TemporaryDirectory(prefix="orkcraft-forge-") as tmp:
        wt = Path(tmp) / "wt"
        _git(repo, "worktree", "add", "--detach", str(wt), branch, check=True)
        try:
            out = subprocess.run(argv, cwd=wt, capture_output=True, text=True, timeout=timeout_s)
            tail = "\n".join((out.stdout + out.stderr).strip().splitlines()[-25:])
            return out.returncode == 0, tail
        except subprocess.TimeoutExpired:
            return False, f"no result within {timeout_s} s"
        except FileNotFoundError:
            return False, f"{argv[0]} not found"
        finally:
            _git(repo, "worktree", "remove", "--force", str(wt))


def merge(repo: Path, branch: str, base: str, test_cmd: str = "", runner=run_tests) -> Result:
    res = Result(False, branch, base)
    for ref in (branch, base):
        if _git(repo, "rev-parse", "--verify", "--quiet", f"refs/heads/{ref}").returncode != 0:
            res.error = f"no branch {ref!r}"
            return res
    if branch == base:
        res.error = "a branch cannot be merged into itself"
        return res
    here = current_branch(repo)
    if here == base and _git(repo, "status", "--porcelain", "--untracked-files=no").stdout.strip():
        res.error = f"{base} is checked out with uncommitted changes — commit or stash them first"
        return res
    ahead = _git(repo, "rev-list", "--count", f"{base}..{branch}").stdout.strip()
    if ahead == "0":
        res.error = f"{branch} has nothing that {base} does not have"
        return res
    if test_cmd:
        passed, tail = runner(repo, branch, test_cmd)
        res.tests = tail
        if not passed:
            res.error = "tests failed"
            return res
    mt = _git(repo, "merge-tree", "--write-tree", "--name-only", "--no-messages", base, branch)
    if mt.returncode == 1:
        lines = mt.stdout.strip().splitlines()
        res.conflicts = [ln for ln in lines[1:] if ln.strip()]
        res.error = "conflicts"
        return res
    if mt.returncode != 0:
        res.error = (mt.stderr or "git merge-tree failed (needs git 2.38+)").strip()[:300]
        return res
    tree = mt.stdout.strip().splitlines()[0]
    if tree == _git(repo, "rev-parse", f"refs/heads/{base}^{{tree}}").stdout.strip():
        res.error = f"{branch} has nothing that {base} does not have (already squashed in?)"
        return res
    subjects = _git(repo, "log", "--reverse", "--format=- %s", f"{base}..{branch}").stdout.strip()
    res.message = f"squash: {branch} ({ahead} commit{'s' if ahead != '1' else ''})\n\n{subjects}"
    old = _git(repo, "rev-parse", f"refs/heads/{base}", check=True).stdout.strip()
    commit = _git(repo, "commit-tree", tree, "-p", old, "-m", res.message, check=True).stdout.strip()
    if here == base:
        _git(repo, "merge", "--ff-only", "--quiet", commit, check=True)
    else:
        _git(repo, "update-ref", f"refs/heads/{base}", commit, old, check=True)
    res.ok, res.commit, res.error = True, commit, ""
    return res
