"""Keep the computer awake while Orkline runs: the screen may turn off, the machine does not sleep by itself,
so the orks go on working and a phone reaches the town (docs/design/mobile.md §10).

    awake = Awake()
    awake.apply(True)      # while the town is open (gui/launch.py); False or stop() lets it sleep again
    awake.how              # "caffeinate", "systemd-inhibit", "windows", or "" where nothing holds it

Each system's own way, and only against idle sleep — never the display, never a sleep the person asks for:

- macOS: `caffeinate -i -w <pid>`: it ends with this process, even when it is killed. A laptop's lid closed
  still sleeps it, unless it is on power with a display attached (the system's rule).
- Linux: `systemd-inhibit --what=sleep` around a `tail --pid=<pid>` that ends with this process.
- Windows: `SetThreadExecutionState(ES_CONTINUOUS | ES_SYSTEM_REQUIRED)` from a thread of its own.

Nothing found (no systemd, a container): it says so through `how` and does nothing. The setting is the
machine's (`keep_awake`, Town settings), on by default.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import threading
from typing import Callable

WHY = "Orkline is open: the orks keep working while the screen is off"
ES_CONTINUOUS, ES_SYSTEM_REQUIRED = 0x80000000, 0x00000001


def _argv(platform: str, pid: int, which: Callable[[str], str | None]) -> tuple[str, list[str]] | None:
    """(how, the command that holds the machine awake until `pid` ends), or None where none is found."""
    if platform == "darwin" and which("caffeinate"):
        return "caffeinate", ["caffeinate", "-i", "-w", str(pid)]
    if platform.startswith("linux") and which("systemd-inhibit") and which("tail"):
        return "systemd-inhibit", ["systemd-inhibit", "--what=sleep", "--who=Orkline", f"--why={WHY}",
                                   "--mode=block", "tail", f"--pid={pid}", "-f", "/dev/null"]
    return None


class Awake:
    def __init__(self, platform: str | None = None, popen=None, which=None) -> None:
        self.platform = platform or sys.platform
        self.popen = popen or subprocess.Popen
        self.which = which or shutil.which
        self.how = ""
        self.running = False                  # the town is open (gui/launch.py): the setting applies at once
        self._proc = None
        self._stop: threading.Event | None = None

    @property
    def on(self) -> bool:
        return bool(self.how)

    def apply(self, want: bool) -> str:
        """Hold the machine awake, or let it go; what holds it ("" for nothing)."""
        if want and not self.on:
            self._start()
        elif not want:
            self.stop()
        return self.how

    def _start(self) -> None:
        if self.platform == "win32":
            self._start_windows()
            return
        got = _argv(self.platform, os.getpid(), self.which)
        if got is None:
            return
        how, argv = got
        try:
            self._proc = self.popen(argv, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                    stderr=subprocess.DEVNULL)
        except OSError:
            return
        try:
            self._proc.wait(0.5)               # refused (no right to inhibit, no logind): it ends at once
            self._proc = None
            return
        except subprocess.TimeoutExpired:
            pass
        self.how = how

    def _start_windows(self) -> None:
        try:
            import ctypes
            kernel = ctypes.windll.kernel32   # type: ignore[attr-defined]
        except (ImportError, AttributeError, OSError):
            return
        stop, ready = threading.Event(), threading.Event()

        def hold() -> None:                   # the state is the thread's: it holds while this thread waits
            ok = kernel.SetThreadExecutionState(ES_CONTINUOUS | ES_SYSTEM_REQUIRED)
            ready.set()
            if ok:
                stop.wait()
                kernel.SetThreadExecutionState(ES_CONTINUOUS)

        threading.Thread(target=hold, name="orkcraft-awake", daemon=True).start()
        ready.wait(2)
        self._stop, self.how = stop, "windows"

    def stop(self) -> None:
        proc, self._proc = self._proc, None
        if proc is not None:
            try:
                proc.terminate()
                proc.wait(5)
            except Exception:                 # gone already, or slow: it ends with this process either way
                pass
        if self._stop is not None:
            self._stop.set()
            self._stop = None
        self.how = ""
