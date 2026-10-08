"""Pairing a phone with this machine, and knowing it again (docs/design/mobile.md §2, §7).

    p = Pairing()
    code = p.new_code()                 # shown on the desktop as a QR code: good for 2 minutes, once
    p.pair(code, "Vadim's phone")       # → (device id, device token): the token goes to the phone, once
    p.device(token)                     # → the device, or None: forgotten, never paired, a guess
    p.forget(device_id)                 # at once: the listener closes its socket too (gui/phones.py)

A pairing code and a device token are 32 random bytes each. The host keeps only the token's SHA-256,
the device's name and when it was paired and last seen, in the machine's settings (`settings.save_phones`),
never in the Town Scroll: the scroll is committed to the project's git. A token is compared with
`secrets.compare_digest`, as the page's own is (`Server._token_ok`).

Pairing takes 5 attempts a minute; the 6th voids the code and locks pairing until the desktop shows a
new one. Commands take a few a second per device (`Bucket`).
"""
from __future__ import annotations

import datetime as dt
import hashlib
import secrets
import time
from dataclasses import dataclass, field

from orkcraft import settings

CODE_S = 120.0           # a pairing code is good for 2 minutes
ATTEMPTS = 5             # pairing attempts a minute; one more and pairing locks until a new code
ATTEMPT_WINDOW_S = 60.0
NAME_LIMIT = 60
SEEN_EVERY_S = 60.0      # how often "last seen" is written for a device that keeps talking
CMD_RATE = 5.0           # commands a second a device may send…
CMD_BURST = 10.0         # …and at most this many at once


class PairError(Exception):
    """Pairing refused; its text is what the phone is told."""


def digest(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _now_iso() -> str:
    return dt.datetime.now().isoformat(timespec="seconds")


def clean_name(name: object) -> str:
    """A device's name as the desktop shows it: one line of printable text."""
    text = "".join(ch for ch in str(name or "") if ch.isprintable()).strip()
    return text[:NAME_LIMIT] or "Phone"


@dataclass
class Bucket:
    """A token bucket: `take()` is False once a device sends faster than `rate` a second for long."""
    rate: float = CMD_RATE
    burst: float = CMD_BURST
    level: float = CMD_BURST
    at: float = field(default_factory=time.monotonic)

    def take(self, now: float | None = None) -> bool:
        now = time.monotonic() if now is None else now
        self.level = min(self.burst, self.level + (now - self.at) * self.rate)
        self.at = now
        if self.level < 1.0:
            return False
        self.level -= 1.0
        return True


class Pairing:
    def __init__(self, file=None) -> None:
        self.file = file                       # None: settings.path(), as the rest of the machine's settings
        self._code: str | None = None
        self._expires = 0.0
        self._attempts: list[float] = []
        self.locked = False                    # too many attempts: nothing pairs until a new code
        self._cache: tuple[tuple, list[dict]] | None = None
        self._seen: dict[str, float] = {}

    # -- the devices, as the settings file has them -------------------------------------------------

    def _path(self):
        return self.file or settings.path()

    def devices(self) -> list[dict]:
        """The paired devices, read again whenever the file changed (another town on this machine may
        have forgotten one)."""
        path = self._path()
        try:
            st = path.stat()
            key = (st.st_mtime_ns, st.st_size)
        except OSError:
            key = ()
        if self._cache is None or self._cache[0] != key:
            self._cache = (key, settings.load(path).phones if key else [])
        return [dict(d) for d in self._cache[1]]

    def port(self) -> int:
        return settings.load(self._path()).phone_port

    def _save(self, devices: list[dict], port: int | None = None) -> None:
        settings.save_phones(devices, self.port() if port is None else port, self._path())
        self._cache = None

    def save_port(self, port: int) -> None:
        self._save(self.devices(), port)

    def public(self) -> list[dict]:
        """What the desktop lists (Settings → Phones): never a token's hash."""
        return [{"id": d["id"], "name": d["name"], "paired": d["paired"], "seen": d["seen"]} for d in self.devices()]

    def device(self, token: str) -> dict | None:
        """The device this token is, compared in constant time against every one; None for anything else."""
        if not isinstance(token, str) or not token:
            return None
        want, found = digest(token), None
        for d in self.devices():
            if secrets.compare_digest(want, d["hash"]):
                found = d
        return found

    def known(self, device_id: str) -> bool:
        return any(d["id"] == device_id for d in self.devices())

    def seen(self, device_id: str, now: float | None = None) -> None:
        """The device talked: its "last seen", written at most once a minute."""
        now = time.monotonic() if now is None else now
        if now - self._seen.get(device_id, -SEEN_EVERY_S) < SEEN_EVERY_S:
            return
        self._seen[device_id] = now
        devices = self.devices()
        for d in devices:
            if d["id"] == device_id:
                d["seen"] = _now_iso()
                self._save(devices)
                return

    def forget(self, device_id: str) -> bool:
        devices = self.devices()
        kept = [d for d in devices if d["id"] != device_id]
        if len(kept) == len(devices):
            return False
        self._save(kept)
        self._seen.pop(device_id, None)
        return True

    # -- the pairing code ----------------------------------------------------------------------------

    def new_code(self, now: float | None = None) -> str:
        """A fresh one-time code: the one before it is void, and a lock lifts."""
        now = time.monotonic() if now is None else now
        self._code, self._expires = secrets.token_urlsafe(32), now + CODE_S
        self._attempts, self.locked = [], False
        return self._code

    def code_live(self, now: float | None = None) -> bool:
        now = time.monotonic() if now is None else now
        return self._code is not None and now < self._expires and not self.locked

    def expires_in(self, now: float | None = None) -> float:
        now = time.monotonic() if now is None else now
        return max(0.0, self._expires - now) if self.code_live(now) else 0.0

    def void(self) -> None:
        self._code = None

    def attempt(self, now: float | None = None) -> bool:
        """One more pairing attempt: False once there were too many this minute (the code is void and
        pairing locks until the desktop shows a new code)."""
        now = time.monotonic() if now is None else now
        if self.locked:
            return False
        self._attempts = [t for t in self._attempts if now - t < ATTEMPT_WINDOW_S] + [now]
        if len(self._attempts) > ATTEMPTS:
            self.locked, self._code = True, None
            return False
        return True

    def code_ok(self, code: object, now: float | None = None) -> bool:
        """Whether this is the live code (it stays live: `GET /api/version` may ask before pairing)."""
        if not self.code_live(now) or not isinstance(code, str) or not code:
            return False
        return secrets.compare_digest(code.encode("utf-8"), self._code.encode("utf-8"))

    def pair(self, code: object, name: object, now: float | None = None) -> tuple[str, str, str]:
        """The live code traded for a device token, once: (device id, token, name). The caller counts
        the attempt first (`attempt`)."""
        if self.locked:
            raise PairError("Pairing is locked: show a new code on the desktop")
        if not self.code_ok(code, now):
            raise PairError("That code is not the one on the desktop, or it ran out")
        self._code = None                      # once
        devices = self.devices()
        token, ids = secrets.token_urlsafe(32), {d["id"] for d in devices}
        device_id = secrets.token_hex(8)
        while device_id in ids:
            device_id = secrets.token_hex(8)
        label, stamp = clean_name(name), _now_iso()
        devices.append({"id": device_id, "name": label, "hash": digest(token), "paired": stamp, "seen": stamp})
        self._save(devices)
        return device_id, token, label
