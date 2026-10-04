"""🛑 Halt All for everything the camp runs: agents, model calls, scripts, tests and browsers.

Every child process orkcraft starts for work is registered here (`started` / `ended`, or the
`running` context). `halt_all` kills them all — the whole process group, so a harness's own
children go too — and moves the halt count on, so a loop that was between two steps (a browser
scout, a repair, a batch of judgements) sees `stopped_since` and gives up instead of starting the
next one. A process killed by the halt raises `Halted` (an InterruptedError) in its caller, never a
plain failure, so nothing reads a halt as "the model failed".
"""
from __future__ import annotations

import os
import signal
import subprocess
import threading
from contextlib import contextmanager
from typing import Iterator

_LOCK = threading.Lock()
_LIVE: set[subprocess.Popen] = set()
_KILLED: set[int] = set()            # pids the halt killed (their callers raise Halted)
_COUNT = 0                           # how many halts so far


class Halted(InterruptedError):
    """The work was stopped by 🛑 Halt All."""

    def __init__(self, what: str = "stopped by Halt All") -> None:
        super().__init__(what)


class Stopped(RuntimeError):
    """A short model call (`claude -p`) the halt killed: callers that read RuntimeError as "the model
    failed" stay safe; those that must not mistake it (the Lookout) catch it first."""

    def __init__(self) -> None:
        super().__init__("stopped by Halt All")


def count() -> int:
    with _LOCK:
        return _COUNT


def stopped_since(seen: int) -> bool:
    """A halt came after `seen` (a `count()` taken when the work started)."""
    return count() != seen


def check(seen: int) -> None:
    """Between two steps of a long job: raise `Halted` when a halt came since `seen`."""
    if stopped_since(seen):
        raise Halted()


def started(proc: subprocess.Popen) -> subprocess.Popen:
    with _LOCK:
        _LIVE.add(proc)
    return proc


def ended(proc: subprocess.Popen) -> None:
    """Forget the process; raise `Halted` when the halt is what ended it."""
    with _LOCK:
        _LIVE.discard(proc)
        killed = proc.pid in _KILLED
        _KILLED.discard(proc.pid)
    if killed:
        raise Halted()


@contextmanager
def running(proc: subprocess.Popen) -> Iterator[subprocess.Popen]:
    """`with halt.running(Popen(...)) as proc:` — registered while it runs; `Halted` if the halt killed it."""
    started(proc)
    try:
        yield proc
    except BaseException:
        with _LOCK:
            _LIVE.discard(proc)
            killed = proc.pid in _KILLED
            _KILLED.discard(proc.pid)
        if killed:
            raise Halted() from None
        raise
    ended(proc)


def _kill(proc: subprocess.Popen) -> None:
    try:
        if os.name == "posix" and os.getpgid(proc.pid) == proc.pid:      # its own session: the whole group
            os.killpg(proc.pid, signal.SIGKILL)
        else:
            proc.kill()
    except (OSError, ProcessLookupError):
        pass


def halt_all() -> int:
    """Kill every registered process that still runs; the number killed."""
    global _COUNT
    with _LOCK:
        _COUNT += 1
        live = [p for p in _LIVE if p.poll() is None]
        _KILLED.update(p.pid for p in live)
    for p in live:
        _kill(p)
    return len(live)


def run(argv: list[str], *, input: str | None = None, timeout: float | None = None,
        **popen: object) -> subprocess.CompletedProcess:
    """`subprocess.run(..., capture_output=True, text=True)` that Halt All can stop (its own process
    group). Raises subprocess.TimeoutExpired like it, and `Halted` when the halt killed it."""
    proc = subprocess.Popen(argv, stdin=subprocess.PIPE if input is not None else None, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, text=True, start_new_session=True, **popen)
    with running(proc):
        try:
            out, err = proc.communicate(input, timeout=timeout)
        except subprocess.TimeoutExpired:
            _kill(proc)
            proc.communicate()
            raise
    return subprocess.CompletedProcess(argv, proc.returncode, out, err)


def reset() -> None:
    """Tests: forget everything."""
    global _COUNT
    with _LOCK:
        _LIVE.clear()
        _KILLED.clear()
        _COUNT = 0
