"""The git of an idea's tasks (docs/specs/29a-board-focus.md §5): a worktree per task, the gate, the merge.

    g = IdeaGit(repo_root)
    path, branch = g.prepare(slug, task_id, "main")      # a worktree off the local `main`, branch idea/<slug>/<id>
    g.commits(path, base) / g.touched(path, base)        # what the task committed since it left the base
    ok, tail = g.gate(path, cancel)                      # the critical tests + the test files of touched modules
    commit, subjects, note = g.land(path, branch, "main", push=True)   # rebase, fast-forward main, push
    g.revert(slug, task_id, commit, since, "main", push=True, cancel=cancel)   # undo a landed task the same way
    read_secret(state_dir, slug, todo_id)                # a `secret` to-do's value, from where part A stored it

Every call runs git with fixed arguments (no shell). One lock per repository (`lock_of`) holds every change
of refs and worktrees, so two tasks never rebase or fast-forward at once. A task that fails or conflicts never
moves `merge_into`: the rebase happens on its own branch in its own worktree, and `merge_into` moves only by
a fast-forward to a commit that already holds it.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import threading
from pathlib import Path

from orkcraft.realm import jobs, worktrees

GIT_TIMEOUT_S = 60
PUSH_TIMEOUT_S = 120
CRITICAL_TESTS = ("tests/test_architecture.py", "tests/test_cli.py", "tests/test_updates.py")
TEST_TAIL = 3000
SECRETS_FILE = "secrets.json"
KEYRING_SERVICE = "orkline"

_LOCKS: dict[str, threading.RLock] = {}
_LOCKS_GUARD = threading.Lock()


class Conflict(RuntimeError):
    """The task's branch does not rebase cleanly onto `merge_into`."""


def lock_of(repo_root: Path) -> threading.RLock:
    """The one lock of a repository: refs, worktrees and the root checkout change under it."""
    key = str(Path(repo_root).resolve())
    with _LOCKS_GUARD:
        return _LOCKS.setdefault(key, threading.RLock())


def _git(cwd: Path, *args: str, timeout: int = GIT_TIMEOUT_S) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, timeout=timeout)


def _ok(proc: subprocess.CompletedProcess) -> str:
    if proc.returncode != 0:
        raise RuntimeError((proc.stderr or proc.stdout).strip()[:300] or f"git failed ({proc.returncode})")
    return proc.stdout.strip()


def branch_of(slug: str, task_id: str) -> str:
    return f"idea/{slug}/{task_id}"


def _worktree_id(slug: str, task_id: str) -> str:
    raw = re.sub(r"[^a-z0-9_-]+", "-", f"idea-{slug}-{task_id}".lower()).strip("-")
    return raw[:64].rstrip("-") or "idea"


def test_files(touched: list[str], root: Path) -> list[str]:
    """The critical tests, and the test files named after the modules the diff touches (CLAUDE.md "Alpha"):
    `orkcraft/realm/ideas.py` → `tests/test_ideas.py`, a touched test file itself; only those that exist."""
    out = list(CRITICAL_TESTS)
    for name in touched:
        p = Path(name)
        if p.suffix != ".py":
            continue
        if p.parts[:1] == ("tests",) and p.name.startswith("test_"):
            cand = p.as_posix()
        elif p.stem != "__init__":
            cand = f"tests/test_{p.stem}.py"
        else:
            continue
        if cand not in out and (root / cand).is_file():
            out.append(cand)
    return [t for t in out if (root / t).is_file()]


