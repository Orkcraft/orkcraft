"""The value of a `secret` to-do of an idea's plan (spec 29a §3): kept with the machine's secrets, never in a page,
in plan.json or in a prompt.

Where: the OS keychain through `keyring` when it is importable (service `orkcraft-ideas`, account
`<idea slug>/<to-do id>`), else `<state_dir>/secrets.json` with mode 600, git-ignored. plan.json says only
`"value": "stored"`; the runner reads the value back here and hands it to the task's session as an environment
variable named in the to-do's title.

    put(state_dir, "dark-mode", "t1", "sk-…")
    get(state_dir, "dark-mode", "t1") == "sk-…"
    forget(state_dir, "dark-mode")          # the idea was dropped

No face, no model, no bus.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

from orkcraft.env import getenv

SERVICE = "orkcraft-ideas"
FILE = "secrets.json"
_NAME = re.compile(r"^[a-z0-9-]+/[A-Za-z0-9_-]{1,40}$")

try:                                    # an optional extra: `pip install keyring`
    import keyring                      # type: ignore[import-not-found]
except ImportError:                     # pragma: no cover - depends on the machine
    keyring = None


def _keychain():
    """The keychain, unless the tests keep it out (`ORKCRAFT_LOGINS_FILE`, as realm/logins.py)."""
    return None if getenv("LOGINS_FILE") else keyring


def key(slug: str, todo_id: str) -> str:
    name = f"{slug}/{todo_id}"
    if not _NAME.match(name):
        raise ValueError("Not a to-do of an idea")
    return name


def _path(state_dir: Path) -> Path:
    return state_dir / FILE


def _read(state_dir: Path) -> dict:
    try:
        data = json.loads(_path(state_dir).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _write(state_dir: Path, data: dict) -> None:
    state_dir.mkdir(parents=True, exist_ok=True)
    _ignored(state_dir)
    tmp = _path(state_dir).with_suffix(".tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(json.dumps(data, indent=2) + "\n")
    os.chmod(tmp, 0o600)
    tmp.replace(_path(state_dir))


def _ignored(state_dir: Path) -> None:
    """`secrets.json` is git-ignored in the town's folder even where the folder itself is not."""
    path = state_dir / ".gitignore"
    try:
        have = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    except OSError:
        have = []
    if FILE not in have:
        path.write_text("\n".join([*have, FILE]) + "\n", encoding="utf-8")


def put(state_dir: Path, slug: str, todo_id: str, value: str) -> str:
    """Keep the value; where it went: "keychain" or "file"."""
    name = key(slug, todo_id)
    kc = _keychain()
    if kc is not None:
        try:
            kc.set_password(SERVICE, name, value)
            data = _read(state_dir)
            if name in data:                    # an older copy in the file goes
                data.pop(name)
                _write(state_dir, data)
            return "keychain"
        except Exception:                       # no secret service running: the file, as without it
            pass
    data = _read(state_dir)
    data[name] = value
    _write(state_dir, data)
    return "file"


def get(state_dir: Path, slug: str, todo_id: str) -> str | None:
    name = key(slug, todo_id)
    kc = _keychain()
    if kc is not None:
        try:
            value = kc.get_password(SERVICE, name)
            if value is not None:
                return value
        except Exception:
            pass
    value = _read(state_dir).get(name)
    return value if isinstance(value, str) else None


def forget(state_dir: Path, slug: str, todo_ids: list[str] = ()) -> None:
    """The idea's secrets go (all of the file's, and the keychain's for the to-dos named)."""
    kc = _keychain()
    for todo_id in todo_ids:
        try:
            if kc is not None:
                kc.delete_password(SERVICE, key(slug, todo_id))
        except Exception:
            pass
    data = _read(state_dir)
    kept = {k: v for k, v in data.items() if not k.startswith(f"{slug}/")}
    if kept != data:
        _write(state_dir, kept)
