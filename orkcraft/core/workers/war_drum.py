"""🥁 War Drum's work: the day and the week from an `.ics` file or URL (realm/daybook.py).

`refresh()` loads the calendar: events added or removed go out (`calendar.event_added` /
`calendar.event_removed`). `tick()` (every `TICK_S`) looks at the clock: an event that starts sends
`calendar.event_due`, a meeting `lead` (2h) away sends `calendar.event_upcoming` once (tagged
`[meet:<id>]`; `upcoming.json` remembers which went), the day's digest goes out once at `day_starts`
as `calendar.day_schedule`, and every `RELOAD_S` the calendar is loaded again.

A cart that comes back with the tag is the meeting's document (`docs.json`): a file it names, else
its Markdown kept in `docs/<id>.md`. `open_doc` sends it as `calendar.doc_opened` when a road carries
that; otherwise the face shows it in Lake. `prepare` sends `meeting soon` for a meeting at once, and
`add` puts an event in the calendar it may write (its own when the calendar is a URL).
"""
from __future__ import annotations

import datetime as dt
import json
import re
import time
from pathlib import Path

from orkcraft.core.workers import Worker
from orkcraft.realm import daybook, shelves

TICK_S = 30.0
RELOAD_S = 300.0
DOC = "📄"
_PATH = re.compile(r"`([^`\n]+\.[A-Za-z0-9]{1,8})`")