class IdeaGit:
    def __init__(self, repo_root: Path) -> None:
        self.root = Path(repo_root)
        self.lock = lock_of(self.root)

    # -- the task's worktree ---------------------------------------------------------------------

    def prepare(self, slug: str, task_id: str, base: str) -> tuple[Path, str]:
        """A fresh worktree on branch `idea/<slug>/<task id>`, cut from the local `base` (a leftover of an
        earlier try is removed, and its branch cut anew)."""
        branch = branch_of(slug, task_id)
        if not worktrees.valid_branch(self.root, branch):
            raise RuntimeError(f"{branch!r} is not a valid branch name")
        with self.lock:
            self.ensure_branch(base)
            path = worktrees.worktree_path(self.root, _worktree_id(slug, task_id))
            self.remove(path)
            path.parent.mkdir(parents=True, exist_ok=True)
            _ok(_git(self.root, "worktree", "add", "-B", branch, str(path), base))
        return path, branch

    def ensure_branch(self, base: str) -> None:
        """`base` as a local branch: as it is; else from `origin/<base>`; else cut from `main` (or HEAD) — the first
        task of a town creates `dev` (decisions §45). Under the repository lock."""
        if _git(self.root, "rev-parse", "--verify", "-q", f"refs/heads/{base}").returncode == 0:
            return
        if not worktrees.valid_branch(self.root, base):
            raise RuntimeError(f"{base!r} is not a valid branch name")
        _git(self.root, "fetch", "-q", "origin", base)
        for start in (f"refs/remotes/origin/{base}", "refs/heads/main", "HEAD"):
            if _git(self.root, "rev-parse", "--verify", "-q", start).returncode == 0:
                _ok(_git(self.root, "branch", base, start))
                return
        raise RuntimeError(f"no branch to cut {base!r} from")

    def remove(self, path: Path) -> None:
        with self.lock:
            if path.exists():
                try:
                    worktrees.remove(self.root, path, force=True)
                except worktrees.WorktreeError:
                    pass
            _git(self.root, "worktree", "prune")

    def head(self, path: Path) -> str:
        return _ok(_git(path, "rev-parse", "HEAD"))

    def rev(self, ref: str) -> str:
        """The commit a ref names in the repository, "" when none."""
        done = _git(self.root, "rev-parse", "--verify", "-q", f"{ref}^{{commit}}")
        return done.stdout.strip() if done.returncode == 0 else ""

    def commits(self, path: Path, base: str) -> list[str]:
        """The subjects of what the branch committed since it left `base`, oldest first."""
        out = _git(path, "log", "--reverse", "--format=%s", f"{base}..HEAD").stdout
        return [ln for ln in out.splitlines() if ln.strip()]

    def touched(self, path: Path, base: str) -> list[str]:
        out = _git(path, "diff", "--name-only", f"{base}...HEAD").stdout
        return [ln for ln in out.splitlines() if ln.strip()]

    def dirty(self, path: Path) -> bool:
        return bool(_git(path, "status", "--porcelain").stdout.strip())

    def commit_left(self, path: Path, message: str) -> bool:
        """Commit what the session left uncommitted (a session in `acceptEdits` edits files but may not run git):
        True when it made a commit. Orkline is its author; ignored files stay out, as `git add -A` leaves them."""
        if not self.dirty(path):
            return False
        _ok(_git(path, "add", "-A"))
        _ok(_git(path, "-c", "user.name=Orkline", "-c", "user.email=orkline@localhost", "commit", "-q", "-m",
                 message.strip()[:200] or "Orkline: the task's work"))
        return True

    # -- the gate --------------------------------------------------------------------------------

    def gate(self, path: Path, base: str, cancel: threading.Event,
             timeout_s: int = jobs.TEST_TIMEOUT_S) -> tuple[bool, str]:
        """(passed, the output's tail) of `python -m pytest -q` on the critical tests and the touched modules'."""
        files = test_files(self.touched(path, base), path)
        if not files:
            return True, "no test files to run"
        # No cache, no bytecode: the gate leaves the worktree as the session left it (land checks it is clean).
        argv = [self.python(), "-m", "pytest", "-q", "-p", "no:cacheprovider", *files]
        proc = subprocess.Popen(argv, cwd=path, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                                start_new_session=True, env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})
        out_box: list[str] = []
        reader = threading.Thread(target=lambda: out_box.append(proc.stdout.read() if proc.stdout else ""),
                                  daemon=True)
        reader.start()
        jobs._wait(proc, cancel, timeout_s, "ideas/gate")
        reader.join(5)
        out = out_box[0] if out_box else ""
        return proc.returncode == 0, f"$ python -m pytest -q {' '.join(files)}\n{out[-TEST_TAIL:]}"

    def python(self) -> str:
        """The repository's own Python when it has one (`.venv`, where its test tools are), else Orkline's."""
        for rel in (".venv/bin/python", ".venv/Scripts/python.exe"):
            if (self.root / rel).is_file():
                return str(self.root / rel)
        return sys.executable

    # -- the merge -------------------------------------------------------------------------------

    def _checked_out_in_root(self, branch: str) -> bool:
        head = _git(self.root, "symbolic-ref", "-q", "HEAD").stdout.strip()
        return head == f"refs/heads/{branch}"

    def land(self, path: Path, branch: str, into: str, push: bool = True) -> tuple[str, list[str], str]:
        """Rebase the task's branch onto the current `into`, fast-forward `into` to it and push when asked:
        (the new head of `into`, the subjects it brought, a note). Raises Conflict on a conflicting rebase,
        RuntimeError when `into` cannot move; either way `into` is as it was."""
        with self.lock:
            if self.dirty(path):
                raise RuntimeError("the task left uncommitted changes")
            rebase = _git(path, "rebase", into, timeout=PUSH_TIMEOUT_S)
            if rebase.returncode != 0:
                files = _git(path, "diff", "--name-only", "--diff-filter=U").stdout.split()
                _git(path, "rebase", "--abort")
                raise Conflict("conflicts with " + into + (" in " + ", ".join(files) if files else ""))
            new = self.head(path)
            old = _ok(_git(self.root, "rev-parse", f"refs/heads/{into}"))
            if _git(self.root, "merge-base", "--is-ancestor", old, new).returncode != 0:
                raise RuntimeError(f"{into} moved during the merge")
            subjects = [s for s in _git(self.root, "log", "--reverse", "--format=%s", f"{old}..{new}")
                        .stdout.splitlines() if s.strip()]
            if old != new:
                self._fast_forward(into, old, new)
            note = self.push(into) if push else ""
        return new, subjects, note

    def revert(self, slug: str, task_id: str, commit: str, since: str, into: str, push: bool,
               cancel: threading.Event) -> tuple[str, list[str], str]:
        """Undo a landed task (spec 29c §1): `git revert --no-edit` of what it brought (`since..commit`, or the one
        commit) in a worktree off `into`, the gate, then landed as a task is. Raises Conflict when the revert does
        not apply, RuntimeError when the gate is red; either way `into` is as it was."""
        if not re.fullmatch(r"[0-9a-f]{7,40}", commit or "") or (since and not re.fullmatch(r"[0-9a-f]{7,40}", since)):
            raise RuntimeError("no commit to revert")
        path, branch = self.prepare(slug, f"{task_id}-revert", into)
        try:
            start = self.head(path)
            span = f"{since}..{commit}" if since else commit
            done = _git(path, "-c", "user.name=Orkline", "-c", "user.email=orkline@localhost", "revert", "--no-edit",
                        span, timeout=PUSH_TIMEOUT_S)
            if done.returncode != 0:
                files = _git(path, "diff", "--name-only", "--diff-filter=U").stdout.split()
                _git(path, "revert", "--abort")
                if not files:
                    raise RuntimeError((done.stderr or done.stdout).strip()[:300] or "the revert failed")
                raise Conflict(f"the revert conflicts with {into} in " + ", ".join(files))
            ok, tail = self.gate(path, start, cancel)
            if not ok:
                raise RuntimeError(f"the gate is red after the revert: {tail[-600:]}")
            return self.land(path, branch, into, push)
        finally:
            self.remove(path)

    def _fast_forward(self, into: str, old: str, new: str) -> None:
        if self._checked_out_in_root(into):
            touched = [ln for ln in _git(self.root, "diff", "--name-only", old, new).stdout.splitlines() if ln]
            busy = [ln for ln in _git(self.root, "status", "--porcelain", "--", *touched).stdout.splitlines()
                    if ln.strip()] if touched else []
            if busy:
                files = ", ".join(ln[3:] for ln in busy)
                raise RuntimeError(f"{into} is checked out with uncommitted changes in {files}")
            _ok(_git(self.root, "merge", "--ff-only", new, timeout=PUSH_TIMEOUT_S))
        else:
            _ok(_git(self.root, "update-ref", f"refs/heads/{into}", new, old))

    def push(self, branch: str) -> str:
        """`git push origin <branch>` when there is an origin: a note ("" when pushed or no origin)."""
        if "origin" not in _git(self.root, "remote").stdout.split():
            return ""
        done = _git(self.root, "push", "origin", branch, timeout=PUSH_TIMEOUT_S)
        if done.returncode != 0:
            return f"push failed: {(done.stderr or done.stdout).strip()[:200]}"
        return ""


