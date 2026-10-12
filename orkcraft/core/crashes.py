"""Crash reports (docs/crash-reports.md): where in Orkcraft's code something broke, never what was in it.

One answer with the usage stats (core/usage.py): off until the operator says yes. Then an error
nobody caught, a command that broke, a part of the town's clock that failed or an error of the window
goes to Orkcraft's proxy (tools/usage-worker/, `/v1/crash`), which holds the Sentry key and passes
it on as a Sentry event. Each run is a Sentry session too (ok, exited, crashed, or abnormal when the
process died without closing), so Sentry can say which share of runs of each version ended well.

What a report holds: the exception's type, its message scrubbed (`scrub`: no paths, URLs, addresses
or quoted text), and the stack as file, function and line — Orkcraft's files by their path in the
package, a library's by its own, anything else as `<other>` with no function name. No local
variables, no prompt, no log, no project or building name.

    r = crashes.install(machine, face="gui", demo=demo)   # the hooks; a session starts
    crashes.capture(e, where="command")                    # a caught error that should not happen
    r.close()                                              # the session ends; the hooks go

Whatever was answered, each crash is also written to `~/.orkcraft/crashes/` (the full traceback,
on this machine only), so it can be attached to an issue. `ORKCRAFT_USAGE_DEBUG=1` prints each
report instead of sending it.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import platform
import re
import sys
import sysconfig
import threading
import time
import traceback
import urllib.error
import urllib.request
import uuid
from pathlib import Path
from types import TracebackType
from typing import Any, Callable

from orkcraft import __version__, settings
from orkcraft.core import usage
from orkcraft.env import getenv

WHERE = ("unhandled", "thread", "asyncio", "command", "clock", "window")
STATUSES = ("ok", "exited", "crashed", "abnormal")
MAX_EVENTS = 20          # reports from one run at most; the same error twice goes once
MAX_FRAMES = 40
MAX_VALUE = 300
KEEP_LOGS = 30           # local crash files kept
TIMEOUT_S = 5.0

PACKAGE = Path(__file__).resolve().parents[1]          # …/orkcraft
_STDLIB = Path(sysconfig.get_paths()["stdlib"]).resolve()


def endpoint() -> str:
    """The proxy's crash address: `ORKCRAFT_CRASH_URL`, else beside the usage stats' `/v1/events`."""
    own = getenv("CRASH_URL")
    if own:
        return own
    events = usage.endpoint()
    return events[: -len("/v1/events")] + "/v1/crash" if events.endswith("/v1/events") else ""


def log_dir() -> Path:
    return Path(getenv("CRASH_DIR") or Path.home() / ".orkcraft" / "crashes")


# -- what a report may say -----------------------------------------------------------------------

_URL = re.compile(r"\b[a-z][a-z0-9+.-]*://\S+", re.I)
_EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_PATH = re.compile(r"(?:~|[A-Za-z]:\\|\\\\|/)[^\s'\"(),:;]*[/\\][^\s'\"(),:;]*|~[/\\]?[^\s'\"(),:;]*")
_QUOTED = re.compile(r"'[^']*'|\"[^\"]*\"")


def scrub(text: str) -> str:
    """An error's message with nothing of the person's in it: paths, URLs, e-mail addresses and
    anything quoted (a file, a key, a name) become placeholders; at most `MAX_VALUE` characters."""
    text = str(text).replace(str(Path.home()), "~")
    text = _URL.sub("<url>", text)
    text = _EMAIL.sub("<email>", text)
    text = _QUOTED.sub("'…'", text)
    text = _PATH.sub("<path>", text)
    text = " ".join(text.split())
    return text[:MAX_VALUE]


def _site(path: Path) -> str | None:
    parts = path.parts
    for i, p in enumerate(parts):
        if p in ("site-packages", "dist-packages") and i + 1 < len(parts):
            return "/".join(parts[i + 1:])
    return None


def frame(filename: str, function: str, line: int | None) -> dict[str, Any]:
    """One line of a stack as a report says it."""
    path = Path(filename)
    try:
        resolved = path.resolve()
    except (OSError, RuntimeError):
        resolved = path
    if resolved.is_relative_to(PACKAGE):
        return {"file": "orkcraft/" + resolved.relative_to(PACKAGE).as_posix(), "function": function,
                "line": line, "in_app": True}
    lib = _site(resolved)
    if lib is not None:
        return {"file": lib, "function": function, "line": line, "in_app": False}
    if resolved.is_relative_to(_STDLIB):
        return {"file": "<stdlib>/" + resolved.relative_to(_STDLIB).as_posix(), "function": function,
                "line": line, "in_app": False}
    if filename.startswith("<frozen "):
        return {"file": filename, "function": function, "line": line, "in_app": False}
    return {"file": "<other>", "function": "?", "line": None, "in_app": False}


def _exceptions(exc: BaseException) -> list[dict[str, Any]]:
    """The exception and up to two it came from, innermost last (as Sentry reads them)."""
    chain: list[BaseException] = []
    seen: set[int] = set()
    e: BaseException | None = exc
    while e is not None and id(e) not in seen and len(chain) < 3:
        seen.add(id(e))
        chain.append(e)
        e = e.__cause__ or (None if e.__suppress_context__ else e.__context__)
    out = []
    for e in reversed(chain):
        frames = [frame(f.filename, f.name, f.lineno) for f in traceback.extract_tb(e.__traceback__)]
        out.append({"type": type(e).__qualname__[:100], "value": scrub(str(e)), "frames": frames[-MAX_FRAMES:]})
    return out


_JS_FRAME = re.compile(r"(?:at (?P<fn>[^\s(]+) \()?(?:[a-z]+://[^/\s]+)?/(?P<file>static/[\w./-]+\.js):(?P<line>\d+)")
_JS_FRAME_FF = re.compile(r"^(?P<fn>[^@\s]*)@(?:[a-z]+://[^/\s]+)?/(?P<file>static/[\w./-]+\.js):(?P<line>\d+)")


def js_frames(stack: str) -> list[dict[str, Any]]:
    """The window's stack (Chromium's or WebKit's form), only its frames in Orkcraft's own scripts."""
    frames = []
    for raw in str(stack or "").splitlines()[:MAX_FRAMES]:
        line = raw.strip()
        m = _JS_FRAME_FF.match(line) or _JS_FRAME.search(line)
        if m:
            fn = re.sub(r"[^\w.$<>]", "", m.group("fn") or "") or "?"
            frames.append({"file": m.group("file"), "function": fn[:80], "line": int(m.group("line")),
                           "in_app": not m.group("file").startswith("static/js/vendor/")})
    return list(reversed(frames))              # outermost first, as Sentry reads them


# -- the reporter --------------------------------------------------------------------------------

class Reporter:
    def __init__(self, machine: settings.MachineSettings, face: str = "gui", demo: bool = False,
                 send: Callable[[str, bytes], None] | None = None, environment: str = "") -> None:
        self.machine = machine
        self.face = face
        self.demo = demo
        self.environment = environment or _environment()
        self._send = send or _post
        self._lock = threading.Lock()
        self._seen: set[tuple] = set()
        self.count = 0
        self.errors = 0
        self.crashed = False
        self.started = time.time()
        self.sid = uuid.uuid4().hex
        self._hooks: tuple | None = None

    def enabled(self) -> bool:
        return (self.machine.usage is True and bool(self.machine.install_id) and not self.demo
                and not usage.blocked() and bool(endpoint() or usage.debug()))

    # -- what happened -------------------------------------------------------------------------

    def capture(self, exc: BaseException, where: str = "command", handled: bool = True,
                fatal: bool = False, command: str = "") -> None:
        """Report an exception (and keep its traceback on this machine), once per kind and place."""
        if where not in WHERE:
            where = "command"
        self._keep_local(exc, where)
        exceptions = _exceptions(exc)
        self._event(exceptions, "python", where, handled, fatal, command)

    def capture_window(self, message: str, stack: str = "") -> None:
        """An error of the page, as `window.onerror` / `unhandledrejection` saw it (js/crashes.js)."""
        m = re.match(r"(?:Uncaught )?([A-Z][\w.]{0,60}): ?(.*)", str(message or ""), re.S)
        kind, value = (m.group(1), m.group(2)) if m else ("Error", str(message or ""))
        self._event([{"type": kind, "value": scrub(value), "frames": js_frames(stack)}], "javascript", "window",
                    False, False, "")

    def _event(self, exceptions: list[dict], platform_: str, where: str, handled: bool, fatal: bool,
               command: str) -> None:
        last = exceptions[-1]
        top = next((f for f in reversed(last["frames"]) if f["in_app"]), last["frames"][-1] if last["frames"] else {})
        key = (last["type"], top.get("file"), top.get("line"), where)
        with self._lock:
            self.errors += 1
            self.crashed = self.crashed or fatal
            if key in self._seen or self.count >= MAX_EVENTS:
                return
            self._seen.add(key)
            self.count += 1
        if not self.enabled():
            return
        event = {"type": "event", "event_id": uuid.uuid4().hex, "time": int(time.time() * 1000),
                 "platform": platform_, "where": where, "handled": handled, "level": "fatal" if fatal else "error",
                 "face": self.face, "environment": self.environment, "exceptions": exceptions}
        if command and re.fullmatch(r"[a-z][a-z0-9_.]{0,60}", command):
            event["command"] = command
        self._deliver([event], wait=TIMEOUT_S if fatal else None)

    # -- the run as a Sentry session -------------------------------------------------------------

    def session(self, status: str, init: bool = False, sid: str = "", started: float = 0.0,
                errors: int | None = None, wait: float | None = None) -> None:
        if not self.enabled():
            return
        start = started or self.started
        item = {"type": "session", "sid": sid or self.sid, "init": init, "status": status,
                "started": int(start * 1000), "time": int(time.time() * 1000),
                "duration": max(0, int(time.time() - start)), "errors": self.errors if errors is None else errors,
                "environment": self.environment}
        self._deliver([item], wait=wait)

    def start(self) -> None:
        """A session begins; one of an earlier run that never closed (killed, power off) ends as abnormal.
        Each run keeps a marker of its own while it lives, so two windows open at once never look dead."""
        if not self.enabled():
            return
        folder = log_dir()
        for marker in folder.glob("session-*.json"):
            try:
                last = json.loads(marker.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                last = None
            if isinstance(last, dict) and _alive(last.get("pid")):
                continue
            if isinstance(last, dict) and re.fullmatch(r"[0-9a-f]{32}", str(last.get("sid", ""))):
                self.session("abnormal", sid=last["sid"], started=float(last.get("started") or 0), errors=0)
            marker.unlink(missing_ok=True)
        try:
            folder.mkdir(parents=True, exist_ok=True)
            self._marker().write_text(json.dumps({"sid": self.sid, "started": self.started, "pid": os.getpid()}),
                                      encoding="utf-8")
        except OSError:
            pass
        self.session("ok", init=True)

    def _marker(self) -> Path:
        return log_dir() / f"session-{self.sid}.json"

    def close(self) -> None:
        self.session("crashed" if self.crashed else "exited", wait=2.0)
        self._marker().unlink(missing_ok=True)
        self.uninstall()

    # -- delivery ------------------------------------------------------------------------------

    def payload(self, items: list[dict]) -> dict[str, Any]:
        return {"install_id": self.machine.install_id, "app_version": __version__,
                "os": platform.system().lower() or "unknown",
                "python": ".".join(platform.python_version_tuple()[:2]), "items": items}

    def _deliver(self, items: list[dict], wait: float | None = None) -> None:
        body = self.payload(items)
        if usage.debug():
            sys.stderr.write("orkcraft crash: " + json.dumps(body, ensure_ascii=False) + "\n")
            return
        data = json.dumps(body).encode("utf-8")
        thread = threading.Thread(target=self._try, args=(data,), daemon=True, name="crash-report")
        thread.start()
        if wait:
            thread.join(wait)

    def _try(self, data: bytes) -> None:
        try:
            self._send(endpoint(), data)
        except Exception:                # a report never troubles the town: it is dropped
            pass

    def _keep_local(self, exc: BaseException, where: str) -> None:
        folder = log_dir()
        try:
            folder.mkdir(parents=True, exist_ok=True)
            stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S-%f")
            text = (f"orkcraft {__version__} · {platform.system()} · Python {platform.python_version()} · {where}\n\n"
                    + "".join(traceback.format_exception(exc)))
            (folder / f"crash-{stamp}.txt").write_text(text, encoding="utf-8")
            for old in sorted(folder.glob("crash-*.txt"))[:-KEEP_LOGS]:
                old.unlink()
        except OSError:
            pass

    # -- the hooks -----------------------------------------------------------------------------

    def install(self) -> None:
        if self._hooks is not None:
            return
        self._hooks = (sys.excepthook, threading.excepthook)
        before_sys, before_thread = self._hooks

        def on_sys(kind: type[BaseException], exc: BaseException, tb: TracebackType | None) -> None:
            if not issubclass(kind, KeyboardInterrupt):
                self.capture(exc, "unhandled", handled=False, fatal=True)
            before_sys(kind, exc, tb)

        def on_thread(args: threading.ExceptHookArgs) -> None:
            if args.exc_value is not None and not issubclass(args.exc_type, SystemExit):
                self.capture(args.exc_value, "thread", handled=False)
            before_thread(args)

        sys.excepthook = on_sys
        threading.excepthook = on_thread

    def uninstall(self) -> None:
        global _current
        if self._hooks is not None:
            sys.excepthook, threading.excepthook = self._hooks
            self._hooks = None
        if _current is self:
            _current = None

    def asyncio_handler(self, loop: Any, context: dict) -> None:
        """For `loop.set_exception_handler`: a task's error that nobody awaited."""
        exc = context.get("exception")
        if isinstance(exc, BaseException):
            self.capture(exc, "asyncio", handled=False)
        loop.default_exception_handler(context)


