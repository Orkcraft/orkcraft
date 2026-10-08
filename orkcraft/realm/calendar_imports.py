"""Imported calendars of a Calendar (War Drum): a `.ics` file taken in, or a subscription to an ICS link.

Google, Apple and Outlook each give a calendar a secret address in iCal format: whoever has the link
reads the calendar. So a link is a secret. It goes to realm/logins.py (the OS keychain, else a 0600
file out of the project) under `calendar.<building>.<id>`, and the building's settings keep only its
reference and the host it is on — never the link, in the town scroll, a log or a toast:

    "imports": {"3fa9c1": {"kind": "file", "name": "Offsite"},
                "8b20de": {"kind": "link", "name": "Work", "secret": "keychain:calendar.drum.8b20de",
                           "host": "calendar.google.com", "every": 30}}

A spec whose link import holds anything but such a reference is refused (`problems`): a link pasted
into the settings by hand never lands in the scroll.

A file's calendar is copied into `<state>/imports/<id>.ics`; a link's last good copy is kept there too,
fetched again every `every` minutes (`EVERY_MIN`–`EVERY_MAX`, default `EVERY`). A failed fetch keeps the
last copy and says why in plain words (`status.json`: when each was fetched, how many events, the
error). The copies are read like any other calendar (sources/ics.py), so an occurrence moved, cancelled
or taken out of the calendar is moved, gone or `calendar.event_removed` on the next fetch.

`fetch` is the only door to the network (tests put a fake one here). No bus, no face.
"""
from __future__ import annotations

import datetime as dt
import json
import re
import secrets as _secrets
import socket
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from orkcraft.realm import logins
from orkcraft.sources import ics

EVERY, EVERY_MIN, EVERY_MAX = 30, 15, 24 * 60     # minutes between two fetches of a link
MAX_BYTES = 10 * 1024 * 1024                       # a calendar bigger than this is not one
TIMEOUT_S = 15
KINDS = ("file", "link")
_ID = re.compile(r"^[0-9a-f]{6,16}$")


class NotImported(ValueError):
    """What went wrong, in words the person can act on (never the link itself)."""


# -- the link --------------------------------------------------------------------------------------

def normal_link(url: str) -> str:
    """The link as it is fetched: `webcal://` (what Apple and Outlook hand out) becomes https."""
    url = "".join((url or "").split())
    if url.lower().startswith("webcal://"):
        url = "https://" + url[len("webcal://"):]
    parts = urllib.parse.urlsplit(url)
    if parts.scheme not in ("http", "https") or not parts.hostname:
        raise NotImported("That is not a calendar link: it starts with https:// or webcal://")
    return url


def is_link(text: str) -> bool:
    return (text or "").strip().lower().startswith(("http://", "https://", "webcal://"))


def host(url: str) -> str:
    """Where a link points, safe to show: its host alone."""
    try:
        return urllib.parse.urlsplit(normal_link(url)).hostname or ""
    except NotImported:
        return ""


def _fetch(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "orkcraft", "Accept": "text/calendar, */*"})
    with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp:
        data = resp.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise NotImported("The calendar is larger than 10 MB")
    return data.decode("utf-8", errors="replace")


fetch = _fetch                                       # url → the calendar's text; tests put a fake one here


def _why(exc: BaseException) -> str:
    """A failed fetch in plain words; never the link, whatever the error carried."""
    if isinstance(exc, NotImported):
        return str(exc)
    if isinstance(exc, urllib.error.HTTPError):
        if exc.code in (401, 403, 404, 410):
            return f"The calendar refused the link (HTTP {exc.code}): it may have been reset — copy the secret address again"
        return f"The calendar's server answered HTTP {exc.code}"
    if isinstance(exc, (socket.timeout, TimeoutError)):
        return "The calendar did not answer in time"
    if isinstance(exc, urllib.error.URLError):
        return "The calendar cannot be reached (offline, or the address is wrong)"
    return "The calendar could not be fetched"


# -- reading what came ------------------------------------------------------------------------------

