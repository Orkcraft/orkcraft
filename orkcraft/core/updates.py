"""Updates (docs/updates.md): Orkcraft looks for a newer version of itself and installs it.

The list of releases is `updates.json` at the root of the repository, read from its `main` branch.
A release marked `critical` (a security fix, a bug that loses work) installs by itself when the
town opens, before anything else loads, unless the operator said otherwise; any other release is
offered and installs with one click (or `orkcraft update`).

    s = updates.load_state()                  # what was read last, from the cache: no network
    offer = updates.offer(s.manifest, __version__)
    offer.version, offer.critical, offer.notes
    way = updates.method()                    # how this copy was installed: git, pipx, uv, pip
    result = updates.install(way)             # its own tool upgrades it; result.ok, result.output
    updates.check(force=True)                 # read the list again now (a few seconds at most)

How often: the list is read at most every `CHECK_EVERY_S` (a launch reads it when the cache is
older; the window reads it again on its clock). The policy is the machine's (`settings.updates`):

    auto       every update installs when the town opens
    critical   critical ones install when the town opens; the others are offered (the default)
    ask        nothing installs by itself; every update is offered, a critical one loudly

Nothing is read and nothing installs while `ORKCRAFT_NO_UPDATE` is set or under CI.
`ORKCRAFT_UPDATE_URL` reads the list from elsewhere (a fork, a test: `file://` works too).
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from orkcraft import __version__
from orkcraft.env import getenv

MANIFEST_URL = "https://raw.githubusercontent.com/Orkcraft/orkcraft/main/updates.json"
SOURCE = "git+https://github.com/Orkcraft/orkcraft"
CHECK_EVERY_S = 6 * 3600          # the list is read again after this long
RETRY_FAILED_S = 24 * 3600        # an install that failed is tried again by itself after this long
FETCH_TIMEOUT_S = 3.0             # a launch never waits longer than this for the list
INSTALL_TIMEOUT_S = 600.0
MAX_BYTES = 256 * 1024
POLICIES = ("auto", "critical", "ask")
BRANCHES = ("main", "master")    # a git checkout pulls by itself only on these
RESTART = 75                      # the exit code the window returns when it closed to restart
UPDATED_ENV = "ORKCRAFT_UPDATED"  # set on the process a launch restarted into: it never installs again


# -- versions -----------------------------------------------------------------------------------

def version_key(text: str) -> tuple[int, ...]:
    """"0.1.10" → (0, 1, 10); what is not a number is left out, so "1.2.0rc1" sorts as 1.2.0."""
    parts = []
    for part in str(text).strip().lstrip("vV").split("."):
        m = re.match(r"\d+", part)
        if not m:
            break
        parts.append(int(m.group()))
    while len(parts) > 1 and parts[-1] == 0:
        parts.pop()
    return tuple(parts)


def newer(a: str, b: str) -> bool:
    """`a` is a later version than `b`."""
    return version_key(a) > version_key(b)


# -- the list of releases -----------------------------------------------------------------------

@dataclass(frozen=True)
class Release:
    version: str
    critical: bool = False
    notes: str = ""
    date: str = ""


@dataclass(frozen=True)
class Offer:
    """What is newer than the running version: the latest, whether any release on the way is critical,
    and what each of them changes, newest first."""
    version: str
    critical: bool
    releases: tuple[Release, ...]

    @property
    def notes(self) -> list[str]:
        return [f"{r.version}: {r.notes}" for r in self.releases if r.notes]

    @property
    def critical_notes(self) -> list[str]:
        return [f"{r.version}: {r.notes}" for r in self.releases if r.critical and r.notes]

    def to_dict(self) -> dict[str, Any]:
        return {"version": self.version, "critical": self.critical, "notes": self.notes,
                "critical_notes": self.critical_notes}


def releases(manifest: Any) -> list[Release]:
    """The releases a manifest lists, newest first; anything malformed is left out."""
    if not isinstance(manifest, dict) or not isinstance(manifest.get("releases"), list):
        return []
    out = []
    for raw in manifest["releases"][:500]:
        if not isinstance(raw, dict) or not isinstance(raw.get("version"), str) or not version_key(raw["version"]):
            continue
        out.append(Release(version=raw["version"].strip()[:40], critical=raw.get("critical") is True,
                           notes=str(raw.get("notes") or "")[:500], date=str(raw.get("date") or "")[:20]))
    return sorted(out, key=lambda r: version_key(r.version), reverse=True)


def offer(manifest: Any, current: str = __version__) -> Offer | None:
    """What a manifest offers over `current`, or None when nothing newer is listed."""
    ahead = tuple(r for r in releases(manifest) if newer(r.version, current))
    if not ahead:
        return None
    return Offer(version=ahead[0].version, critical=any(r.critical for r in ahead), releases=ahead)


def due(found: Offer | None, policy: str) -> bool:
    """Whether `found` installs by itself under `policy` when the town opens."""
    if found is None:
        return False
    return policy == "auto" or (policy == "critical" and found.critical)


# -- when it is read, and where that is kept ----------------------------------------------------

def blocked() -> str:
    """Why nothing is read or installed here whatever the policy, or ""."""
    if getenv("NO_UPDATE") not in ("", "0"):
        return "ORKCRAFT_NO_UPDATE is set"
    if os.environ.get("CI", "").strip().lower() not in ("", "0", "false", "no"):
        return "running under CI"
    return ""


def url() -> str:
    return getenv("UPDATE_URL") or MANIFEST_URL


def state_path() -> Path:
    base = os.environ.get("XDG_CACHE_HOME", "").strip() or str(Path.home() / ".cache")
    return Path(base) / "orkcraft" / "updates.json"


@dataclass
class State:
    checked: float = 0.0               # when the list was last read (or tried)
    manifest: dict = field(default_factory=dict)
    failed_version: str = ""           # the last install that failed, its version
    failed_at: float = 0.0
    failed_error: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {"checked": self.checked, "manifest": self.manifest,
                "failed": {"version": self.failed_version, "at": self.failed_at, "error": self.failed_error}}

    def failed_recently(self, version: str, now: float) -> bool:
        return self.failed_version == version and now - self.failed_at < RETRY_FAILED_S


def load_state(file: Path | None = None) -> State:
    try:
        data = json.loads((file or state_path()).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return State()
    if not isinstance(data, dict):
        return State()
    failed = data.get("failed") if isinstance(data.get("failed"), dict) else {}
    num = lambda v: float(v) if isinstance(v, (int, float)) else 0.0   # noqa: E731
    return State(checked=num(data.get("checked")),
                 manifest=data["manifest"] if isinstance(data.get("manifest"), dict) else {},
                 failed_version=str(failed.get("version") or "")[:40], failed_at=num(failed.get("at")),
                 failed_error=str(failed.get("error") or "")[:2000])


def save_state(s: State, file: Path | None = None) -> None:
    file = file or state_path()
    try:
        file.parent.mkdir(parents=True, exist_ok=True)
        tmp = file.with_suffix(".tmp")
        tmp.write_text(json.dumps(s.to_dict(), indent=2) + "\n", encoding="utf-8")
        tmp.replace(file)
    except OSError:                    # a cache that cannot be written only means the list is read again
        pass


def fetch(where: str | None = None, timeout: float = FETCH_TIMEOUT_S) -> dict:
    """The manifest at `where` (the default list); raises OSError or ValueError when it cannot be read."""
    request = urllib.request.Request(where or url(), headers={"User-Agent": f"orkcraft/{__version__}",
                                                              "Cache-Control": "no-cache"})
    with urllib.request.urlopen(request, timeout=timeout) as answer:
        data = json.loads(answer.read(MAX_BYTES + 1)[:MAX_BYTES].decode("utf-8"))
    if not isinstance(data, dict):
        raise ValueError("the list of updates is not a JSON object")
    return data


def check(force: bool = False, now: float | None = None, file: Path | None = None,
          timeout: float = FETCH_TIMEOUT_S, read: Callable[[], dict] | None = None) -> State:
    """The state with the list read again when it is older than `CHECK_EVERY_S` (or `force`d). A list
    that cannot be read leaves the last one in place and is tried again after the same while."""
    now = time.time() if now is None else now
    s = load_state(file)
    fresh = 0 < s.checked <= now and now - s.checked < CHECK_EVERY_S   # a clock set back reads it again
    if blocked() or (fresh and not force):
        return s
    s.checked = now
    try:
        s.manifest = (read or (lambda: fetch(timeout=timeout)))()
    except Exception:                  # offline, a proxy, a broken file: the town opens all the same
        if force:
            save_state(s, file)
            raise
    save_state(s, file)
    return s


# -- how this copy was installed, and how it upgrades ------------------------------------------

@dataclass(frozen=True)
class Method:
    kind: str                          # git · pipx · uv · pip · none
    steps: tuple[tuple[str, ...], ...] = ()
    cwd: str = ""
    why: str = ""                      # for `none`: why it cannot update itself, and what to run instead

    @property
    def can(self) -> bool:
        return bool(self.steps)

    def describe(self) -> str:
        return " && ".join(" ".join(step) for step in self.steps) if self.steps else self.why


MANUAL = f'pipx install --force "orkcraft[gui] @ {SOURCE}"'


def _checkout(package: Path) -> Path | None:
    """The git checkout this package runs from (bin/orkcraft, `pip install -e`), or None."""
    root = package.parent
    if (root / ".git").exists() and (root / "pyproject.toml").is_file():
        try:
            if 'name = "orkcraft"' in (root / "pyproject.toml").read_text(encoding="utf-8"):
                return root
        except OSError:
            return None
    return None


def _direct_url() -> str:
    """The URL pip installed this copy from (PEP 610), "" when it came from elsewhere."""
    try:
        from importlib import metadata
        raw = metadata.distribution("orkcraft").read_text("direct_url.json") or ""
        data = json.loads(raw) if raw else {}
    except Exception:
        return ""
    if isinstance(data, dict) and isinstance(data.get("vcs_info"), dict) and isinstance(data.get("url"), str):
        return data["url"]
    return ""


def method(package: Path | None = None, prefix: str | None = None,
           which: Callable[[str], str | None] = shutil.which) -> Method:
    """How this copy upgrades: the tool that installed it does it, so its own records stay right."""
    package = package or Path(__file__).resolve().parents[1]
    prefix = prefix if prefix is not None else sys.prefix
    root = _checkout(package)
    if root is not None:
        steps: list[tuple[str, ...]] = [("git", "-C", str(root), "pull", "--ff-only")]
        if which("uv"):
            steps.append(("uv", "pip", "install", "--quiet", "--python", sys.executable, "-e", str(root)))
        return Method("git", tuple(steps), cwd=str(root))
    parts = Path(prefix).parts
    if "pipx" in parts and "venvs" in parts:
        return (Method("pipx", (("pipx", "upgrade", "orkcraft"),)) if which("pipx")
                else Method("none", why=f"pipx is not on PATH; run: {MANUAL}"))
    if "uv" in parts and "tools" in parts:
        return (Method("uv", (("uv", "tool", "upgrade", "orkcraft"),)) if which("uv")
                else Method("none", why=f"uv is not on PATH; run: uv tool upgrade orkcraft"))
    source = _direct_url()
    if source.startswith("git+") or source.startswith("https://github.com/"):
        spec = source if source.startswith("git+") else f"git+{source}"
        return Method("pip", ((sys.executable, "-m", "pip", "install", "--upgrade", f"orkcraft @ {spec}"),))
    return Method("none", why=f"this copy was not installed from git; run: {MANUAL}")


@dataclass(frozen=True)
class Result:
    ok: bool
    output: str = ""
    version: str = ""                  # the version installed now, when it could be read


def _dirty(root: str, run: Callable) -> str:
    """Why a git checkout cannot be pulled by itself ("" when it can): changes, or no branch."""
    status = run(["git", "-C", root, "status", "--porcelain", "--untracked-files=no"],
                 capture_output=True, text=True, timeout=60)
    if status.returncode != 0:
        return (status.stderr or status.stdout or "git status failed").strip()
    if status.stdout.strip():
        return "the checkout has changes of its own: commit or stash them, then `git pull`"
    head = run(["git", "-C", root, "symbolic-ref", "-q", "--short", "HEAD"], capture_output=True, text=True,
               timeout=60)
    branch = head.stdout.strip() if head.returncode == 0 else ""
    if branch not in BRANCHES:
        return (f"the checkout is on {branch}, and updates come to main" if branch
                else "the checkout is not on a branch, and updates come to main")
    return ""


def installed_version(run: Callable = subprocess.run) -> str:
    """The version a fresh interpreter imports now (this process keeps the one it started with)."""
    try:
        done = run([sys.executable, "-c", "import orkcraft; print(orkcraft.__version__)"],
                   capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.SubprocessError):
        return ""
    return done.stdout.strip() if done.returncode == 0 else ""


def install(way: Method | None = None, run: Callable = subprocess.run) -> Result:
    """Each step of `way` in turn; the first that fails stops it. Never raises."""
    way = way or method()
    if not way.can:
        return Result(False, way.why)
    out: list[str] = []
    try:
        if way.kind == "git":
            why = _dirty(way.cwd, run)
            if why:
                return Result(False, why)
        for step in way.steps:
            done = run(list(step), capture_output=True, text=True, timeout=INSTALL_TIMEOUT_S)
            out.append(f"$ {' '.join(step)}\n{(done.stdout or '').strip()}\n{(done.stderr or '').strip()}".strip())
            if done.returncode != 0:
                return Result(False, "\n".join(out)[-4000:])
    except (OSError, subprocess.SubprocessError) as e:
        out.append(f"{type(e).__name__}: {e}")
        return Result(False, "\n".join(out)[-4000:])
    now_version = installed_version(run)
    if now_version and not newer(now_version, __version__):
        out.append(f"the install finished, and the version is still {now_version}")
        return Result(False, "\n".join(out)[-4000:], now_version)
    return Result(True, "\n".join(out)[-4000:], now_version)


def remember(result: Result, version: str, file: Path | None = None, now: float | None = None) -> None:
    """A failed install is kept, so a launch does not try it again before `RETRY_FAILED_S`."""
    s = load_state(file)
    if result.ok:
        s.failed_version, s.failed_at, s.failed_error = "", 0.0, ""
    else:
        s.failed_version, s.failed_at, s.failed_error = version, time.time() if now is None else now, result.output
    save_state(s, file)


# -- when the town opens ------------------------------------------------------------------------

def restart(argv: list[str], version: str = "", execv: Callable = os.execv) -> None:
    """This process becomes a fresh one with the same arguments, on the code installed now."""
    os.environ[UPDATED_ENV] = version or "1"
    sys.stdout.flush()
    sys.stderr.flush()
    execv(sys.executable, [sys.executable, "-m", "orkcraft.cli", *argv])


def at_launch(argv: list[str], policy: str, say: Callable[[str], None] | None = None,
              now: float | None = None, file: Path | None = None, read: Callable[[], dict] | None = None,
              run: Callable = subprocess.run, execv: Callable = os.execv) -> Offer | None:
    """Before the town loads: the list read again when it is old, and an update the policy says is due
    installed, then the process restarts on it. Returns what is newer and was not installed (for the
    window to offer). Nothing here stops the town from opening: a failure is said and the town opens."""
    say = say or (lambda text: sys.stderr.write(f"orkcraft: {text}\n"))
    if blocked() or os.environ.get(UPDATED_ENV):
        return None
    now = time.time() if now is None else now
    s = check(now=now, file=file, read=read)
    found = offer(s.manifest)
    if found is None or not due(found, policy) or s.failed_recently(found.version, now):
        return found
    way = method()
    if not way.can:
        if found.critical:
            say(f"a critical update {found.version} is out and cannot install itself here: {way.why}")
        return found
    kind = "critical update" if found.critical else "update"
    say(f"installing the {kind} {found.version} ({way.kind})…")
    for line in (found.critical_notes or found.notes)[:5]:
        say(f"  {line}")
    result = install(way, run)
    remember(result, found.version, file, now)
    if not result.ok:
        say(f"the {kind} {found.version} did not install; the town opens on {__version__}:\n{result.output}")
        return found
    say(f"installed {result.version or found.version}; restarting")
    restart(argv, result.version or found.version, execv)
    return None


def check_later(on_done: Callable[[State], None] | None = None) -> threading.Thread:
    """The list read again on a thread of its own (the window's clock); `on_done` with the state."""
    def work() -> None:
        try:
            s = check()
        except Exception:
            return
        if on_done is not None:
            on_done(s)
    thread = threading.Thread(target=work, daemon=True, name="updates")
    thread.start()
    return thread
