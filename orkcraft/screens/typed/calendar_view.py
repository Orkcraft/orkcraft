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

Over the meetings lie the town's scheduled runs (↻) and ≈ when its limits are reached at the present
burn rate (realm/drumbeat.py): the head says the limits, the week each day's runs and limits, the hut
the next of all three.

The work — loading, the clock, the documents, adding — is the building's worker's
(core/workers/war_drum.py); the view draws the day and the week and holds the dialog.
"""
from __future__ import annotations

import datetime as dt

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Horizontal, VerticalScroll
from textual.widgets import OptionList, Static
from textual.widgets.option_list import Option

from orkcraft.core.workers.war_drum import DOC, TICK_S, WarDrumWorker
from orkcraft.design import tokens
from orkcraft.realm import catalog, daybook, drumbeat
from orkcraft.screens.dialogs import TextPrompt
from orkcraft.screens.typed.base import TypedView


def _tone(tone: str) -> str:
    """A colour role as the terminal draws it: the camp's theme (design/tokens.json)."""
    try:
        return tokens.color(tone, "camp")
    except KeyError:
        return ""


def _beat(b: drumbeat.Beat) -> str:
    """A run or a limit in the week: `↻ 05:00 Watchtower · daily 05:00`, `≈ 17:40 gold limit · $2.60 / $5.00`."""
    if b.kind == "schedule":
        return f"{drumbeat.MARK['schedule']} {b.at:%H:%M} {b.title} · {b.detail}"
    if b.reached:
        return f"{drumbeat.MARK['limit']} now {b.title} limit reached · {b.detail}"
    return f"{drumbeat.MARK['limit']} {b.at:%H:%M} {b.title} limit (estimate) · {b.detail}"


