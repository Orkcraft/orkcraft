"""Logins: the tokens the Watchtower listens with, kept on this machine and out of the project.

A spec never holds a token. It names one: an environment variable as before (`token=SLACK_TOKEN`),
or a login kept here (`token=keychain:slack-acme`). A login is a name and a secret; the secret goes
to the OS keychain when `keyring` is installed, else to `$XDG_CONFIG_HOME/orkcraft/logins.json` with
mode 0600 (`$ORKCRAFT_LOGINS_FILE` moves the file and keeps the keychain out, as tests do). The file
also lists every login (the keychain cannot list), with when it was saved and what for — never the
secret itself when the keychain holds it.

    save("slack-acme", "xoxp-…", service="slack", account="acme")
    resolve("keychain:slack-acme") == "xoxp-…"
    resolve("SLACK_TOKEN") == os.environ["SLACK_TOKEN"]

No model, no bus, no face: the Watchtower's form hands a token here and nothing else sees it.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import re
from pathlib import Path

from orkcraft.env import getenv

PREFIX = "keychain:"
NAME = re.compile(r"^[a-z0-9][a-z0-9._@:+-]{0,127}$")
REF = re.compile(r"^keychain:[a-z0-9][a-z0-9._@:+-]{0,127}$")
ENV_NAME = re.compile(r"^[A-Z][A-Z0-9_]{1,63}$")
SERVICE = "orkcraft"                    # the keychain's service name

try:                                    # an optional extra: `pip install keyring`
    import keyring                      # type: ignore[import-not-found]
except ImportError:                     # pragma: no cover - depends on the machine
    keyring = None


def is_ref(value: str) -> bool:
    return bool(REF.match(value or ""))


def is_name(value: str) -> bool:
    """A setting that may name a secret: an environment variable or a login."""
    return bool(ENV_NAME.match(value or "")) or is_ref(value)


def path() -> Path:
    env = getenv("LOGINS_FILE")
    if env:
        return Path(env).expanduser()
    base = os.environ.get("XDG_CONFIG_HOME", "").strip() or str(Path.home() / ".config")
    return Path(base) / "orkcraft" / "logins.json"


def _keychain():
    return None if getenv("LOGINS_FILE") else keyring


def _read() -> dict:
    try:
        data = json.loads(path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _write(data: dict) -> None:
    file = path()
    file.parent.mkdir(parents=True, exist_ok=True)
    tmp = file.with_suffix(file.suffix + ".tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(json.dumps(data, indent=2) + "\n")
    os.chmod(tmp, 0o600)
    tmp.replace(file)


def save(name: str, secret: str, service: str = "", account: str = "") -> str:
    """Keep `secret` as login `name`; its reference (`keychain:<name>`)."""
    if not NAME.match(name or ""):
        raise ValueError(f"{name!r} is not a login name")
    data = _read()
    entry = {"service": service, "account": account, "saved": dt.datetime.now().isoformat(timespec="seconds")}
    kc = _keychain()
    if kc is not None:
        try:
            kc.set_password(SERVICE, name, secret)
            entry["where"] = "keychain"
        except Exception:                               # no secret service running: the file, as without it
            kc = None
    if kc is None:
        entry["where"], entry["secret"] = "file", secret
    data[name] = entry
    _write(data)
    return PREFIX + name


def get(name: str) -> str:
    entry = _read().get(name)
    if not isinstance(entry, dict):
        return ""
    if entry.get("where") == "keychain":
        kc = keyring
        try:
            return (kc.get_password(SERVICE, name) or "") if kc is not None else ""
        except Exception:
            return ""
    return str(entry.get("secret") or "")


def resolve(value: str) -> str:
    """What a setting names: a login's secret (`keychain:<name>`), else the environment variable's value."""
    value = value or ""
    if value.startswith(PREFIX):
        return get(value[len(PREFIX):])
    return os.environ.get(value, "") if value else ""


def remove(name: str) -> bool:
    data = _read()
    entry = data.pop(name, None)
    if entry is None:
        return False
    if isinstance(entry, dict) and entry.get("where") == "keychain" and keyring is not None:
        try:
            keyring.delete_password(SERVICE, name)
        except Exception:
            pass
    _write(data)
    return True


def listed(service: str = "") -> list[dict]:
    """Every login (or one service's): name, service, account, where, saved — never the secret."""
    out = []
    for name, entry in sorted(_read().items()):
        if not isinstance(entry, dict) or (service and entry.get("service") != service):
            continue
        out.append({"name": name, **{k: str(entry.get(k) or "") for k in ("service", "account", "where", "saved")}})
    return out
