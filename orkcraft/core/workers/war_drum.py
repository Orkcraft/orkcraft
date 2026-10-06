"""🥁 War Drum's work: the day and the week from an `.ics` file or URL (realm/daybook.py).

`refresh()` loads the calendar: events added or removed go out (`calendar.event_added` /
`calendar.event_removed`). `tick()` (every `TICK_S`) looks at the clock: an event that starts sends
`calendar.event_due`, a meeting `lead` (2h) away sends `calendar.event_upcoming` once (tagged
`[meet:<id>]`; `upcoming.json` remembers which went), the day's digest goes out once at `day_starts`
as `calendar.day_schedule`, and every `RELOAD_S` the calendar is loaded again.

`meeting soon` is titled by the meeting, carries its `[meet:<id>]` tag in its text and the ref
`<building>:<id>`. A cart that comes back with the tag, or under that ref (by a return road), is the
meeting's document (`docs.json`): a file it names, else its Markdown kept in `docs/<id>.md`, and the
first link it gives. `open_doc` sends it as `calendar.doc_opened` when a road carries that; otherwise
the face shows it in Lake. `prepare` sends `meeting soon` for a meeting at once, and `add` puts an
event in the calendar it may write (its own when the calendar is a URL).

Any other cart that names a time in a `When:` line (a Clan Fire's `team.routed` for a meeting) is an
event to add, titled as the cart is (realm/daybook.py `find_when`). With `prepare_new`, an event added
by a road or by New event is sent as `meeting soon` at once, so its document is asked for right away.

Over the meetings it lays the town's schedules and its limits (realm/drumbeat.py): `jobs()` are the
scheduled runs of every standing building, `limits()` the 🪙 spend and 🪵 context limits with ≈ when
each is reached at the burn rate it samples on every tick (`burn.jsonl`; the demo's is seeded, as
agents never run there), and `beats(until)` all three on one timeline — or only the kinds `beats` names (a calendar of meetings alone:
`["meeting"]`).
"""
from __future__ import annotations

import datetime as dt
import json
import re
import time
from pathlib import Path

from orkcraft.core.workers import Worker
from orkcraft.realm import daybook, drumbeat, shelves

