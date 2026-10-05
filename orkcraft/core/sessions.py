"""Sessions without a face: the orks' CLIs (Claude Code, Codex, agy) running on PTYs.

A face draws a session's bytes (the GUI in xterm.js) and sends it keys; the processes, what their
screens say and what they leave behind are the core's. Each session keeps a pyte screen of its own,
so the roster reads a question off it (`realm/roster.py`, `detect_prompt`) whatever face shows it,
and the last `BACKLOG` bytes, so a face that opens it later draws it as it stands.

    sessions = Sessions(town)
    sessions.on_output = lambda key, data: ...         # every chunk a session prints (the town's thread)
    key = sessions.new("claude")                        # a new Claude session in the War Tent
    key = sessions.deploy(orc, muster, treasury)        # a garrison ork with its orders (or a refusal, said)
    sessions.write(key, b"1")
    sessions.infos()                                    # WorkerInfo for the roster

A reader thread per session feeds its screen and hands each chunk to the town's thread
(`town.call`). A session that ends publishes `SESSION`; a deployed ork's ends sends its report down
the roads that take `on_task`, as the TUI's War Tent did.

The TUI still runs its own terminals (`widgets/terminal.py`); moving it onto this service is the
next step of stage 1 (docs/design/gui-migration.md §2).
"""
from __future__ import annotations

import os
import signal
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

import pyte

from orkcraft.core import bus
from orkcraft.core.town import Town
from orkcraft.realm import chronicles, pipes, worktrees
from orkcraft.realm.roster import WorkerInfo
from orkcraft.sources import sessions as past
from orkcraft.sources.sessions import HARNESS_AGY, HARNESS_CLAUDE, HARNESS_CODEX

BACKLOG = 512 * 1024          # bytes a session keeps for a face that opens it later
HARNESSES = (HARNESS_CLAUDE, HARNESS_CODEX, HARNESS_AGY)
COLS, ROWS = 100, 30


@dataclass
class Session:
    key: str
    command: list[str]
    harness: str
    title: str
    cwd: str
    env: dict[str, str] = field(default_factory=dict)
    ticket: str | None = None
    ork: str = ""                                    # "<building id>/<ork id>" of a deployed garrison ork
    pid: int | None = None
    fd: int | None = None
    running: bool = False
    exit_code: int | None = None
    started: float = field(default_factory=time.monotonic)
    last_output: float = field(default_factory=time.monotonic)

    def __post_init__(self) -> None:
        self.screen = pyte.Screen(COLS, ROWS)
        self.stream = pyte.ByteStream(self.screen)
        self.backlog = bytearray()
        self.lock = threading.Lock()

    def text_lines(self) -> list[str]:
        with self.lock:
            return [line.rstrip() for line in self.screen.display]

    def replay(self) -> bytes:
        with self.lock:
            return bytes(self.backlog)

    def feed(self, data: bytes) -> None:
        with self.lock:
            self.stream.feed(data)
            self.backlog += data
            if len(self.backlog) > BACKLOG:
                del self.backlog[:len(self.backlog) - BACKLOG]
            self.last_output = time.monotonic()


