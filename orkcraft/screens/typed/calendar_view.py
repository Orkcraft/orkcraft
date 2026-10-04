"""📅 Calendar: the day and the week from an `.ics` file or URL.

The hut tells what is on now, what is next and how much is left today; the open building lists
today on the left and the week on the right. Every 30 s it looks at the clock: an event that
starts sends `calendar.event_due`; once a day, at `day_starts` (08:00), the day's digest goes out
as `calendar.day_schedule`; a reload that finds events added or removed sends those. `+` adds an
event (to the local calendar — a URL calendar is read-only).

Documents for meetings: `lead` (2h) before a meeting starts, `calendar.event_upcoming` goes out
once (`upcoming.json` remembers which went, so a restart does not repeat them), tagged
`[meet:<id>]` in its title and its text; 📄 (]) sends it for the selected meeting at once. Which
meetings get a document is the roads' business (a Signpost), not the Drum's. A cart that comes back
with the tag — a Barracks' `pool.done` — is the meeting's document (`docs.json`): a file it names,
else its Markdown kept in `docs/<id>.md`. The meeting then shows 📄, and Enter on it sends the
document as `calendar.doc_opened` — along its road, or straight to a Lake of Insight when none
carries it.
"""
from __future__ import annotations

import datetime as dt
import json
import re
from pathlib import Path

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Horizontal, VerticalScroll
from textual.widgets import OptionList, Static
from textual.widgets.option_list import Option

from orkcraft.realm import catalog, daybook, shelves
from orkcraft.screens.dialogs import TextPrompt
from orkcraft.screens.typed.base import TypedView

TICK_S = 30.0
RELOAD_S = 300.0
DOC = "📄"
_PATH = re.compile(r"`([^`\n]+\.[A-Za-z0-9]{1,8})`")


