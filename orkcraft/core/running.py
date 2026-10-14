"""Since when this machine runs Orkline's code as it is now (docs/design/improve-buildings.md §13): the moment the
latest change to the code was applied — an update installed, a `git pull` in a checkout — so Improve can read the logs
of the work done on it, and no older.

The code is known by its version and, in a git checkout (bin/orkcraft, `pip install -e`), by the commit it stands on.
The first time a code is seen, now is kept as its start in `~/.orkcraft/running.json`; a later start on the same code
keeps the first.

    running.mark()       the code now and since when: {"code", "since"}, kept on first sight
    running.since()      that moment, as a datetime
"""
from __future__ import annotations

import datetime as dt
import json
import subprocess
from pathlib import Path

import orkcraft
from orkcraft.env import getenv

FILE = "running.json"


def _path() -> Path:
    return Path(getenv("STATE_DIR") or Path.home() / ".orkcraft") / FILE


def checkout() -> Path | None:
    """The git checkout Orkline runs from, or None."""
    from orkcraft.core import updates
    return updates._checkout(Path(orkcraft.__file__).resolve().parent)


def code() -> str:
    """The version, and the checkout's commit when it runs from one: `0.2.9` or `0.2.9+1a2b3c4d5e6f`."""
    root = checkout()
    if root is not None:
        try:
            got = subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"], capture_output=True, text=True,
                                 timeout=10)
            if got.returncode == 0 and got.stdout.strip():
                return f"{orkcraft.__version__}+{got.stdout.strip()[:12]}"
        except (OSError, subprocess.SubprocessError):
            pass
    return orkcraft.__version__


def mark(now: dt.datetime | None = None, path: Path | None = None) -> dict:
    path = path or _path()
    now_code = code()
    try:
        kept = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(kept, dict) and kept.get("code") == now_code and dt.datetime.fromisoformat(kept["since"]):
            return kept
    except (OSError, ValueError, KeyError, TypeError):
        pass
    kept = {"code": now_code, "since": (now or dt.datetime.now()).isoformat(timespec="seconds")}
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(kept), encoding="utf-8")
    except OSError:
        pass
    return kept


def since(path: Path | None = None) -> dt.datetime:
    return dt.datetime.fromisoformat(mark(path=path)["since"])