class Sessions:
    def __init__(self, town: Town) -> None:
        self.town = town
        self.live: dict[str, Session] = {}
        self.on_output: Callable[[str, bytes], None] = lambda key, data: None
        self._seq = 0

    # -- what runs ------------------------------------------------------------------------------

    def get(self, key: str) -> Session | None:
        return self.live.get(key)

    def infos(self) -> list[WorkerInfo]:
        """What the roster reads of every session (its questions come off the screen)."""
        now = time.monotonic()
        return [WorkerInfo(s.key, s.harness, s.title, s.ticket, s.text_lines(), now - s.last_output, s.running)
                for s in self.live.values()]

    def keys(self) -> list[str]:
        return list(self.live)

    def cwd(self) -> Path:
        """Where a new session runs: the active orkspace's worktree, else the repository."""
        town = self.town
        return worktrees.cwd_for(town.scroll, town.scroll.active_orkspace_id, town.repo_root)

    # -- opening one ----------------------------------------------------------------------------

    def open(self, key: str, command: list[str], harness: str, title: str,
             env: dict[str, str] | None = None, ticket: str | None = None, ork: str = "") -> Session:
        """Run `command` on a PTY as session `key` (one that still runs is kept as it is)."""
        s = self.live.get(key)
        if s is not None and s.running:
            return s
        merged = {**({"ORKCRAFT_TICKET": ticket} if ticket else {}), **(env or {})}
        if self.town.run_id:                 # 🪙 / 🪵: the hook tags the session with this run and terminal
            merged["ORKCRAFT_RUN"] = self.town.run_id
            merged["ORKCRAFT_TERMINAL"] = key
        s = Session(key, list(command), harness, title, str(self.cwd()), merged, ticket, ork)
        self.live[key] = s
        self._start(s)
        self.town.publish(bus.SESSION, key=key, state="opened")
        return s

    def new(self, harness: str, ticket: str | None = None) -> str:
        if harness not in HARNESSES:
            raise ValueError(f"No harness {harness!r}")
        self._seq += 1
        key = f"new:{harness}:{self._seq}"
        self.open(key, past.new_command(harness), harness, f"new {harness} session", ticket=ticket)
        return key

    def resume(self, session_key: str) -> str:
        """An earlier session of this project, reopened."""
        found = next((s for s in past.collect_sessions(self.town.repo_root) if s.key == session_key), None)
        if found is None:
            raise ValueError("That session is not in this project's history")
        command = past.resume_command(found)
        if command is None:
            raise ValueError(f"A cloud session: open {found.url}" if found.url else "This session cannot be reopened here")
        ork = next(iter(found.orcs), "")
        self.open(found.key, command, found.harness, found.title or found.short_id, ork=ork)
        return found.key

    def deploy(self, ork_ref: str, muster, treasury, first_message: str = "") -> str | None:
        """A garrison ork's session: its running one (the message typed into it), else a new one on its
        orders. None, said why, when supply or gold is out or its harness cannot be deployed."""
        town = self.town
        b_id, _, ork_id = ork_ref.partition("/")
        b_spec = town.scroll.building(b_id)
        m_spec = next((m for m in b_spec.garrison.members if m.id == ork_id), None) if b_spec else None
        if m_spec is None:
            raise ValueError(f"No ork {ork_ref!r}")
        running = next((s for s in self.live.values() if s.ork == ork_ref and s.running), None)
        if running is not None:
            if first_message:
                self.write(running.key, (first_message + "\r").encode())
            return running.key
        budget = town.scroll.budget
        if muster.roster.active >= budget.supply_max_workers:
            town.toast(f"Supply {muster.roster.active}/{budget.supply_max_workers}: stop a session first",
                       title="Not enough food", severity="warning")
            return None
        if treasury.exhausted():
            return None
        prompt = f"You are {m_spec.name}, {m_spec.role}, a garrison orc of the {b_spec.title} building in orkcraft."
        if m_spec.orders:
            prompt += f" Orders: {m_spec.orders}"
        if first_message:
            prompt += f"\n\nThe operator says: {first_message}"
        first = (m_spec.harness[0].get("harness") if m_spec.harness else "") or HARNESS_CLAUDE
        harness = first if first == HARNESS_CODEX else HARNESS_CLAUDE     # agy's orks deploy as Claude
        command = past.deploy_command(harness, prompt)
        if command is None:
            town.toast("This ork's harness cannot be deployed yet", title="Deploy", severity="warning")
            return None
        self._seq += 1
        key = f"deploy:{ork_ref}:{self._seq}"
        self.open(key, command, harness, f"{m_spec.name} · {b_spec.title}", env={"ORKCRAFT_ORC": ork_ref}, ork=ork_ref)
        muster.deployments[key] = ork_ref
        town.record(b_id, "orc_deployed", orc=m_spec.name, harness=harness)
        return key

    # -- talking to one -------------------------------------------------------------------------

    def write(self, key: str, data: bytes) -> bool:
        s = self.live.get(key)
        if s is None or not s.running or s.fd is None:
            return False
        try:
            os.write(s.fd, data)
            return True
        except OSError:
            return False

    def resize(self, key: str, cols: int, rows: int) -> None:
        s = self.live.get(key)
        if s is None:
            return
        cols, rows = max(int(cols), 20), max(int(rows), 5)
        with s.lock:
            if (rows, cols) == (s.screen.lines, s.screen.columns):
                return
            s.screen.resize(rows, cols)
        self._winsize(s, rows, cols)
        if s.running and s.pid is not None:
            try:
                os.kill(s.pid, signal.SIGWINCH)
            except ProcessLookupError:
                pass

    def interrupt(self, key: str) -> bool:
        """Ctrl+C for the CLI: it cancels its turn and keeps the session."""
        s = self.live.get(key)
        if s is None or not s.running or s.pid is None:
            return False
        try:
            os.kill(s.pid, signal.SIGINT)
            return True
        except ProcessLookupError:
            return False

    def interrupt_all(self) -> int:
        return sum(self.interrupt(k) for k in list(self.live))

    def stop(self, key: str) -> None:
        s = self.live.get(key)
        if s is not None and s.running and s.pid is not None:
            try:
                os.kill(s.pid, signal.SIGHUP)
            except ProcessLookupError:
                pass

    def forget(self, key: str) -> None:
        """A finished session leaves the list (a running one is stopped first)."""
        self.stop(key)
        self.live.pop(key, None)
        self.town.publish(bus.SESSION, key=key, state="forgotten")

    def close(self) -> None:
        for key in list(self.live):
            self.stop(key)

    # -- the process ----------------------------------------------------------------------------

    @staticmethod
    def _winsize(s: Session, rows: int, cols: int) -> None:
        if s.fd is None:
            return
        import fcntl
        import struct
        import termios
        try:
            fcntl.ioctl(s.fd, termios.TIOCSWINSZ, struct.pack("HHHH", rows, cols, 0, 0))
        except OSError:
            pass

    def _start(self, s: Session) -> None:
        import pty
        env = {**os.environ, "TERM": "xterm-256color", "COLORTERM": "truecolor", **s.env}
        pid, fd = pty.fork()
        if pid == 0:                                      # the child
            try:
                os.chdir(s.cwd)
                os.execvpe(s.command[0], s.command, env)
            except Exception as e:                        # exec failed: say why, then leave
                os.write(2, f"orkcraft: cannot run {s.command[0]}: {e}\r\n".encode())
            os._exit(127)
        s.pid, s.fd, s.running = pid, fd, True
        self._winsize(s, s.screen.lines, s.screen.columns)
        threading.Thread(target=self._read, args=(s,), daemon=True, name=f"session-{s.key}").start()

    def _read(self, s: Session) -> None:
        while True:
            try:
                data = os.read(s.fd, 65536)
            except OSError:
                data = b""
            if not data:
                break
            s.feed(data)
            self.town.call(self.on_output, s.key, data)
        code = None
        try:
            _, status = os.waitpid(s.pid, 0)
            code = os.waitstatus_to_exitcode(status)
        except ChildProcessError:
            pass
        try:
            os.close(s.fd)
        except OSError:
            pass
        tail = f"\r\n\x1b[2m[process exited{'' if code is None else f' with {code}'}]\x1b[0m".encode()
        s.feed(tail)
        self.town.call(self._finished, s, code, tail)

    def _finished(self, s: Session, code: int | None, tail: bytes) -> None:
        s.running, s.exit_code = False, code
        self.on_output(s.key, tail)
        self.town.publish(bus.SESSION, key=s.key, state="exited", code=code)
        if s.ork:
            self._report(s)

    def _report(self, s: Session) -> None:
        """A deployed ork went home: the chronicle says so, and its last screen goes down the roads
        that take `on_task`."""
        town = self.town
        b_id, _, ork_id = s.ork.partition("/")
        b_spec = town.scroll.building(b_id)
        m_spec = next((m for m in b_spec.garrison.members if m.id == ork_id), None) if b_spec else None
        name = m_spec.name if m_spec else ork_id
        try:
            chronicles.record(town.repo_root, town.scroll, b_id, "orc_returned", orc=name, by=name)
        except OSError:
            pass
        if b_spec is None or not town.roads.has_roads(b_id, pipes.ON_TASK):
            return
        title, md = pipes.task_report(name, b_spec.title, s.text_lines())
        cwd, root = Path(s.cwd), town.repo_root
        worktree = str(cwd.relative_to(root)) if cwd != root and root in cwd.parents else ""
        hop = pipes.hop(b_id, ork_id, "task", worktree=worktree, outcome="done")
        town.roads.emit(pipes.Payload(kind=pipes.TEXT, value=md, source=b_id, mode=pipes.ON_TASK, title=title,
                                      trail=(hop,)))