class CalendarView(TypedView):
    TYPE = "war_drum"
    UI_PANES = {"head": "#cal-head", "day": "#cal-today", "week": "#cal-week-scroll"}

    def __init__(self, *a, **kw) -> None:
        super().__init__(*a, **kw)
        self._rows: list = []                        # today's events, as the list shows them

    @property
    def worker(self) -> WarDrumWorker:
        return super().worker

    # -- the worker's state, as the view's own (tests and other views read these) -------------------

    @property
    def day(self) -> daybook.Day:
        return self.worker.day

    @property
    def own_ics(self):
        return self.worker.own_ics

    @property
    def lead(self) -> dt.timedelta:
        return self.worker.lead

    @property
    def configured(self) -> str:
        return self.worker.configured

    def clock(self) -> dt.datetime:
        return self.worker.clock()

    def docs(self) -> dict:
        return self.worker.docs()

    def doc_of(self, e) -> dict | None:
        return self.worker.doc_of(e)

    def send_upcoming(self, e) -> bool:
        return self.worker.send_upcoming(e)

    def receive(self, payload, title: str, markdown: str) -> None:
        self.worker.receive(payload, title, markdown)

    def tick(self) -> None:
        self.worker.tick()

    # -- the view -----------------------------------------------------------------------------------

    def compose_body(self) -> ComposeResult:
        yield Static("", id="cal-head", classes="typed-head")
        with Horizontal(classes="typed-row"):
            yield OptionList(id="cal-today", classes="typed-list")
            with VerticalScroll(classes="typed-detail", id="cal-week-scroll"):
                yield Static("", id="cal-week")

    def on_mount(self) -> None:
        super().on_mount()
        self.set_interval(TICK_S, self.tick)          # the worker loads the calendar again by itself

    def refresh_data(self) -> None:
        self.worker.refresh()
        self._render_list()

    def redraw(self) -> None:
        self._render_list()

    def open_doc(self, e) -> bool:
        """Enter on a meeting: its document along its road, else in the Lake of Insight. False when it has none."""
        doc = self.worker.open_doc(e)
        if doc is None:
            return False
        if doc["sent"]:
            return True
        path, title = doc["path"], doc["title"]
        app = self.app
        lake = next((bid for bid, spec in getattr(app, "custom_specs", {}).items()
                     if catalog.type_of(spec).id == "lake"), None)
        view = app._custom_view(lake) if lake else None
        if view is None or not hasattr(view, "show_value"):
            app.notify(f"{path} — build a Lake of Insight (or a road to one) to read it here", title=title)
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
        return self.worker.selected()

    def _render_list(self) -> None:
        w = self.worker
        now = w.clock()
        try:
            head, today, week = (self.query_one("#cal-head", Static), self.query_one("#cal-today", OptionList),
                                 self.query_one("#cal-week", Static))
        except Exception:
            return
        cur, nxt, left = daybook.now_and_next(w.day.events, now)
        bits = [f"{now:%A %d %B}"]
        if cur:
            bits.append(f"now: {cur.summary}")
        if nxt:
            bits.append(f"next {daybook.when(nxt)[:5]}: {nxt.summary}")
        bits.append(f"{left} left today")
        limits = w.limits()
        for lim in limits:
            if lim.reached:
                bits.append(f"{lim.what} limit reached")
            elif lim.at is not None:
                when = f"{lim.at:%H:%M}" if lim.at.date() == now.date() else f"{lim.at:%a %H:%M}"
                bits.append(f"≈{when} {lim.what} limit")
        if w.day.errors:
            bits.append("⚠ " + "; ".join(w.day.errors)[:80])
        if not w.configured and not w.day.events:
            bits.append("set `ics` in the building's settings, or + to add an event")
        head.update(Text(" · ".join(bits), style="dim"))
        docs = w.docs()
        keep = today.highlighted
        today.clear_options()
        self._rows = w.today()
        for i, e in enumerate(self._rows):
            past = isinstance(e.start, dt.datetime) and (daybook._end(e) or e.start) <= now
            style = "dim" if past else "bold" if e is cur else ""
            today.add_option(Option(Text(w.mark(e, docs) + daybook.line(e), style=style, no_wrap=True,
                                         overflow="ellipsis"), id=f"e{i}"))
        if keep is not None and keep < len(self._rows):
            today.highlighted = keep
        by_day = w.week_beats(limits)
        t = Text()
        for d in range(daybook.WEEK_DAYS):
            day = now.date() + dt.timedelta(days=d)
            evs = [e for e in w.day.events if e.day == day]
            marks = by_day.get(day, [])
            t.append(f"{'Today' if d == 0 else f'{day:%a %d %b}'}\n", style="bold")
            for e in evs:
                t.append(f"  {w.mark(e, docs)}{daybook.line(e)}\n")
            for b in marks:
                t.append(f"  {_beat(b)}\n", style=_tone(b.tone))
            if not evs and not marks:
                t.append("  —\n", style="dim")
        week.update(t)

    # -- the hut ----------------------------------------------------------------------------------

    def mini_status(self) -> list[str]:
        return self.worker.mini_status()

    def hut_lines(self, widths: list[int]) -> list[str]:
        return self.worker.hut_lines(widths)

    def quick_action(self, action_id: str) -> bool:
        if action_id == "calendar.prepare":
            e = self.selected()
            problem = self.worker.prepare(e) if e is not None else "pick a meeting in today's list first"
            if problem:
                self.app.notify(problem, title=f"{DOC} Prepare doc",
                                severity="warning" if "road" in problem else "information")
            else:
                self.app.notify(f"{daybook.line(e)}", title=f"{DOC} Preparing")
            return True
        if action_id == "calendar.import":
            self.app.notify("Import calendar is in the window: orkcraft gui", title="🥁 Import calendar")
            return True
        if action_id != "calendar.new":
            return False
        target = self.worker.writable

        def done(answer: str | None) -> None:
            if not answer:
                return
            title, when, minutes = (answer.split("\t") + ["", ""])[:3]
            try:
                start = self.worker.add(title, when, int(minutes or 30))
            except (ValueError, OSError) as e:
                self.app.notify(str(e), title="📅 Not added", severity="error")
                return
            self.app.notify(f"{start:%a %d %H:%M} {title}", title="📅 Added")

        self.app.push_screen(TextPrompt("📅 New event", placeholder="title",
                                        fields=(("when: 14:30 · tomorrow 9:00 · 2026-10-05 14:00", ""),
                                                ("minutes (30)", "")),
                                        help=f"saved to {target.name}"), done)
        return True
