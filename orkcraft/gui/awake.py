"""Keep the computer awake while the orks work: the screen may turn off, the machine does not sleep by itself, so
carts in work go on while the person is away (docs/design/audience.md §2a, leaving the camp; mobile.md §10).

    awake = Awake()
    awake.apply(True)      # while carts are in work, on power, under the cap (gui/host.py `keep_awake`); False lets it sleep
    awake.how              # "caffeinate", "systemd-inhibit", "windows", or "" where nothing holds it
    on_power()             # True on mains power (or a machine with no battery), False on battery, None unknown

The host holds it only while carts are in work in an Agent pool (core/leaving.py) and the computer is on power, and
lets go when the work is done or the cap of a day away is reached; with "Stay reachable from your phone" also while a
phone is paired, carts or not (gui/away.py `reason`, decisions-2026-10 §18). A laptop on battery is never kept awake.

Each system's own way, and only against idle sleep — never the display, never a sleep the person asks for:

- macOS: `caffeinate -i -w <pid>`: it ends with this process, even when it is killed. A laptop's lid closed
  still sleeps it, unless it is on power with a display attached (the system's rule).
- Linux: `systemd-inhibit --what=sleep` around a `tail --pid=<pid>` that ends with this process.
- Windows: `SetThreadExecutionState(ES_CONTINUOUS | ES_SYSTEM_REQUIRED)` from a thread of its own.

Nothing found (no systemd, a container): it says so through `how` and does nothing. The setting is the
machine's (`keep_awake`, Town settings: off | carts | phone), "carts" by default.

Power: macOS `pmset -g batt` ("AC Power"), Linux `/sys/class/power_supply` (a Mains supply online, or no battery at
all), Windows `GetSystemPowerStatus`. A machine that tells nothing counts as on power (a desktop).
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import threading
from pathlib import Path
from typing import Callable

WHY = "Orkline: the orks keep working, and a paired phone reaches the town, while the screen is off"
ES_CONTINUOUS, ES_SYSTEM_REQUIRED = 0x80000000, 0x00000001


def _argv(platform: str, pid: int, which: Callable[[str], str | None]) -> tuple[str, list[str]] | None:
    """(how, the command that holds the machine awake until `pid` ends), or None where none is found."""
    if platform == "darwin" and which("caffeinate"):
        return "caffeinate", ["caffeinate", "-i", "-w", str(pid)]
    if platform.startswith("linux") and which("systemd-inhibit") and which("tail"):
        return "systemd-inhibit", ["systemd-inhibit", "--what=sleep", "--who=Orkline", f"--why={WHY}",
                                   "--mode=block", "tail", f"--pid={pid}", "-f", "/dev/null"]
    return None


POWER_SUPPLY = Path("/sys/class/power_supply")


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def on_power(platform: str | None = None, run=None, supplies: Path | None = None) -> bool | None:
    """Whether the computer is on mains power: True (or no battery), False on battery, None when it cannot tell."""
    platform = platform or sys.platform
    if platform == "darwin":
        try:
            out = (run or subprocess.run)(["pmset", "-g", "batt"], capture_output=True, text=True, timeout=5).stdout
        except (OSError, subprocess.SubprocessError):
            return None
        if "AC Power" in out:
            return True
        return False if "Battery Power" in out else None
    if platform.startswith("linux"):
        base = supplies or POWER_SUPPLY
        try:
            kinds = [(_read(d / "type"), _read(d / "online")) for d in base.iterdir()]
        except OSError:
            return None
        if any(k == "Mains" and online == "1" for k, online in kinds):
            return True
        return False if any(k == "Battery" for k, _ in kinds) else True
    if platform == "win32":
        try:
            import ctypes

            class Status(ctypes.Structure):
                _fields_ = [("ACLineStatus", ctypes.c_byte), ("BatteryFlag", ctypes.c_byte),
                            ("BatteryLifePercent", ctypes.c_byte), ("SystemStatusFlag", ctypes.c_byte),
                            ("BatteryLifeTime", ctypes.c_ulong), ("BatteryFullLifeTime", ctypes.c_ulong)]
            status = Status()
            if not ctypes.windll.kernel32.GetSystemPowerStatus(ctypes.byref(status)):   # type: ignore[attr-defined]
                return None
        except (ImportError, AttributeError, OSError):
            return None
        return {1: True, 0: False}.get(status.ACLineStatus)
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

    def can(self) -> bool:
        """This system has a way to hold it (whether it holds now or not)."""
        return self.platform == "win32" or _argv(self.platform, os.getpid(), self.which) is not None

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