TICK_S = 30.0
RELOAD_S = 300.0
HUT_BEATS = 7                                       # timeline rows on the TUI's hut
DOC = "📄"
_PATH = re.compile(r"`([^`\n]+\.[A-Za-z0-9]{1,8})`")
_HEAD = re.compile(r"\A\s*\*\*[^\n]*\*\* — [^\n]*\n+")       # a Barracks report's `**Task** — who did it`
_LINK = re.compile(r"https?://[^\s)>\]`*]+")


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
        self.sample_burn(now)
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

    # -- the timeline: meetings, the town's schedules, its limits -----------------------------

    @property
    def burn_file(self) -> Path:
        return self.state_dir / "burn.jsonl"

    def sample_burn(self, now: dt.datetime | None = None) -> bool:
        """Keep where this run's spend and the fullest session's context stand (none in the demo:
        its samples are seeded)."""
        if self.simulated:
            return False
        snap = self.town.snapshot
        who, ctx = max(snap.context_by_terminal.items(), key=lambda kv: kv[1], default=("", 0))
        try:
            return drumbeat.sample(self.burn_file, now or self.clock(), self.town.run_id, snap.spent_usd, ctx, who)
        except OSError:
            return False

    @property
    def kinds(self) -> tuple[str, ...]:
        """What its timeline lays over the meetings (`beats`: meeting, schedule, limit; default all three)."""
        got = self.config.get("beats")
        kinds = tuple(k for k in drumbeat.KINDS if not got or k in got)
        return kinds or drumbeat.KINDS

    def jobs(self) -> list[drumbeat.Job]:
        if "schedule" not in self.kinds:
            return []
        return drumbeat.jobs(self.town.scroll, self.town.custom_specs)

    def limits(self) -> list[drumbeat.Limit]:
        if "limit" not in self.kinds:
            return []
        rows = drumbeat.read_samples(self.burn_file, None if self.simulated else self.town.run_id)
        budget = self.town.scroll.budget
        return drumbeat.limits(rows, budget.gold_session_limit_usd, budget.lumber_context_limit_tokens, self.clock())

    def beats(self, until: dt.datetime | None = None, limits: list | None = None) -> list[drumbeat.Beat]:
        """Meetings, scheduled runs and ≈ limits from now to `until` (a day ahead), in time order."""
        now = self.clock()
        until = until or now + dt.timedelta(days=1)
        return drumbeat.timeline(self.day.events, self.jobs(), self.limits() if limits is None else limits, now, until)

    def week_beats(self, limits: list | None = None) -> dict:
        """Each day of the week → its scheduled runs (up to `drumbeat.PER_JOB` a job, the rest as
        `more`) and the limits reached that day; today's from now on."""
        now = self.clock()
        limits = self.limits() if limits is None else limits
        jobs = self.jobs()
        last = now.date() + dt.timedelta(days=daybook.WEEK_DAYS - 1)
        reached = drumbeat.timeline([], [], limits, now, dt.datetime.combine(last, dt.time(23, 59)))
        out = {}
        for d in range(daybook.WEEK_DAYS):
            day = now.date() + dt.timedelta(days=d)
            start = now if d == 0 else dt.datetime.combine(day, dt.time()) - dt.timedelta(minutes=1)
            runs = drumbeat.timeline([], jobs, [], start, dt.datetime.combine(day, dt.time(23, 59)))
            out[day] = sorted(runs + [b for b in reached if b.at.date() == day], key=lambda b: (b.at, b.kind))
        return out

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
        """`meeting soon` for `e`: titled by it, its tag in the text, its ref `<building>:<meeting id>`."""
        mid = daybook.meet_id(e)
        return self.emit("calendar.event_upcoming", f"{daybook.line(e)} ({e.day:%a %d}) [meet:{mid}]", e.summary,
                         ref=f"{self.building_id}:{mid}")

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
        """A meeting's document came back (a cart tagged `[meet:<id>]` or under the meeting's ref); else a
        cart that names a time is an event to add."""
        own = f"{self.building_id}:"
        mid = (payload.ref[len(own):] if payload.ref.startswith(own) else "") or daybook.meet_tag(payload.title) \
            or daybook.meet_tag(title) or daybook.meet_tag(payload.value)
        if not mid:
            self._event_from(payload, title, markdown)
            return
        repo = self.repo_root
        path = payload.value if payload.kind == "file" else self._named_file(repo, payload.value)
        if not path:
            doc = self.state_dir / "docs" / f"{mid}.md"
            doc.parent.mkdir(parents=True, exist_ok=True)
            doc.write_text(_HEAD.sub("", markdown or payload.value, count=1), encoding="utf-8")
            path = shelves.rel_to(repo, doc)
        docs = self.docs()
        link = next(iter(_LINK.findall(f"{payload.value}\n{markdown}")), "")
        docs[mid] = {"path": path, "title": title or payload.title, "at": self.clock().isoformat(timespec="seconds"),
                     "link": link.rstrip(".,;:")}
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

    @property
    def prepare_new(self) -> bool:
        return bool(self.config.get("prepare_new"))

    def add(self, title: str, when: str | dt.datetime, minutes: int = 30) -> dt.datetime:
        """A new event; ValueError / OSError when it cannot be (a bad time, a file it cannot write). With
        `prepare_new`, its document is asked for at once."""
        title = " ".join(str(title).split())
        if not title:
            raise ValueError("an event needs a title")
        start = when if isinstance(when, dt.datetime) else daybook.parse_when(when, self.clock().date())
        daybook.add_event(self.writable, title, start, int(minutes or 30))
        self.refresh()
        if self.prepare_new:
            e = next((x for x in self.day.events if x.summary == title and x.start == start), None)
            if e is not None:
                self.send_upcoming(e)
        return start

    def _event_from(self, payload, title: str, markdown: str) -> None:
        """A cart that names a time (`When: tomorrow 11:00, 30 min`) becomes an event, titled as the cart."""
        found = daybook.find_when(f"{payload.value}\n{markdown}", self.clock().date())
        name = (payload.title or title).strip()
        if found is None or not name:
            return
        start, minutes = found
        if any(e.summary == name and e.start == start for e in self.day.events):
            return                                       # the same cart twice: one event
        try:
            self.add(name, start, minutes)
        except (ValueError, OSError) as e:
            self.toast(f"{name[:60]}: {e}", title="🥁 Not added", severity="warning")

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
        beats = self.beats()
        lines += [self.beat_line(b, docs) for kind in ("schedule", "limit")
                  for b in [next((x for x in beats if x.kind == kind), None)] if b is not None]
        return lines

    def beat_line(self, b: drumbeat.Beat, docs: dict | None = None) -> str:
        """One beat as the hut says it: `[14:00] 📄 1:1 Ann`, `[05:00] ↻ Watchtower`, `[≈17:40] gold limit`."""
        now = self.clock()
        when = f"{b.at:%a} {b.at:%H:%M}" if b.at.date() != now.date() else f"{b.at:%H:%M}"
        if b.kind == "meeting":
            e = self.event(b.ref)
            return f"[{when}] {'▶ ' if b.now else ''}{self.mark(e, docs) if e else ''}{b.title}"
        if b.kind == "schedule":
            return f"[{when}] ↻ {b.title}"
        if b.reached:
            return f"[!] {b.title} limit reached"
        return f"[≈{when}] {b.title} limit"

    def hut_lines(self, widths: list[int]) -> list[str]:
        _, _, left = self.now_and_next()
        docs = self.docs()
        beats = drumbeat.ahead(self.beats(), HUT_BEATS)
        lines = [self.beat_line(b, docs) for b in beats] or ["nothing ahead"]
        lines += [""] * (HUT_BEATS - len(lines))
        approx = any(b.approx for b in beats)
        lines.append(f"left today: {left}" + (" · ≈ estimate" if approx else ""))
        return lines