# -- secrets of `secret` to-dos (stored by part A, §3) ------------------------------------------------

def secret_keys(slug: str, todo_id: str) -> tuple[str, ...]:
    return (f"ideas/{slug}/{todo_id}", f"{slug}/{todo_id}")


def read_secret(state_dir: Path, slug: str, todo_id: str) -> str | None:
    """A `secret` to-do's value from where part A stores it: `realm/secrets` if there is one, else the OS
    keychain (`keyring`, service "orkline"), else `<state_dir>/secrets.json` (flat by key, or {slug: {id: v}})."""
    keys = secret_keys(slug, todo_id)
    try:
        from orkcraft.realm import secrets as store          # type: ignore[attr-defined]
        get = getattr(store, "get", None) or getattr(store, "read", None)
        for key in keys:
            value = get(key) if get else None
            if value:
                return str(value)
    except Exception:
        pass
    try:
        import keyring                                         # type: ignore[import-not-found]
        for key in keys:
            value = keyring.get_password(KEYRING_SERVICE, key)
            if value:
                return value
    except Exception:
        pass
    try:
        data = json.loads((Path(state_dir) / SECRETS_FILE).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict):
        return None
    for key in keys:
        if isinstance(data.get(key), str):
            return data[key]
    nested = data.get(slug) if isinstance(data.get(slug), dict) else (data.get("ideas") or {}).get(slug)
    value = nested.get(todo_id) if isinstance(nested, dict) else None
    return value if isinstance(value, str) else None


ENV_NAME = re.compile(r"\b[A-Z][A-Z0-9_]{1,63}\b")


def env_name(title: str) -> str:
    """The environment variable a `secret` to-do's title names (`Add API_KEY` → `API_KEY`), else ""."""
    names = ENV_NAME.findall(title or "")
    return next((n for n in names if "_" in n), names[0] if names else "")
