"""Anonymous usage stats (docs/usage-stats.md): which features are used, never what is in them.

Off until the operator says yes (Settings, or `orkcraft usage on`). Then a short closed list of
events — each with only the properties named in `EVENTS`, each a word from a known set or a bucket —
goes in batches to Orkcraft's own proxy (tools/usage-worker/), which holds the analytics key and
passes them on to Amplitude. No code, prompt, path, file or project name, no text an ork or a person
wrote, no IP address: the proxy drops it before Amplitude sees the request.

    u = Usage(town.machine, face="gui", demo=town.demo)
    u.track("building_built", type="lake")   # an unknown event or property is dropped, never sent
    u.tick(time.monotonic())                 # from the host's clock: a batch at most once a minute
    u.close()                                # the window closed: what is left goes, briefly

Nothing is collected while `DO_NOT_TRACK` or `ORKCRAFT_NO_USAGE` is set, under CI, in the demo, or
while `ENDPOINT` is empty. `ORKCRAFT_USAGE_DEBUG=1` prints each batch to stderr instead of sending it.
"""
from __future__ import annotations

import json
import os
import platform
import sys
import threading
import time
import urllib.error
import urllib.request
import uuid
from typing import Any, Callable

from orkcraft import __version__, autonomy, settings
from orkcraft.env import getenv
from orkcraft.realm import catalog, growth

# The proxy's address (tools/usage-worker/README.md). Empty: nothing leaves the machine.
ENDPOINT = ""
FLUSH_S = 60.0           # a batch at most this often
BATCH = 50               # …or as soon as this many wait
KEEP = 200               # what waits when the proxy cannot be reached: the oldest go first
TIMEOUT_S = 5.0
CLOSE_TIMEOUT_S = 2.0    # the window never waits longer than this for the last batch

COUNTS = ("0", "1", "2-5", "6-10", "11+")
MINUTES = ("<5", "5-30", "30-120", "120+")

# Every event and every property it may carry; the proxy keeps the same list (tools/usage-worker/worker.js).
EVENTS: dict[str, dict[str, Callable[[Any], bool]]] = {
    "app_opened": {"face": lambda v: v in ("gui", "tui"),
                   "tools": lambda v: isinstance(v, list) and all(t in settings.TOOLS for t in v),
                   "buildings": lambda v: v in COUNTS, "roads": lambda v: v in COUNTS},
    "app_closed": {"minutes": lambda v: v in MINUTES},
    "building_built": {"type": lambda v: v in catalog.TYPES},
    "building_demolished": {},
    "road_laid": {},
    "session_opened": {"harness": lambda v: v in settings.TOOLS},
    "deed_earned": {"deed": lambda v: v in {d.id for d in growth.DEEDS}},
    "stage_reached": {"stage": lambda v: v in (1, 2, 3, 4)},
    "autonomy_set": {"level": lambda v: v in autonomy.WORDS},
    "halted": {},
}


def count(n: int) -> str:
    """A number of things as a bucket: no exact count leaves the machine."""
    return "0" if n <= 0 else "1" if n == 1 else "2-5" if n <= 5 else "6-10" if n <= 10 else "11+"


def minutes(seconds: float) -> str:
    m = seconds / 60
    return "<5" if m < 5 else "5-30" if m < 30 else "30-120" if m < 120 else "120+"


