"""Jobs: one run of a script or an agent for a typed building, and their log.

Agent / Script runs its skill here; the Barracks runs its orcs' tasks here. A job runs off the UI
thread; the caller passes a `cancel` event and gets (text, cost, tokens) back or an exception.

    script   the skill is a command line, run in the repository with the input on stdin
    claude   `claude -p`; read-only in the repository unless `workdir` is given (a worktree)
    agy      `agy --print` in a sandbox limited to `workdir` (a scratch dir when none is given)
    codex    `codex exec` in a read-only sandbox; may write only inside `workdir` when one is given
"""
from __future__ import annotations

import datetime as dt
import json
import os
import shlex
import subprocess
import threading
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

from orkcraft.realm import halt, harnesses, roads
from orkcraft.sources import telemetry

SCRIPT_TIMEOUT_S = 300
WORK_TIMEOUT_S = 1800
RESULT_KEEP = 4000
HARNESSES = (*harnesses.ids(), "script")


@dataclass
class Job:
    id: str
    title: str
    harness: str
    input: str = ""
    model: str = ""
    orc: str = ""
    started: str = ""
    ended: str = ""
    outcome: str = ""            # running | done | error | interrupted
    result: str = ""
    error: str = ""
    cost_usd: float | None = None
    tokens: int | None = None
    trigger: str = "manual"      # manual | road | follow-up | new
    meta: dict = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return self.outcome == "done"


def now_iso() -> str:
    return dt.datetime.now().isoformat(timespec="seconds")


def _wait(proc: subprocess.Popen, cancel: threading.Event, timeout_s: int, who: str = "",
          agent: bool = False) -> None:
    """Until it ends, `cancel` is set (InterruptedError) or the time is up; 🛑 Halt All kills it (Halted)."""
    halt.started(proc, who, agent)
    try:
        _wait_for(proc, cancel, timeout_s)
    finally:
        halt.ended(proc)


def _wait_for(proc: subprocess.Popen, cancel: threading.Event, timeout_s: int) -> None:
    deadline = time.monotonic() + timeout_s
    while proc.poll() is None:
        if cancel.wait(0.2) or time.monotonic() > deadline:
            proc.terminate()
            try:
                proc.wait(5)
            except subprocess.TimeoutExpired:
                proc.kill()
            if cancel.is_set():
                raise InterruptedError("stopped")
            raise RuntimeError(f"no answer within {timeout_s} s")


def run_script(command: str, stdin: str, repo_root: Path, cancel: threading.Event,
               env: dict | None = None, timeout_s: int = SCRIPT_TIMEOUT_S,
               base_env: dict | None = None) -> tuple[str, None, None]:
    """`base_env` replaces the inherited environment (the Mill passes a clean one); `env` goes on top."""
    argv = shlex.split(command)
    if not argv:
        raise RuntimeError("the script is empty — ✎ Edit skill to set its command")
    try:
        base = os.environ if base_env is None else base_env
        proc = subprocess.Popen(argv, cwd=repo_root, env={**base, **(env or {})}, stdin=subprocess.PIPE,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, start_new_session=True)
    except FileNotFoundError as e:
        raise RuntimeError(f"{argv[0]} not found") from e
    if stdin:
        try:
            proc.stdin.write(stdin)
        except (BrokenPipeError, OSError):
            pass
    try:
        proc.stdin.close()
    except OSError:
        pass
    _wait(proc, cancel, timeout_s)
    out, err = proc.stdout.read(), proc.stderr.read()
    if proc.returncode != 0:
        raise RuntimeError(f"exit {proc.returncode}: {(err or out).strip()[:300]}")
    return out.strip(), None, None


def work_cmd(harness: str, prompt: str, workdir: Path, model: str = "", resume: str = "",
             dirs: tuple = ()) -> list[str]:
    """An agent that may change files — only inside `workdir` (a Barracks worktree); `dirs` it may read too."""
    h = harnesses.get(roads.resolve(harness))
    if h is None:
        raise RuntimeError(f"harness {harness!r} cannot work in a worktree")
    return h.work(prompt, workdir, model, resume if h.resumable else "", dirs)


