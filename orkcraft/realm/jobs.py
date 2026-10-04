"""Jobs: one run of a script or an agent for a typed building, and their log.

Agent / Script runs its skill here; the Barracks runs its orcs' tasks here. A job runs off the UI
thread; the caller passes a `cancel` event and gets (text, cost, tokens) back or an exception.

    script   the skill is a command line, run in the repository with the input on stdin
    claude   `claude -p`; read-only in the repository unless `workdir` is given (a worktree)
    agy      `agy --print` in a sandbox limited to `workdir` (a scratch dir when none is given)
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

from orkcraft.realm import roads
from orkcraft.sources import telemetry

SCRIPT_TIMEOUT_S = 300
WORK_TIMEOUT_S = 1800
RESULT_KEEP = 4000
HARNESSES = ("claude", "agy", "script")


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


def _wait(proc: subprocess.Popen, cancel: threading.Event, timeout_s: int) -> None:
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
               env: dict | None = None, timeout_s: int = SCRIPT_TIMEOUT_S) -> tuple[str, None, None]:
    argv = shlex.split(command)
    if not argv:
        raise RuntimeError("the script is empty — ✎ Edit skill to set its command")
    try:
        proc = subprocess.Popen(argv, cwd=repo_root, env={**os.environ, **(env or {})}, stdin=subprocess.PIPE,
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


def work_cmd(harness: str, prompt: str, workdir: Path, model: str = "", resume: str = "") -> list[str]:
    """An agent that may change files — only inside `workdir` (a Barracks worktree)."""
    if harness == "claude":
        cmd = [os.environ.get("ORKCRAFT_CLAUDE_BIN", "claude"), "-p", prompt, "--output-format", "json",
               "--permission-mode", "acceptEdits"]
        return cmd + (["--model", model] if model else []) + (["--resume", resume] if resume else [])
    if harness == "agy":
        return [os.environ.get("ORKCRAFT_AGY_BIN", "agy"), "--print", prompt, "--model", model or roads.AGY_MODEL,
                "--mode", "accept-edits", "--sandbox", "--add-dir", str(workdir), "--output-format", "json"]
    raise RuntimeError(f"harness {harness!r} cannot work in a worktree")


def session_of(stdout: str) -> str:
    try:
        env = json.loads(stdout.strip())
    except ValueError:
        return ""
    return str(env.get("session_id", "")) if isinstance(env, dict) else ""


def run_work(harness: str, prompt: str, workdir: Path, cancel: threading.Event, model: str = "",
             env: dict | None = None, resume: str = "",
             timeout_s: int = WORK_TIMEOUT_S) -> tuple[str, float | None, int | None, str]:
    """(text, cost, tokens, session) of an agent working in `workdir`."""
    cmd = work_cmd(harness, prompt, workdir, model, resume)
    try:
        proc = subprocess.Popen(cmd, cwd=workdir, env={**os.environ, **(env or {})}, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, text=True, start_new_session=True)
    except FileNotFoundError as e:
        raise RuntimeError(f"{cmd[0]} not found") from e
    _wait(proc, cancel, timeout_s)
    out, err = proc.communicate()
    if proc.returncode != 0:
        raise RuntimeError(f"{harness} exited with {proc.returncode}: {(err or out).strip()[:300]}")
    text, cost, tokens = roads._result_of(out)
    if not telemetry.charged({**os.environ, **(env or {})}):
        telemetry.charge(cost, f"{harness} worker")
    return text, cost, tokens, session_of(out)


def run_skill(harness: str, skill: str, input_text: str, repo_root: Path, cancel: threading.Event,
              env: dict | None = None, agent_runner=None) -> tuple[str, float | None, int | None]:
    """Agent / Script: a script gets the input on stdin; an agent gets the skill and the input."""
    if harness == "script":
        return run_script(skill, input_text, repo_root, cancel, env)
    prompt = skill.strip() or "Summarise the input for the operator."
    if input_text:
        prompt += f"\n\n## Input\n\n{input_text}"
    prompt += "\n\nAnswer with the Markdown the operator should see and nothing else."
    runner = agent_runner or roads.run_agent
    answer = runner(harness, prompt, repo_root, env or {}, cancel)
    return answer[0], answer[1], answer[2] if len(answer) > 2 else None


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


# -- worktrees (the Barracks) --------------------------------------------------------------------------

def add_worktree(repo_root: Path, building_id: str, orc: str) -> tuple[Path, str]:
    """A worktree on `pool/<building>/<orc>` (realm/worktrees.py: `.orkcraft/worktrees/`); reused when there."""
    from orkcraft.realm import worktrees
    wid, branch = f"pool-{building_id}-{orc.lower()}".replace("_", "-"), f"pool/{building_id}/{orc.lower()}"
    path = worktrees.worktree_path(repo_root, wid)
    if (path / ".git").exists():
        return path, branch
    try:
        return worktrees.create(repo_root, wid, branch), branch
    except worktrees.WorktreeError as e:
        raise RuntimeError(str(e)) from e
