"""📜 Improve reads a day (docs/design/improve-buildings.md §13): the Warchief's Improve, on a day picked, has the
Mechanic and the Farseer read that day's logs (realm/day_review.py) in a thread of their own; when they are done the
Warchief is asked to offer each change, to apply or skip. A day read before is not read again (no cost) unless asked.
At night (gui/nightly.py, with the Elders, while the Council's `review_nightly` is on) yesterday is read the same way,
and the morning says what was found: Improve then goes through it at no cost.

    host.day_review.start(key, ask_warchief=True)     host.day_review.state()     .tick(quiet, exhausted, when)
    host.day_review.since_update()                    the key of the logs since the last update, up to now

*Since the last update* reads the logs from the moment this machine started on the code it runs now (core/running.py:
an update installed, a `git pull`) up to the press, so the work done on the latest changes is read and no older.
    improve.findings {day} → its findings and the Test bench each can go to; improve.try {day, n} → tried and
    measured there (gui/day_try.py)
"""
from __future__ import annotations

import datetime as dt
import threading
import time

from orkcraft.core import running
from orkcraft.gui import day_try
from orkcraft.realm import analytics, builders, call_log, check_history, day_review, fastpath
from orkcraft.sources import telemetry

DAYS_SHOWN = 14                         # the days Improve offers, newest first
DAYS_FRESH_S = 30.0                     # the days are looked at again at most this often (the snapshot asks often)
HALL = "town_hall"