def run_work(harness: str, prompt: str, workdir: Path, cancel: threading.Event, model: str = "",
             env: dict | None = None, resume: str = "",
             timeout_s: int = WORK_TIMEOUT_S, dirs: tuple = ()) -> tuple[str, float | None, int | None, str]:
    """(text, cost, tokens, session) of an agent working in `workdir` (and reading `dirs` too)."""
    harness = roads.resolve(harness)
    cmd = work_cmd(harness, prompt, workdir, model, resume, dirs)
    tool_env = h.env("work", workdir) if (h := harnesses.get(harness)) else {}
    run_env = {**os.environ, **tool_env, **(env or {})}
    resumed = roads.codex_thread_usage(resume, run_env) if harness == "codex" and resume else None
    before = resumed or 0
    code, out, err = roads.run_proc(cmd, workdir, run_env, roads.harness_stdin(harness, prompt),
                                    lambda proc: _wait(proc, cancel, timeout_s, run_env.get("ORKCRAFT_ORC") or harness, True),
                                    harness)
    if code != 0:
        raise roads.failure(harness, code, out, err)
    text, cost, tokens, session = roads.result_of(harness, out, before, model)
    if harness == "codex" and resume and resumed is None:
        cost = None                       # its running total holds earlier runs we cannot tell apart
    what = dict(tokens=tokens, building=telemetry.building_of(run_env), model=model)
    if not telemetry.charged(run_env):
        telemetry.charge(cost, f"{harness} worker", **what)
    else:
        telemetry.noted(cost, f"{harness} worker", **what)
    return text, cost, tokens, session


def run_read(harness: str, prompt: str, workdir: Path, cancel: threading.Event, model: str = "",
             env: dict | None = None, resume: str = "",
             timeout_s: int = WORK_TIMEOUT_S) -> tuple[str, float | None, int | None, str]:
    """(text, cost, tokens, "") of an agent that only reads, in `workdir` (harness mode `read`: no terminal, no
    file edits) — an Agent pool's reply (docs/design/barracks-flows.md §7). It starts fresh: no session."""
    harness = roads.resolve(harness)
    h = harnesses.get(harness)
    if h is None:
        raise RuntimeError(f"harness {harness!r} cannot read")
    cmd = h.read(prompt, workdir, model, False)
    run_env = {**os.environ, **h.env("read", workdir), **(env or {})}
    code, out, err = roads.run_proc(cmd, workdir, run_env, roads.harness_stdin(harness, prompt),
                                    lambda proc: _wait(proc, cancel, timeout_s, run_env.get("ORKCRAFT_ORC") or harness, True),
                                    harness)
    if code != 0:
        raise roads.failure(harness, code, out, err)
    text, cost, tokens, _session = roads.result_of(harness, out, 0, model)
    what = dict(tokens=tokens, building=telemetry.building_of(run_env), model=model)
    if not telemetry.charged(run_env):
        telemetry.charge(cost, f"{harness} reader", **what)
    else:
        telemetry.noted(cost, f"{harness} reader", **what)
    return text, cost, tokens, ""


class Log:
    """`runs.jsonl` of one building: newest last on disk, newest first when read."""

    def __init__(self, state_dir: Path, name: str = "runs.jsonl") -> None:
        self.path = state_dir / name

    def append(self, job: Job) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        row = asdict(job)
        row["result"] = row["result"][:RESULT_KEEP]
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    def trim(self, keep: int) -> None:
        """Keep only the newest `keep` runs on disk."""
        try:
            lines = self.path.read_text(encoding="utf-8").splitlines()
            if len(lines) > keep:
                self.path.write_text("\n".join(lines[-keep:]) + "\n", encoding="utf-8")
        except OSError:
            pass

    def read(self, limit: int = 50) -> list[Job]:
        try:
            lines = self.path.read_text(encoding="utf-8").splitlines()[-limit:]
        except OSError:
            return []
        out = []
        for line in reversed(lines):
            try:
                out.append(Job(**json.loads(line)))
            except (ValueError, TypeError):
                continue
        return out


# -- worktrees and task branches (the Barracks) ------------------------------------------------------

GIT_TIMEOUT_S = 60
TEST_TIMEOUT_S = 900
TEST_TAIL = 3000


def _git(cwd: Path, *args: str, timeout: int = GIT_TIMEOUT_S) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, timeout=timeout)


def _ok(proc: subprocess.CompletedProcess) -> str:
    if proc.returncode != 0:
        raise RuntimeError((proc.stderr or proc.stdout).strip()[:300] or f"git failed ({proc.returncode})")
    return proc.stdout.strip()