def check(text: str) -> int:
    """How many events `text` holds (each recurring one once); NotImported when it is no calendar."""
    if "BEGIN:VCALENDAR" not in (text or "").upper():
        raise NotImported("This is not a calendar: an .ics file starts with BEGIN:VCALENDAR")
    return len(re.findall(r"^BEGIN:VEVENT\s*$", text, re.M | re.I))


# -- where they are kept ----------------------------------------------------------------------------

def folder(state_dir: Path) -> Path:
    return state_dir / "imports"


def copy_of(state_dir: Path, import_id: str) -> Path:
    return folder(state_dir) / f"{import_id}.ics"


def secret_name(building_id: str, import_id: str) -> str:
    bid = re.sub(r"[^a-z0-9._-]+", "-", building_id.lower()).strip("-.") or "calendar"
    return f"calendar.{bid[:80]}.{import_id}"


def _status_file(state_dir: Path) -> Path:
    return folder(state_dir) / "status.json"


def status(state_dir: Path) -> dict:
    try:
        data = json.loads(_status_file(state_dir).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _set_status(state_dir: Path, import_id: str, **got) -> None:
    data = status(state_dir)
    if got:
        data[import_id] = {**data.get(import_id, {}), **got}
    else:
        data.pop(import_id, None)
    _status_file(state_dir).parent.mkdir(parents=True, exist_ok=True)
    _status_file(state_dir).write_text(json.dumps(data, indent=1), encoding="utf-8")


def _write_copy(state_dir: Path, import_id: str, text: str) -> None:
    path = copy_of(state_dir, import_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)


MAX_IMPORTS = 20


def entries(config: dict) -> list[dict]:
    """The imports a building's settings list, in the order they came, each with its `id` (a broken one
    is left out)."""
    got = config.get("imports")
    out = []
    for key, item in (got.items() if isinstance(got, dict) else ()):
        if isinstance(item, dict) and item.get("kind") in KINDS and _ID.match(str(key)):
            out.append({**item, "id": str(key)})
    return out


def as_config(items: list[dict]) -> dict:
    """The imports as the settings keep them: by id."""
    return {e["id"]: {k: v for k, v in e.items() if k != "id"} for e in items}


def problems(value: dict) -> list[str]:
    """What is wrong with a spec's `imports` (catalog_checks.py)."""
    out = []
    if len(value) > MAX_IMPORTS:
        out.append(f"at most {MAX_IMPORTS} calendars")
    for key, item in value.items():
        if not isinstance(key, str) or not _ID.match(key) or not isinstance(item, dict):
            out.append(f"{key!r} is not an import")
        elif item.get("kind") not in KINDS:
            out.append(f"{key}: kind is file or link")
        elif not isinstance(item.get("name", ""), str) or len(item.get("name", "")) > 80:
            out.append(f"{key}: a name is up to 80 characters")
        elif item["kind"] == "link" and not logins.is_ref(str(item.get("secret") or "")):
            out.append(f"{key}: a link is kept in the keychain — its secret is keychain:<name>, never the link")
    return out


def new_id(taken: list[dict]) -> str:
    ids = {e.get("id") for e in taken}
    while True:
        got = _secrets.token_hex(3)
        if got not in ids:
            return got


def every(value) -> int:
    """Minutes between two fetches, held to `EVERY_MIN`–`EVERY_MAX`."""
    try:
        n = int(value)
    except (TypeError, ValueError):
        return EVERY
    return min(max(n, EVERY_MIN), EVERY_MAX)


# -- taking one in ----------------------------------------------------------------------------------

def take_file(state_dir: Path, taken: list[dict], name: str, text: str, now: dt.datetime) -> dict:
    """A `.ics` file's calendar, copied in: its entry for the settings."""
    count = check(text)
    entry = {"id": new_id(taken), "kind": "file", "name": _name(name, "Imported calendar")}
    _write_copy(state_dir, entry["id"], text)
    _set_status(state_dir, entry["id"], fetched=now.isoformat(timespec="seconds"), events=count, error="")
    return entry


def take_link(state_dir: Path, building_id: str, taken: list[dict], name: str, url: str, minutes,
              now: dt.datetime) -> dict:
    """A subscription: the link fetched once (a bad one never gets saved), kept as a secret, its copy
    written. Its entry for the settings holds the secret's reference, never the link."""
    url = normal_link(url)
    try:
        text = fetch(url)
    except Exception as exc:                            # every kind of failure: said, never the link
        raise NotImported(_why(exc)) from None
    count = check(text)
    import_id = new_id(taken)
    ref = logins.save(secret_name(building_id, import_id), url, service="calendar", account=host(url))
    entry = {"id": import_id, "kind": "link", "name": _name(name, host(url) or "Subscribed calendar"),
             "secret": ref, "host": host(url), "every": every(minutes if minutes not in (None, "") else EVERY)}
    _write_copy(state_dir, import_id, text)
    _set_status(state_dir, import_id, fetched=now.isoformat(timespec="seconds"), events=count, error="")
    return entry


def _name(name: str, default: str) -> str:
    name = " ".join(str(name or "").split())[:80]
    if name.lower().endswith(".ics"):
        name = name[:-4].strip()
    return name or default


# -- keeping them current ---------------------------------------------------------------------------

def due(state_dir: Path, items: list[dict], now: dt.datetime) -> list[dict]:
    """The links whose `every` minutes have passed since they were last tried."""
    got = status(state_dir)
    out = []
    for e in items:
        if e["kind"] != "link":
            continue
        tried = got.get(e["id"], {}).get("tried") or got.get(e["id"], {}).get("fetched") or ""
        try:
            last = dt.datetime.fromisoformat(tried)
        except ValueError:
            last = None
        if last is None or now - last >= dt.timedelta(minutes=every(e.get("every"))):
            out.append(e)
    return out


def refresh(state_dir: Path, entry: dict, now: dt.datetime) -> str:
    """Fetch a link again: its copy replaced on success. What went wrong (the last copy stays), or ""."""
    stamp = now.isoformat(timespec="seconds")
    url = logins.resolve(str(entry.get("secret") or ""))
    if not url:
        why = "The link is no longer kept on this machine: subscribe again"
        _set_status(state_dir, entry["id"], tried=stamp, error=why)
        return why
    try:
        text = fetch(url)
        count = check(text)
    except Exception as exc:
        why = _why(exc)
        _set_status(state_dir, entry["id"], tried=stamp, error=why)
        return why
    _write_copy(state_dir, entry["id"], text)
    _set_status(state_dir, entry["id"], tried=stamp, fetched=stamp, events=count, error="")
    return ""


def forget(state_dir: Path, entry: dict) -> None:
    """An import taken out: its copy, its status and (a link) its secret go."""
    copy_of(state_dir, entry["id"]).unlink(missing_ok=True)
    _set_status(state_dir, entry["id"])
    ref = str(entry.get("secret") or "")
    if logins.is_ref(ref):
        logins.remove(ref[len(logins.PREFIX):])


def sources(state_dir: Path, items: list[dict]) -> list[ics.CalendarSource]:
    """What the calendar reads of them: each one's copy, under its name."""
    return [ics.CalendarSource(e.get("name") or e["id"], path=str(copy_of(state_dir, e["id"])))
            for e in items if copy_of(state_dir, e["id"]).exists()]


def rows(state_dir: Path, items: list[dict]) -> list[dict]:
    """The imports as the window lists them: name, kind, host, how often, when fetched, events, error."""
    got = status(state_dir)
    return [{"id": e["id"], "kind": e["kind"], "name": e.get("name") or e["id"], "host": e.get("host", ""),
             "every": every(e.get("every")) if e["kind"] == "link" else 0,
             "fetched": got.get(e["id"], {}).get("fetched", ""), "events": got.get(e["id"], {}).get("events", 0),
             "error": got.get(e["id"], {}).get("error", "")} for e in items]
