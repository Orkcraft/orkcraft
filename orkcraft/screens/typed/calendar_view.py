"""📅 Calendar: the day and the week from an `.ics` file or URL.

The hut tells what is on now, what is next and how much is left today; the open building lists
today on the left and the week on the right. Every 30 s it looks at the clock: an event that
starts sends `calendar.event_due`; once a day, at `day_starts` (08:00), the day's digest goes out
as `calendar.day_schedule`; a reload that finds events added or removed sends those. `+` adds an
event (to the local calendar — a URL calendar is read-only).
"""
from __future__ import annotations

import datetime as dt
import json

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Horizontal, VerticalScroll
from textual.widgets import OptionList, Static
from textual.widgets.option_list import Option

from orkcraft.realm import daybook
from orkcraft.screens.dialogs import TextPrompt
from orkcraft.screens.typed.base import TypedView

TICK_S = 30.0
RELOAD_S = 300.0


class CalendarView(TypedView):
    TYPE = "war_drum"
    clock = staticmethod(dt.datetime.now)          # tests move time here

    def __init__(self, *a, **kw) -> None:
        super().__init__(*a, **kw)
        self.day: daybook.Day = daybook.Day([], [])
        self._last_events: list | None = None
        self._since: dt.datetime | None = None

    @property
    def own_ics(self):
        return self.state_dir / "local.ics"

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
        self._maybe_digest(now)
        self._render_list()

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
        today.clear_options()
        for i, e in enumerate(x for x in self.day.events if x.day == now.date()):
            past = isinstance(e.start, dt.datetime) and (daybook._end(e) or e.start) <= now
            style = "dim" if past else "bold" if e is cur else ""
            today.add_option(Option(Text(daybook.line(e), style=style, no_wrap=True, overflow="ellipsis"),
                                    id=f"e{i}"))
        t = Text()
        for d in range(daybook.WEEK_DAYS):
            day = now.date() + dt.timedelta(days=d)
            evs = [e for e in self.day.events if e.day == day]
            t.append(f"{'Today' if d == 0 else f'{day:%a %d %b}'}\n", style="bold")
            for e in evs:
                t.append(f"  {daybook.line(e)}\n")
            if not evs:
                t.append("  —\n", style="dim")
        week.update(t)

    # -- the hut ----------------------------------------------------------------------------------

    def mini_status(self) -> list[str]:
        now = self.clock()
        cur, nxt, left = daybook.now_and_next(self.day.events, now)
        lines = []
        if cur:
            lines.append(f"▶ {cur.summary}")
        if nxt:
            lines.append(f"{daybook.when(nxt)[:5]} {nxt.summary}")
        lines.append(f"{left} left today" if left else "nothing more today")
        later = [e for e in self.day.events if e.day > now.date()][:2]
        lines += [f"{e.day:%a} {daybook.when(e)[:5]} {e.summary}" for e in later]
        return lines

    def hut_lines(self, widths: list[int]) -> list[str]:
        now = self.clock()
        cur, nxt, left = daybook.now_and_next(self.day.events, now)
        today = [e for e in self.day.events if e.day == now.date()][:4]
        lines = [f"[{daybook.when(e)[:5]}] {e.summary}" for e in today] or ["nothing today"]
        lines += [""] * (5 - len(lines))
        lines.append(f"now: {cur.summary}" if cur else f"next: {daybook.when(nxt)[:5]} {nxt.summary}" if nxt
                     else "next: nothing more")
        lines.append(f"left today: {left}")
        return lines

    def quick_action(self, action_id: str) -> bool:
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