class WarDrumWorker(Worker):
    TYPE = "war_drum"
    clock = staticmethod(dt.datetime.now)          # tests move time here

    def __init__(self, town, building_id: str) -> None:
        super().__init__(town, building_id)
        self.day: daybook.Day = daybook.Day([], [])
        self._last_events: list | None = None
        self._since: dt.datetime | None = None
        self._loaded = 0.0                          # monotonic: when the calendar was last loaded

    @property
    def own_ics(self) -> Path:
        return self.state_dir / "local.ics"

    @property
    def lead(self) -> dt.timedelta:
        return daybook.parse_lead(str(self.config.get("lead", "")))

    @property
    def configured(self) -> str:
        return str(self.config.get("ics", ""))

    @property
    def writable(self) -> Path:
        """Where a new event goes: the calendar file, or its own when the calendar is a URL."""
        return daybook.writable(self.repo_root, self.configured, self.own_ics)

    # -- its life -------------------------------------------------------------------------------

    def start(self) -> None:
        self.refresh()

    def refresh(self) -> None:
        """Load the calendar again; what was added or removed goes out."""
        now = self.clock()
        self._loaded = time.monotonic()
        srcs = daybook.sources(self.repo_root, self.configured, self.own_ics)
        self.day = daybook.load(srcs, now.date())
        for event_id, e in daybook.changes(self._last_events, self.day.events):
            self.emit(event_id, daybook.line(e) + f" ({e.day:%a %d})", e.summary)
        self._last_events = list(self.day.events)
        if self._since is None:
            self._since = now
        self.changed()

    def tick(self) -> None:
        """The clock moved: what starts, what comes soon, the morning digest; a new day loads its events."""
        now = self.clock()
        if (self._since is not None and now.date() != self._since.date()) or \
                time.monotonic() - self._loaded >= RELOAD_S:
            self.refresh()
        since, self._since = self._since or now, now
        for e in daybook.due(self.day.events, since, now):
            self.emit("calendar.event_due", daybook.line(e), e.summary)
        self._maybe_upcoming(since, now)
        self._maybe_digest(now)
        self.changed()

    def status(self) -> str:
        return "ERROR" if self.day.errors else ""

    # -- what it shows --------------------------------------------------------------------------

    def today(self) -> list:
        now = self.clock()
        return [e for e in self.day.events if e.day == now.date()]

    def now_and_next(self) -> tuple:
        return daybook.now_and_next(self.day.events, self.clock())

    def event(self, meet_id: str):
        """The event of a meeting id, or None."""
        return next((e for e in self.day.events if daybook.meet_id(e) == meet_id), None)

    def selected(self):
        """The meeting a quick action is about when none is picked: the one on now, else the next."""
        cur, nxt, _ = self.now_and_next()
        return nxt or cur

    # -- documents for meetings -----------------------------------------------------------------

    def _load(self, name: str) -> dict:
        try:
            data = json.loads((self.state_dir / name).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}
        return data if isinstance(data, dict) else {}

    def _save(self, name: str, data: dict) -> None:
        self.state_dir.mkdir(parents=True, exist_ok=True)
        (self.state_dir / name).write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")

    def _maybe_upcoming(self, since: dt.datetime, now: dt.datetime) -> None:
        soon = daybook.upcoming(self.day.events, since, now, self.lead)
        if not soon:
            return
        sent = self._load("upcoming.json")
        for e in soon:
            mid = daybook.meet_id(e)
            if mid not in sent:
                self.send_upcoming(e)
                sent[mid] = now.isoformat(timespec="seconds")
        self._save("upcoming.json", sent)

    def _maybe_digest(self, now: dt.datetime) -> None:
        if now.time() < daybook.parse_day_starts(str(self.config.get("day_starts", ""))):
            return
        if self._load("digest.json").get("day", "") == now.date().isoformat():
            return
        if self.emit("calendar.day_schedule", daybook.digest(self.day.events, now.date()), f"{now:%A %d %B}"):
            self._save("digest.json", {"day": now.date().isoformat()})

    def send_upcoming(self, e) -> bool:
        tag = f"[meet:{daybook.meet_id(e)}]"
        return self.emit("calendar.event_upcoming", f"{daybook.line(e)} ({e.day:%a %d}) {tag}", f"{e.summary} {tag}")

    def prepare(self, e=None) -> str:
        """📄 Prepare doc: `meeting soon` for `e` (else the meeting on now or next) at once. What went
        wrong, or ""."""
        e = e if e is not None else self.selected()
        if e is None or not isinstance(e.start, dt.datetime):
            return "pick a meeting first"
        if not self.send_upcoming(e):
            return "no road carries `meeting soon` yet"
        return ""

    def docs(self) -> dict:
        return self._load("docs.json")

    def doc_of(self, e) -> dict | None:
        return self.docs().get(daybook.meet_id(e))

    def receive(self, payload, title: str, markdown: str) -> None:
        """A meeting's document came back: a cart tagged `[meet:<id>]`."""
        mid = daybook.meet_tag(payload.title) or daybook.meet_tag(title) or daybook.meet_tag(payload.value)
        if not mid:
            return
        repo = self.repo_root
        path = payload.value if payload.kind == "file" else self._named_file(repo, payload.value)
        if not path:
            doc = self.state_dir / "docs" / f"{mid}.md"
            doc.parent.mkdir(parents=True, exist_ok=True)
            doc.write_text(markdown or payload.value, encoding="utf-8")
            path = shelves.rel_to(repo, doc)
        docs = self.docs()
        docs[mid] = {"path": path, "title": title or payload.title, "at": self.clock().isoformat(timespec="seconds")}
        self._save("docs.json", docs)
        self.changed()

    @staticmethod
    def _named_file(repo: Path, text: str) -> str:
        """A file the text names in `backticks` that is there in the repository."""
        for m in _PATH.finditer(text or ""):
            p = Path(m.group(1).strip())
            if (p if p.is_absolute() else repo / p).is_file():
                return m.group(1).strip()
        return ""

    def open_doc(self, e) -> dict | None:
        """A meeting's document: sent as `calendar.doc_opened` when a road carries it. None when the
        meeting has none; else {path, title, sent} — not sent, the face shows it in Lake."""
        doc = self.doc_of(e)
        if not doc:
            return None
        path, title = doc["path"], f"{DOC} {e.summary}"
        return {"path": path, "title": title, "sent": self.emit("calendar.doc_opened", path, title)}

    # -- adding ---------------------------------------------------------------------------------

    def add(self, title: str, when: str, minutes: int = 30) -> dt.datetime:
        """A new event; ValueError / OSError when it cannot be (a bad time, a file it cannot write)."""
        title = " ".join(str(title).split())
        if not title:
            raise ValueError("an event needs a title")
        start = daybook.parse_when(when, self.clock().date())
        daybook.add_event(self.writable, title, start, int(minutes or 30))
        self.refresh()
        return start

    # -- the hut --------------------------------------------------------------------------------

    def mark(self, e, docs: dict | None = None) -> str:
        docs = self.docs() if docs is None else docs
        return f"{DOC} " if daybook.meet_id(e) in docs else ""

    def mini_status(self) -> list[str]:
        now = self.clock()
        cur, nxt, left = daybook.now_and_next(self.day.events, now)
        docs = self.docs()
        lines = []
        if cur:
            lines.append(f"▶ {self.mark(cur, docs)}{cur.summary}")
        if nxt:
            lines.append(f"{daybook.when(nxt)[:5]} {self.mark(nxt, docs)}{nxt.summary}")
        lines.append(f"{left} left today" if left else "nothing more today")
        later = [e for e in self.day.events if e.day > now.date()][:2]
        lines += [f"{e.day:%a} {daybook.when(e)[:5]} {self.mark(e, docs)}{e.summary}" for e in later]
        return lines

    def hut_lines(self, widths: list[int]) -> list[str]:
        cur, nxt, left = self.now_and_next()
        docs = self.docs()
        lines = [f"[{daybook.when(e)[:5]}] {self.mark(e, docs)}{e.summary}" for e in self.today()[:4]] or ["nothing today"]
        lines += [""] * (5 - len(lines))
        lines.append(f"now: {cur.summary}" if cur else f"next: {daybook.when(nxt)[:5]} {nxt.summary}" if nxt
                     else "next: nothing more")
        lines.append(f"left today: {left}")
        return lines
