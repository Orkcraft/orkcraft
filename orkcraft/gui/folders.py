"""Choosing a folder for the Wiki (docs/design/wiki-folders-rules.md §2): the system's dialog, browsing,
the recent folders, a dropped folder.

A page (in the app's window or a browser) gets no path from a picker or a drop of its own, so the
server picks: pywebview's folder dialog in the app's window (`attach` hands it the window), else the
system's (`osascript`, `zenity`/`kdialog`, PowerShell). A dialog runs on a thread of its own — the
socket never waits for it —: `start` gives a token, `result` what came of it. `browse` lists folders for
a machine with no dialog. The app's window gives a dropped folder's full path (`pywebviewFullPath`):
`dropped` finds it by its name.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import threading
import time
import uuid
from pathlib import Path

PROMPT = "Choose a folder for the Wiki"
DIALOG_TIMEOUT_S = 15 * 60
DROP_FRESH_S = 10.0
BROWSE_MAX = 400

_window = None                                         # the app's pywebview window (launch.py)
_picks: dict[str, dict] = {}                           # token → {state: open | done | none | error, path, error}
_drops: list[tuple[float, str]] = []                   # (when, full path) of what was dropped on the window
_lock = threading.Lock()


class Unavailable(RuntimeError):
    """No dialog on this machine: browse instead."""


# -- the dialog -----------------------------------------------------------------------------------------

def attach(window) -> None:
    """The app's window: its own folder dialog, and the full paths of what is dropped on it."""
    global _window
    _window = window
    try:
        from webview.dom import DOMEventHandler
    except ImportError:
        return

    def listen() -> None:
        try:
            window.dom.document.events.drop += DOMEventHandler(on_drop, False, False)
        except Exception:                                  # an older pywebview: drops give no path
            pass
    try:
        window.events.loaded += listen
    except Exception:
        pass


def command(start: str = "", platform: str = sys.platform, which=shutil.which) -> list[str] | None:
    """The system's folder dialog as a command (None when this machine has none)."""
    start = start or str(Path.home())
    if platform == "darwin" and which("osascript"):
        where = start.replace("\\", "\\\\").replace('"', '\\"')
        return ["osascript", "-e", f'POSIX path of (choose folder with prompt "{PROMPT}" '
                                   f'default location (POSIX file "{where}"))']
    if platform.startswith("win"):
        ps = which("powershell") or which("pwsh")
        if ps:
            return [ps, "-NoProfile", "-STA", "-Command",
                    "Add-Type -AssemblyName System.Windows.Forms; $d = New-Object System.Windows.Forms.FolderBrowserDialog; "
                    f"$d.Description = '{PROMPT}'; if ($d.ShowDialog() -eq 'OK') {{ $d.SelectedPath }}"]
        return None
    if which("zenity"):
        return ["zenity", "--file-selection", "--directory", f"--title={PROMPT}", f"--filename={start.rstrip('/')}/"]
    if which("kdialog"):
        return ["kdialog", "--getexistingdirectory", start, "--title", PROMPT]
    return None


def native(start: str = "") -> str | None:
    """Ask with the system's dialog: the folder chosen, None when it was cancelled. Unavailable when there is none."""
    window = _window
    if window is not None:
        import webview
        kind = getattr(getattr(webview, "FileDialog", None), "FOLDER", None) or getattr(webview, "FOLDER_DIALOG")
        got = window.create_file_dialog(kind, directory=start or str(Path.home()))
        if not got:
            return None
        return str(got[0] if isinstance(got, (list, tuple)) else got)
    cmd = command(start)
    if cmd is None:
        raise Unavailable("no folder dialog on this machine")
    try:
        done = subprocess.run(cmd, capture_output=True, text=True, timeout=DIALOG_TIMEOUT_S)
    except (OSError, subprocess.TimeoutExpired) as e:
        raise Unavailable(str(e)) from None
    path = done.stdout.strip()
    return path.rstrip("/") or "/" if done.returncode == 0 and path else None


def start(begin: str = "", ask=None) -> str:
    """Open the dialog on a thread of its own: a token for `result`."""
    token = uuid.uuid4().hex[:12]
    ask = ask or native
    with _lock:
        _picks[token] = {"state": "open", "path": "", "error": ""}

    def run() -> None:
        try:
            path = ask(begin)
            got = {"state": "done", "path": path, "error": ""} if path else {"state": "none", "path": "", "error": ""}
        except Unavailable as e:
            got = {"state": "error", "path": "", "error": str(e) or "no folder dialog", "browse": True}
        except Exception as e:                                # a dialog must never take the server down
            got = {"state": "error", "path": "", "error": f"{type(e).__name__}: {e}"[:200], "browse": True}
        with _lock:
            _picks[token] = got

    threading.Thread(target=run, daemon=True, name="folder-dialog").start()
    return token


def result(token: str) -> dict:
    """What came of a dialog: {state: open | done | none | error, path, error}; done once it is read."""
    with _lock:
        got = dict(_picks.get(token) or {"state": "error", "path": "", "error": "no such dialog"})
        if got["state"] != "open":
            _picks.pop(token, None)
    return got


# -- browsing ---------------------------------------------------------------------------------------------

def browse(path: str = "") -> dict:
    """A folder's folders, for picking without a dialog: {path, parent, home, dirs: [{name, path}]}."""
    p = Path(path).expanduser() if path.strip() else Path.home()
    p = p.resolve()
    if not p.is_dir():
        raise ValueError(f"{path}: no such folder")
    try:
        names = sorted((e.name for e in os.scandir(p) if not e.name.startswith(".") and _is_dir(e)), key=str.lower)
    except OSError as e:
        raise ValueError(str(e)) from None
    return {"path": str(p), "parent": str(p.parent) if p.parent != p else "", "home": str(Path.home()),
            "dirs": [{"name": n, "path": str(p / n)} for n in names[:BROWSE_MAX]], "more": max(0, len(names) - BROWSE_MAX)}


def _is_dir(entry: os.DirEntry) -> bool:
    try:
        return entry.is_dir()
    except OSError:
        return False


# -- recent folders ---------------------------------------------------------------------------------------

def recent(machine) -> list[str]:
    """The folders last connected on this machine that are still there, newest first."""
    return [f for f in getattr(machine, "recent_folders", []) or [] if Path(f).is_dir()]


def remember(machine, folder: str, save=None) -> None:
    """Put a connected folder first among the recent ones and keep the machine's settings."""
    from orkcraft import settings
    folder = str(Path(folder).expanduser().resolve())
    machine.recent_folders = [folder, *(f for f in machine.recent_folders if f != folder)][:settings.RECENT_FOLDERS]
    try:
        (save or settings.save)(machine)
    except OSError:
        pass


# -- drops ------------------------------------------------------------------------------------------------

def on_drop(event: dict) -> None:
    """pywebview's drop on the window: the full paths it gives, kept a moment for `dropped`."""
    files = ((event or {}).get("dataTransfer") or {}).get("files") or []
    now = time.time()
    with _lock:
        _drops[:] = [d for d in _drops if now - d[0] < DROP_FRESH_S]
        for f in files:
            full = (f or {}).get("pywebviewFullPath") if isinstance(f, dict) else None
            if full:
                _drops.append((now, str(full)))


def dropped(names: list[str]) -> list[str]:
    """The full paths of what was just dropped with these names (the page knows names only)."""
    now = time.time()
    want = {n for n in names if n}
    with _lock:
        return [p for t, p in _drops if now - t < DROP_FRESH_S and Path(p).name in want]