def add_worktree(repo_root: Path, building_id: str, orc: str) -> tuple[Path, str]:
    """The orc's own worktree (realm/worktrees.py: `.orkcraft/worktrees/`), detached: the branches
    belong to the tasks, not to the orc. Reused when there."""
    from orkcraft.realm import worktrees
    wid = f"pool-{building_id}-{orc.lower()}".replace("_", "-")
    path = worktrees.worktree_path(repo_root, wid)
    if (path / ".git").exists():
        return path, ""
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        _ok(_git(repo_root, "worktree", "add", "--detach", str(path), "HEAD"))
    except (RuntimeError, OSError, subprocess.SubprocessError) as e:
        raise RuntimeError(str(e)) from e
    return path, ""


class TaskGit:
    """The git a task needs: its branch from a fresh base, its diff, the tests, the push and the PR.
    Every call uses fixed arguments (no shell) except the operator's own `test_cmd`."""

    def base_of(self, repo_root: Path, configured: str = "") -> str:
        """The base branch: the configured one, else what the main checkout is on."""
        if configured:
            return configured
        try:
            head = _ok(_git(repo_root, "rev-parse", "--abbrev-ref", "HEAD"))
        except (RuntimeError, OSError, subprocess.SubprocessError):
            return "HEAD"
        return head if head and head != "HEAD" else _ok(_git(repo_root, "rev-parse", "HEAD"))

    def _has_origin(self, cwd: Path) -> bool:
        return _git(cwd, "remote").stdout.split().count("origin") > 0

    def prepare(self, workdir: Path, branch: str, base: str) -> None:
        """Put the worktree on `branch`: kept when it is there and not merged yet, else cut anew from
        the freshest `base` (origin's, when there is one). Leftovers of the last task are stashed."""
        if _git(workdir, "status", "--porcelain").stdout.strip():
            _git(workdir, "stash", "push", "--include-untracked", "-m", "orkcraft: leftovers")
        ref = base
        if self._has_origin(workdir) and _git(workdir, "fetch", "origin", base).returncode == 0:
            ref = f"origin/{base}"
        exists = _git(workdir, "show-ref", "--verify", "--quiet", f"refs/heads/{branch}").returncode == 0
        merged = exists and _git(workdir, "merge-base", "--is-ancestor", branch, ref).returncode == 0
        if exists and not merged:
            _ok(_git(workdir, "checkout", branch))
        else:
            _ok(_git(workdir, "checkout", "-B", branch, ref))

    def cut(self, repo_root: Path, branch: str, base: str) -> None:
        """A planned task's branch, which its parts are merged into: cut from the freshest `base` (origin's,
        when there is one), kept when it is there already."""
        if _git(repo_root, "show-ref", "--verify", "--quiet", f"refs/heads/{branch}").returncode == 0:
            return
        ref = base
        if self._has_origin(repo_root) and _git(repo_root, "fetch", "origin", base).returncode == 0:
            ref = f"origin/{base}"
        _ok(_git(repo_root, "branch", branch, ref))

    def merge(self, repo_root: Path, into: str, branch: str, message: str) -> tuple[bool, str]:
        """Merge `branch` into `into` without checking either out (`git merge-tree`, git 2.38+): (merged,
        the conflicting files or why not). `into` moves only when nobody moved it meanwhile."""
        old = _ok(_git(repo_root, "rev-parse", f"refs/heads/{into}"))
        if _git(repo_root, "merge-base", "--is-ancestor", branch, into).returncode == 0:
            return True, "already merged"
        tree = _git(repo_root, "merge-tree", "--write-tree", "--name-only", into, branch)
        if tree.returncode != 0:
            lines = tree.stdout.strip().splitlines()
            if tree.returncode == 1 and lines:
                files = [ln for ln in lines[1:] if ln and not ln.startswith(("Auto-merging", "CONFLICT"))]
                return False, "conflicts in " + ", ".join(dict.fromkeys(files)) if files else "conflicts"
            return False, (tree.stderr or tree.stdout).strip()[:300] or "git merge-tree failed"
        oid = tree.stdout.strip().splitlines()[0]
        commit = _ok(_git(repo_root, "commit-tree", oid, "-p", into, "-p", branch, "-m", message))
        _ok(_git(repo_root, "update-ref", f"refs/heads/{into}", commit, old))
        return True, "merged"

    def would_conflict(self, repo_root: Path, a: str, b: str) -> list[str] | None:
        """The files two branches would conflict in, merged together (`git merge-tree`: writes nothing):
        [] when they merge cleanly, None when git cannot tell (a branch gone, an old git)."""
        tree = _git(repo_root, "merge-tree", "--write-tree", "--name-only", a, b)
        if tree.returncode == 0:
            return []
        lines = tree.stdout.strip().splitlines()
        if tree.returncode != 1 or not lines:
            return None
        files = [ln for ln in lines[1:] if ln and not ln.startswith(("Auto-merging", "CONFLICT"))]
        return list(dict.fromkeys(files)) or ["(conflicts)"]

    def commit_file(self, repo_root: Path, branch: str, path: str, text: str, message: str) -> str:
        """Commit one file on `branch` without checking it out (a temporary index): the new commit's id.
        `branch` moves only when nobody moved it meanwhile."""
        import os
        import tempfile
        old = _ok(_git(repo_root, "rev-parse", f"refs/heads/{branch}"))
        with tempfile.TemporaryDirectory() as tmp:
            env = {**os.environ, "GIT_INDEX_FILE": str(Path(tmp) / "index")}

            def git(*args: str, data: str | None = None) -> str:
                return _ok(subprocess.run(["git", *args], cwd=repo_root, capture_output=True, text=True, input=data,
                                          env=env, timeout=GIT_TIMEOUT_S))
            git("read-tree", old)
            blob = git("hash-object", "-w", "--stdin", data=text)
            git("update-index", "--add", "--cacheinfo", f"100644,{blob},{path}")
            tree = git("write-tree")
            commit = git("commit-tree", tree, "-p", old, "-m", message)
        _ok(_git(repo_root, "update-ref", f"refs/heads/{branch}", commit, old))
        return commit

    def check(self, repo_root: Path, branch: str, command: str, cancel: threading.Event,
              where: Path) -> tuple[bool, str]:
        """The tests on `branch` as it is (the merged parts), in a worktree of the steward's own at `where`."""
        if not (where / ".git").exists():
            where.parent.mkdir(parents=True, exist_ok=True)
            _ok(_git(repo_root, "worktree", "add", "--detach", str(where), branch))
        else:
            if _git(where, "status", "--porcelain").stdout.strip():
                _git(where, "stash", "push", "--include-untracked", "-m", "orkcraft: leftovers")
            _ok(_git(where, "checkout", "--detach", branch))
        return self.test(where, command, cancel)

    def diff(self, workdir: Path, base: str, branch: str) -> tuple[int, str]:
        """(commits, diff) of the branch since it left the base."""
        ref = f"origin/{base}" if _git(workdir, "rev-parse", "--verify", "--quiet", f"origin/{base}").returncode == 0 \
            else base
        commits = int(_ok(_git(workdir, "rev-list", "--count", f"{ref}..{branch}")) or 0)
        return commits, _git(workdir, "diff", f"{ref}...{branch}").stdout

    def test(self, workdir: Path, command: str, cancel: threading.Event) -> tuple[bool, str]:
        """(passed, the output's tail) of the operator's test command, run in the worktree."""
        argv = shlex.split(command)
        if not argv:
            return True, ""
        try:
            proc = subprocess.Popen(argv, cwd=workdir, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                                    start_new_session=True)
        except FileNotFoundError:
            return False, f"{argv[0]} not found"
        _wait(proc, cancel, TEST_TIMEOUT_S)
        out = proc.stdout.read() if proc.stdout else ""
        return proc.returncode == 0, out[-TEST_TAIL:]

    def publish(self, workdir: Path, branch: str, base: str, title: str, body: str) -> tuple[str, str]:
        """(PR url, note): push the branch and open (or find) its pull request. No origin → the branch
        stays local; no `gh` → pushed without a PR."""
        import shutil
        if not self._has_origin(workdir):
            return "", "no remote: the branch stays local"
        push = _git(workdir, "push", "-u", "origin", branch, timeout=120)
        if push.returncode != 0:
            return "", f"push failed: {(push.stderr or push.stdout).strip()[:200]}"
        if not shutil.which("gh"):
            return "", "pushed; no gh to open the pull request"
        made = subprocess.run(["gh", "pr", "create", "--head", branch, "--base", base, "--title", title,
                               "--body", body], cwd=workdir, capture_output=True, text=True, timeout=120)
        url = (made.stdout.strip().splitlines() or [""])[-1]
        if made.returncode == 0 and url.startswith("http"):
            return url, "pull request opened"
        seen = subprocess.run(["gh", "pr", "view", branch, "--json", "url", "-q", ".url"], cwd=workdir,
                              capture_output=True, text=True, timeout=60)
        if seen.returncode == 0 and seen.stdout.strip():
            return seen.stdout.strip(), "pull request updated"
        return "", f"pushed; gh: {(made.stderr or made.stdout).strip()[:200]}"