class DayReview:
    def __init__(self, host) -> None:
        self.host = host
        self.town = host.town
        self.running = ""                    # the day being read now
        self.night = ""                      # the night key of the last night's reading
        self.lines: list[str] = []           # for the morning, with the Elders
        self._days: tuple[float, dict] = (-DAYS_FRESH_S, {})

    @property
    def root(self):
        return self.town.repo_root

    def days(self) -> list[dict]:
        """The days with logs, newest first, and whether the Elders read each already."""
        out = []
        for day in analytics.days_kept(self.root)[:DAYS_SHOWN]:
            kept = day_review.load(self.root, day)
            out.append({"day": day, "read": kept.said if kept else "", "changes": len(kept.findings) if kept else 0})
        return out

    def update(self) -> dict:
        """The logs since the last update: {"at": since when, "key": the latest reading of them, "read", "changes"}."""
        since = running.since()
        stamp = since.strftime(day_review.STAMP)
        kept = sorted((p.stem for p in (self.root / day_review.DIR).glob(f"{stamp}{day_review.SPAN}*.json")),
                      reverse=True)
        review = day_review.load(self.root, kept[0]) if kept else None
        return {"at": since.isoformat(timespec="minutes"), "key": kept[0] if kept else "",
                "read": review.said if review else "", "changes": len(review.findings) if review else 0}

    def since_update(self, now: dt.datetime | None = None) -> str:
        """The key of the logs since the last update, up to now; ValueError when none is kept since."""
        since, now = running.since(), now or dt.datetime.now()
        key = day_review.span_key(since, max(now, since))
        if not set(day_review.bounds(key)[2]) & set(analytics.days_kept(self.root)):
            raise ValueError(f"No logs kept since the last update ({since.strftime('%Y-%m-%d %H:%M')})")
        return key

    def state(self) -> dict:
        at, days = self._days
        if time.monotonic() - at >= DAYS_FRESH_S:
            days = {"days": self.days(), "update": self.update()}
            self._days = (time.monotonic(), days)
        return {"running": self.running, **days}

    def _titles(self) -> dict[str, str]:
        titles = {b.id: b.title for b in self.town.scroll.buildings}
        titles.setdefault(call_log.TOWN, "The town")
        return titles

    def _ask(self, who: str, prompt: str):
        with telemetry.tagged("retro"):
            return builders.ask(builders.main_tool(self.town.machine), prompt)

    def start(self, day: str, ask_warchief: bool = True, again: bool = False) -> str:
        """Read `day` (in a thread), unless it was read before and not `again`: then its findings go to the Warchief
        at once. What to say now."""
        if self.running:
            return f"The Elders are reading {day_review.label(self.running)}: one reading at a time"
        kept = None if again else day_review.load(self.root, day)
        if kept is not None:
            self._done(kept, ask_warchief)
            return kept.said
        self.running = day
        threading.Thread(target=self._read, args=(day, ask_warchief), daemon=True, name="day-review").start()
        return f"The Mechanic and the Farseer are reading {day_review.label(day)}"

    def _read(self, day: str, ask_warchief: bool) -> day_review.Review | None:
        logs = getattr(self.host, "day_logs", None)
        review = None
        try:
            rows = []
            if logs is not None:
                from orkcraft.realm import feedback
                rows = feedback.incidents(self.root, 5000)
            review = day_review.run(self.root, day, self._ask, self._titles(),
                                    logs.decisions if logs else (lambda b, d: []),
                                    (lambda b, d: logs._dislikes(rows, b, d)) if logs else (lambda b, d: []))
        except Exception as e:  # a day that cannot be read is said; the town goes on
            self.town.toast(f"The Elders could not read {day_review.label(day)}: {str(e)[:200]}", title="Improve", severity="warning")
        finally:
            self.running = ""
            self._days = (-DAYS_FRESH_S, {})
        if review is not None:
            self.town.call(self._done, review, ask_warchief)
        self.town.call(self.host.on_change)
        return review

    def _done(self, review: day_review.Review, ask_warchief: bool) -> None:
        if review.errors and not review.findings:
            self.town.toast(f"{review.said}. " + "; ".join(review.errors), title="Improve", severity="warning")
            return
        if not review.findings:
            self.town.toast(review.said, title="Improve")
            return
        if not ask_warchief:
            return
        hall = self.town.workers.get(HALL)
        titles = self._titles()
        about = sorted({f.building for f in review.findings if f.building in titles})
        problem = hall.ask(day_review.warchief_text(review, titles), about) if hall is not None else "no Town Hall"
        if problem:
            self.town.toast(f"{review.said}; the Warchief could not take it: {problem}", title="Improve")

    # -- at night ------------------------------------------------------------------------------------------------

    def on(self) -> bool:
        return bool(fastpath.settings(self.root).get("review_nightly", True))

    def tick(self, quiet: bool, exhausted: bool = False, when: dt.datetime | None = None) -> None:
        """Once a night, in the quiet hours: yesterday's logs read, when they are kept and were not read yet."""
        when = when or dt.datetime.now()
        day = check_history.night_key(when)  # the night of the 12th reads the 12th, once it has ended
        if when.date().isoformat() <= day or not quiet or exhausted or self.running or self.night == day \
                or self.town.demo or not self.on():
            return
        self.night = day
        if day not in analytics.days_kept(self.root) or day_review.load(self.root, day) is not None:
            return
        self.running = day
        threading.Thread(target=self._night, args=(day,), daemon=True, name="day-review").start()

    def _night(self, day: str) -> None:
        review = self._read(day, ask_warchief=False)
        if review is not None and review.findings:
            self.town.call(self._handed, review)

    def _handed(self, review: day_review.Review) -> None:
        """The night's findings, each to a Test bench that tests its building: the night's improvements try them."""
        handed = day_try.hand(self.host, review.day)
        self.lines.append(f"The Mechanic and the Farseer read {review.said}"
                          + (f"; {handed} went to the Test bench to be tried" if handed else "")
                          + " — Improve goes through them")

    def commands(self) -> dict:
        def tried(args: dict) -> dict:
            try:
                return {"said": day_try.attempt(self.host, str(args.get("day") or ""), int(args.get("n") or 0))}
            except (day_try.TryError, ValueError) as e:
                return {"error": str(e)}
        return {"improve.findings": lambda a: {"findings": day_try.findings(self.host, str(a.get("day") or ""))},
                "improve.try": tried}

    def morning(self) -> list[str]:
        out, self.lines = self.lines, []
        return out