def _set(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() not in ("", "0", "false", "no")


def blocked() -> str:
    """Why nothing is collected whatever the operator said, or "" when nothing stops it."""
    if _set("DO_NOT_TRACK"):
        return "DO_NOT_TRACK is set"
    if getenv("NO_USAGE") not in ("", "0"):
        return "ORKCRAFT_NO_USAGE is set"
    if _set("CI"):
        return "running under CI"
    return ""


def endpoint() -> str:
    return getenv("USAGE_URL") or ENDPOINT


def debug() -> bool:
    return getenv("USAGE_DEBUG") not in ("", "0")


def share(machine: settings.MachineSettings, on: bool) -> None:
    """The operator's answer. Off forgets the install id, so a later yes starts as a new install."""
    machine.usage = bool(on)
    machine.install_id = (machine.install_id or uuid.uuid4().hex) if on else ""


def clean(event: str, props: dict[str, Any]) -> dict[str, Any] | None:
    """Only the properties `EVENTS` names, each with a value it allows; None for an unknown event."""
    allowed = EVENTS.get(event)
    if allowed is None:
        return None
    return {k: v for k, v in props.items() if k in allowed and allowed[k](v)}


class Usage:
    def __init__(self, machine: settings.MachineSettings, face: str = "gui", demo: bool = False,
                 send: Callable[[str, bytes], None] | None = None) -> None:
        self.machine = machine
        self.face = face
        self.demo = demo
        self.started = time.time()
        self.session_id = int(self.started * 1000)   # Amplitude's session: when this one began, in ms
        self._send = send or _post
        self._queue: list[dict[str, Any]] = []
        self._lock = threading.Lock()
        self._sent_at = time.monotonic()

    def enabled(self) -> bool:
        return (self.machine.usage is True and bool(self.machine.install_id) and not self.demo
                and not blocked() and bool(endpoint() or debug()))

    def should_ask(self) -> bool:
        """The operator has not answered yet and an answer would matter here."""
        return self.machine.usage is None and not self.demo and not blocked() and bool(endpoint())

    def track(self, event: str, **props: Any) -> None:
        if not self.enabled():
            return
        kept = clean(event, props)
        if kept is None:
            return
        with self._lock:
            self._queue.append({"event": event, "time": int(time.time() * 1000), "props": kept})
            full = len(self._queue) >= BATCH
        if full:
            self.flush()

    def tick(self, now: float) -> None:
        if now - self._sent_at >= FLUSH_S:
            self._sent_at = now
            self.flush()

    def flush(self, wait: float | None = None) -> None:
        """What waits goes on a thread of its own; `wait` seconds at most for it (None: no wait)."""
        with self._lock:
            batch, self._queue = self._queue, []
        if not batch:
            return
        if not self.enabled():          # the operator said no meanwhile: what waited is forgotten
            return
        body = self.payload(batch)
        if debug():
            sys.stderr.write("orkcraft usage: " + json.dumps(body, ensure_ascii=False) + "\n")
            return
        thread = threading.Thread(target=self._deliver, args=(batch, body), daemon=True, name="usage")
        thread.start()
        if wait:
            thread.join(wait)

    def _deliver(self, batch: list[dict[str, Any]], body: dict[str, Any]) -> None:
        try:
            self._send(endpoint(), json.dumps(body).encode("utf-8"))
        except urllib.error.HTTPError as e:     # refused: only a busy or broken proxy is worth a second try
            if e.code == 429 or e.code >= 500:
                self._keep(batch)
        except Exception:               # unreachable: the stats never trouble the town, they wait
            self._keep(batch)

    def _keep(self, batch: list[dict[str, Any]]) -> None:
        with self._lock:
            self._queue = (batch + self._queue)[-KEEP:]

    def payload(self, batch: list[dict[str, Any]]) -> dict[str, Any]:
        return {"install_id": self.machine.install_id, "session_id": self.session_id,
                "app_version": __version__, "os": platform.system().lower() or "unknown",
                "python": ".".join(platform.python_version_tuple()[:2]), "events": batch}

    def close(self) -> None:
        self.track("app_closed", minutes=minutes(time.time() - self.started))
        self.flush(wait=CLOSE_TIMEOUT_S)


def _post(url: str, data: bytes) -> None:
    request = urllib.request.Request(url, data=data, method="POST", headers={
        "Content-Type": "application/json", "User-Agent": f"orkcraft/{__version__}"})
    with urllib.request.urlopen(request, timeout=TIMEOUT_S):   # an answer of 4xx/5xx raises HTTPError
        pass