def _alive(pid: Any) -> bool:
    if not isinstance(pid, int) or pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except OSError:                      # there, but not ours to signal
        return True
    return True


def _environment() -> str:
    """`checkout` for a git checkout (the people who work on Orkcraft), else `production`."""
    try:
        from orkcraft.core import updates
        return "checkout" if updates._checkout(PACKAGE) is not None else "production"
    except Exception:
        return "production"


def _post(url: str, data: bytes) -> None:
    request = urllib.request.Request(url, data=data, method="POST", headers={
        "Content-Type": "application/json", "User-Agent": f"orkcraft/{__version__}"})
    with urllib.request.urlopen(request, timeout=TIMEOUT_S):
        pass


_current: Reporter | None = None


def install(machine: settings.MachineSettings, face: str = "gui", demo: bool = False) -> Reporter:
    """The reporter of this run: its hooks in place and its session begun."""
    global _current
    if _current is not None:
        _current.uninstall()
    _current = Reporter(machine, face=face, demo=demo)
    _current.install()
    _current.start()
    return _current


def capture(exc: BaseException, where: str = "command", **kw: Any) -> None:
    """Report through this run's reporter; nothing when there is none (a test, a headless command)."""
    if _current is not None:
        try:
            _current.capture(exc, where, **kw)
        except Exception:
            pass