class CalendarView(TypedView):
    TYPE = "war_drum"
    clock = staticmethod(dt.datetime.now)          # tests move time here

    def __init__(self, *a, **kw) -> None:
        super().__init__(*a, **kw)
        self.day: daybook.Day = daybook.Day([], [])
        self._last_events: list | None = None
        self._since: dt.datetime | None = None
        self._rows: list = []                        # today's events, as the list shows them

    @property
    def own_ics(self):
        return self.state_dir / "local.ics"

    @property
    def lead(self) -> dt.timedelta:
        return daybook.parse_lead(str(self.config.get("lead", "")))

    @property
    def configured(self) -> str:
        return str(self.config.get("ics", ""))

    def compose_body(self) -> ComposeResult:
        yield Static("", id="cal-head", classes="typed-head")
        with Horizontal(classes="typed-row"):
            yield OptionList(id="cal-today", classes="typed-list")
            with VerticalScroll(classes="typed-detail"):
                yield Static("", id="cal-week")

    def on_mount(self) -> None:
        self.refresh_data()
        self.set_interval(TICK_S, self.tick)
        self.set_interval(RELOAD_S, self.refresh_data)

    # -- data ---------------------------------------------------------------------------------------

    def refresh_data(self) -> None:
        now = self.clock()
        srcs = daybook.sources(self._get_repo_root(), self.configured, self.own_ics)
        self.day = daybook.load(srcs, now.date())
        for event_id, e in daybook.changes(self._last_events, self.day.events):
            self.emit(event_id, daybook.line(e) + f" ({e.day:%a %d})", e.summary)
        self._last_events = list(self.day.events)
        if self._since is None:
            self._since = now
        self._render_list()

    def tick(self) -> None:
        now = self.clock()
        if self._since is not None and now.date() != self._since.date():
            self.refresh_data()                       # a new day: load its events
        since, self._since = self._since or now, now
        for e in daybook.due(self.day.events, since, now):
            self.emit("calendar.event_due", daybook.line(e), e.summary)
        self._maybe_upcoming(since, now)
        self._maybe_digest(now)
        self._render_list()

    # -- documents for meetings -------------------------------------------------------------------

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

    def send_upcoming(self, e) -> bool:
        tag = f"[meet:{daybook.meet_id(e)}]"
        return self.emit("calendar.event_upcoming", f"{daybook.line(e)} ({e.day:%a %d}) {tag}", f"{e.summary} {tag}")

    def docs(self) -> dict:
        return self._load("docs.json")

    def doc_of(self, e) -> dict | None:
        return self.docs().get(daybook.meet_id(e))

    def receive(self, payload, title: str, markdown: str) -> None:
        """A meeting's document came back: a cart tagged `[meet:<id>]`."""
        mid = daybook.meet_tag(payload.title) or daybook.meet_tag(title) or daybook.meet_tag(payload.value)
        if not mid:
            return
        repo = self._get_repo_root()
        path = payload.value if payload.kind == "file" else self._named_file(repo, payload.value)
        if not path:
            doc = self.state_dir / "docs" / f"{mid}.md"
            doc.parent.mkdir(parents=True, exist_ok=True)
            doc.write_text(markdown or payload.value, encoding="utf-8")
            path = shelves.rel_to(repo, doc)
        docs = self.docs()
        docs[mid] = {"path": path, "title": title or payload.title, "at": self.clock().isoformat(timespec="seconds")}
        self._save("docs.json", docs)
        self._render_list()

    @staticmethod
    def _named_file(repo: Path, text: str) -> str:
        """A file the text names in `backticks` that is there in the repository."""
        for m in _PATH.finditer(text or ""):
            p = Path(m.group(1).strip())
            if (p if p.is_absolute() else repo / p).is_file():
                return m.group(1).strip()
        return ""

    def open_doc(self, e) -> bool:
        """Enter on a meeting: its document in the Lake of Insight. False when it has none."""
        doc = self.doc_of(e)
        if not doc:
            return False
        path, title = doc["path"], f"{DOC} {e.summary}"
        if self.emit("calendar.doc_opened", path, title):
            return True
        app = self.app
        lake = next((bid for bid, spec in getattr(app, "custom_specs", {}).items()
                     if catalog.type_of(spec).id == "lake"), None)
        view = app._custom_view(lake) if lake else None
        if view is None or not hasattr(view, "show_value"):
            app.notify(f"{path} — build a Lake of Insight (or a road to one) to read it here", title=f"{DOC} {e.summary}")
            return True
        view.show_value("file", path, title)
        win = app.desktop.get_window(lake)
        if win is not None:
            app.desktop.focus_window(win)
        return True

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        if event.option_list.id != "cal-today" or not event.option.id:
            return
        i = int(event.option.id[1:])
        if i < len(self._rows) and self.open_doc(self._rows[i]):
            event.stop()

    def selected(self):
        try:
            i = self.query_one("#cal-today", OptionList).highlighted
        except Exception:
            i = None
        if i is not None and i < len(self._rows):
            return self._rows[i]
        now = self.clock()
        cur, nxt, _ = daybook.now_and_next(self.day.events, now)
        return nxt or cur

    def _maybe_digest(self, now: dt.datetime) -> None:
        if now.time() < daybook.parse_day_starts(str(self.config.get("day_starts", ""))):
            return
        state = self.state_dir / "digest.json"
        try:
            last = json.loads(state.read_text(encoding="utf-8")).get("day", "")
        except (OSError, ValueError, AttributeError):
            last = ""
        if last == now.date().isoformat():
            return
        sent = self.emit("calendar.day_schedule", daybook.digest(self.day.events, now.date()),
                         f"{now:%A %d %B}")
        if sent:
            state.parent.mkdir(parents=True, exist_ok=True)
            state.write_text(json.dumps({"day": now.date().isoformat()}), encoding="utf-8")

    def _render_list(self) -> None:
        now = self.clock()
        try:
            head, today, week = (self.query_one("#cal-head", Static), self.query_one("#cal-today", OptionList),
                                 self.query_one("#cal-week", Static))
        except Exception:
            return
        cur, nxt, left = daybook.now_and_next(self.day.events, now)
        bits = [f"{now:%A %d %B}"]
        if cur:
            bits.append(f"now: {cur.summary}")
        if nxt:
            bits.append(f"next {daybook.when(nxt)[:5]}: {nxt.summary}")
        bits.append(f"{left} left today")
        if self.day.errors:
            bits.append("⚠ " + "; ".join(self.day.errors)[:80])
        if not self.configured and not self.day.events:
            bits.append("set `ics` in the building's settings, or + to add an event")
        head.update(Text(" · ".join(bits), style="dim"))
        docs = self.docs()
        keep = today.highlighted
        today.clear_options()
        self._rows = [x for x in self.day.events if x.day == now.date()]
        for i, e in enumerate(self._rows):
            past = isinstance(e.start, dt.datetime) and (daybook._end(e) or e.start) <= now
            style = "dim" if past else "bold" if e is cur else ""
            mark = f"{DOC} " if daybook.meet_id(e) in docs else ""
            today.add_option(Option(Text(mark + daybook.line(e), style=style, no_wrap=True, overflow="ellipsis"),
                                    id=f"e{i}"))
        if keep is not None and keep < len(self._rows):
            today.highlighted = keep
        t = Text()
        for d in range(daybook.WEEK_DAYS):
            day = now.date() + dt.timedelta(days=d)
            evs = [e for e in self.day.events if e.day == day]
            t.append(f"{'Today' if d == 0 else f'{day:%a %d %b}'}\n", style="bold")
            for e in evs:
                t.append(f"  {self._mark(e, docs)}{daybook.line(e)}\n")
            if not evs:
                t.append("  —\n", style="dim")
        week.update(t)

    # -- the hut ----------------------------------------------------------------------------------

    @staticmethod
    def _mark(e, docs: dict) -> str:
        return f"{DOC} " if daybook.meet_id(e) in docs else ""

    def mini_status(self) -> list[str]:
        now = self.clock()
        cur, nxt, left = daybook.now_and_next(self.day.events, now)
        docs = self.docs()
        lines = []
        if cur:
            lines.append(f"▶ {self._mark(cur, docs)}{cur.summary}")
        if nxt:
            lines.append(f"{daybook.when(nxt)[:5]} {self._mark(nxt, docs)}{nxt.summary}")
        lines.append(f"{left} left today" if left else "nothing more today")
        later = [e for e in self.day.events if e.day > now.date()][:2]
        lines += [f"{e.day:%a} {daybook.when(e)[:5]} {self._mark(e, docs)}{e.summary}" for e in later]
        return lines

    def hut_lines(self, widths: list[int]) -> list[str]:
        now = self.clock()
        cur, nxt, left = daybook.now_and_next(self.day.events, now)
        docs = self.docs()
        today = [e for e in self.day.events if e.day == now.date()][:4]
        lines = [f"[{daybook.when(e)[:5]}] {self._mark(e, docs)}{e.summary}" for e in today] or ["nothing today"]
        lines += [""] * (5 - len(lines))
        lines.append(f"now: {cur.summary}" if cur else f"next: {daybook.when(nxt)[:5]} {nxt.summary}" if nxt
                     else "next: nothing more")
        lines.append(f"left today: {left}")
        return lines

    def quick_action(self, action_id: str) -> bool:
        if action_id == "calendar.prepare":
            e = self.selected()
            if e is None or not isinstance(e.start, dt.datetime):
                self.app.notify("pick a meeting in today's list first", title=f"{DOC} Prepare doc")
            elif self.send_upcoming(e):
                self.app.notify(f"{daybook.line(e)}", title=f"{DOC} Preparing")
            else:
                self.app.notify("no road carries `meeting soon` yet", title=f"{DOC} Prepare doc", severity="warning")
            return True
        if action_id != "calendar.new":
            return False
        target = daybook.writable(self._get_repo_root(), self.configured, self.own_ics)

        def done(answer: str | None) -> None:
            if not answer:
                return
            title, when, minutes = (answer.split("\t") + ["", ""])[:3]
            try:
                start = daybook.parse_when(when, self.clock().date())
                daybook.add_event(target, title, start, int(minutes or 30))
            except (ValueError, OSError) as e:
                self.app.notify(str(e), title="📅 Not added", severity="error")
                return
            self.refresh_data()
            self.app.notify(f"{start:%a %d %H:%M} {title}", title="📅 Added")

        self.app.push_screen(TextPrompt("📅 New event", placeholder="title",
                                        fields=(("when: 14:30 · tomorrow 9:00 · 2026-10-05 14:00", ""),
                                                ("minutes (30)", "")),
                                        help=f"saved to {target.name}"), done)
        return True
