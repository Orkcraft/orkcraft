"""The retros and the orks' own changes in the GUI, as the TUI's night (tui/night.py, tui/retros.py) and
with the same core (core/retros.py, core/night.py): the host's clock calls `tick` once a second.

    the retros     the Building retro (`optimize_at`, daily) and the Town retro (`weekly_at`) when due, each
                   in a thread; their proposals wait in the Town Hall (Apply / Dismiss)
    quiet hours    one change at a time that the town's level or the building's own autonomy lets the orks
                   apply (core/night.py `candidates`): the Council's Fast Path looks first (a thread), and
                   only while it is still quiet and the Council lets it is it applied, hushed
    probation      every few minutes: a change with a 👎 or more failed runs since goes back by itself
    the morning    what the orks changed while the operator was away, in one toast

    nightly = Nightly(host)
    nightly.tick(quiet, morning=…)
"""
from __future__ import annotations

import datetime as dt
import threading
import time
from typing import Any, Callable

from orkcraft import schedule
from orkcraft.core import retros, runners
from orkcraft.realm import fastpath

RETRO_CHECK_S = 60.0          # how often the retros' schedules are looked at


class Nightly:
    def __init__(self, host) -> None:
        self.host = host
        self.town = host.town
        self.busy: set[str] = set()              # the retros running now: daily | weekly
        self.checked_at = -RETRO_CHECK_S

    def tick(self, quiet: bool, morning: bool = False, now: float | None = None) -> None:
        now = time.monotonic() if now is None else now
        if morning:
            words = retros.morning_words(self.town)
            if words:
                self.town.toast(words, title="While you were away, the orks changed", timeout=20)
        exhausted = self.host.treasury.exhausted(quiet=True)
        if now - self.checked_at >= RETRO_CHECK_S and not exhausted:
            self.checked_at = now
            today = dt.datetime.now()
            for name, job, done in (("daily", retros.daily_job, retros.daily_done),
                                    ("weekly", retros.weekly_job, retros.weekly_done)):
                if name not in self.busy:
                    work = job(self.town, today)
                    if work is not None:
                        self._thread(name, work, done)
        taken = self.host.night.next_change(quiet, self.town.machine.autonomy, exhausted)
        if taken is not None:
            self._consider(*taken)
        if self.host.night.probation_due():
            retros.probation(self.town)

    def _thread(self, name: str, work: Callable[[], Any], done: Callable[[Any, Any], None]) -> None:
        """A retro's model call off the clock; its result back on the town's thread."""
        self.busy.add(name)

        def run() -> None:
            try:
                result = work()
            except Exception as e:              # a retro that fails never stops the clock
                self.town.call(self._failed, name, e)
                return
            self.town.call(self._finished, name, done, result)

        threading.Thread(target=run, daemon=True, name=f"retro-{name}").start()

    def _finished(self, name: str, done: Callable[[Any, Any], None], result: Any) -> None:
        self.busy.discard(name)
        done(self.town, result)

    def _failed(self, name: str, e: Exception) -> None:
        self.busy.discard(name)
        self.town.toast(f"{type(e).__name__}: {e}", title="🔧 Building retro" if name == "daily" else "🗓 Town retro",
                        severity="warning")

    # -- 🌙 the orks' own changes -----------------------------------------------------------------------

    def _consider(self, c: dict, subject: fastpath.Subject) -> None:
        """The Council's Fast Path looks at the change as it would be (a thread), then `_apply`."""
        repo, taken = self.town.repo_root, self.town.taken_ids() - {subject.id}

        def run() -> None:
            try:
                runner = runners.FASTPATH_RUNNER or fastpath.light_runner(repo)
                verdict = fastpath.review(subject, repo, taken, runner=runner)
            except Exception:
                self.town.call(self.host.night.changed, False)
                return
            self.town.call(self._apply, c, verdict)

        threading.Thread(target=run, daemon=True, name="evolve").start()

    def _apply(self, c: dict, verdict: fastpath.Verdict) -> None:
        """Applied by the orks only while it is still quiet and the Council let it; else it stays a proposal."""
        if not schedule.quiet_now(self.town.machine) or not self.host.night.council_lets(verdict):
            self.host.night.changed(False)
            return
        try:
            ok = retros.apply_change(self.town, c)
        except Exception:                       # a change that fails is left as a proposal
            ok = False
        self.host.night.changed(ok)
        if ok:
            self.host.refresh_roster()
