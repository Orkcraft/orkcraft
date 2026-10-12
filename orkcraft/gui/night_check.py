"""✅ The Mechanic's night check (docs/design/check.md §8): once a night, in the quiet hours, `orkcraft check` runs on
the cheap AI tool — the scenarios in turn, `check_per_night` of them a night and all of them on Saturday night — and
the quiet town; what it found against the last check is said in the morning, with the Elders.

It runs only in a town that has a Test bench (the person chose to have the Mechanic) and while the Council's
`check_nightly` is on. The night's improvements (gui/improve_night.py) wait while it runs: two jobs on one AI tool
account at once slow each other and the numbers say so (docs/nights/2026-10-11.md).

    night = NightCheck(host); night.tick(quiet, exhausted); night.busy; night.morning() → lines
"""
from __future__ import annotations

import datetime as dt
import json
import time
from pathlib import Path

from orkcraft.realm import catalog, check, check_history, fastpath

STATE = check.DIR / "night.json"             # {"night": the last night it ran, "turn": the next scenario's index}
LOOK_S = 60.0                                # how often the night looks whether its check is due or done
ALL_ON = 5                                   # the evening whose night checks everything: Saturday's


class NightCheck:
    def __init__(self, host) -> None:
        self.host = host
        self.town = host.town
        self.looked = -LOOK_S
        self.running = False
        self.lines: list[str] = []

    @property
    def root(self) -> Path:
        return self.town.repo_root

    @property
    def busy(self) -> bool:
        return self.running

    def _state(self) -> dict:
        try:
            data = json.loads((self.root / STATE).read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except (OSError, ValueError):
            return {}

    def _save(self, data: dict) -> None:
        path = self.root / STATE
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

    def settings(self) -> dict:
        s = fastpath.settings(self.root)
        try:
            per = max(int(s.get("check_per_night") or 2), 1)
        except (TypeError, ValueError):
            per = 2
        return {"on": bool(s.get("check_nightly", True)), "per_night": per}

    def _has_mechanic(self) -> bool:
        return any(not b.demolished and catalog.type_of(self.town.spec_of(b.id)).id == "lab"
                   for b in self.town.scroll.buildings)

    def tonight(self, now: dt.datetime | None = None) -> list[str]:
        """The scenarios tonight's check runs: the next ones in turn, every one on Saturday's night."""
        ids = [s.id for s in check.SCENARIOS if s.type]
        night = dt.date.fromisoformat(check_history.night_key(now))
        if night.weekday() == ALL_ON:
            return ids
        turn, per = int(self._state().get("turn") or 0), self.settings()["per_night"]
        return [ids[(turn + k) % len(ids)] for k in range(min(per, len(ids)))]

    def tick(self, quiet: bool, exhausted: bool = False, now: float | None = None,
             when: dt.datetime | None = None) -> None:
        now = time.monotonic() if now is None else now
        if now - self.looked < LOOK_S:
            return
        self.looked = now
        engine = getattr(self.host, "bench", None)
        if engine is None:
            return
        job = engine.check.job()
        if self.running:
            if job is None or job.done:
                self.running = False
                self._finished(job)
            return
        if not quiet or exhausted or self.town.demo or not self.settings()["on"] or not self._has_mechanic():
            return
        state, key = self._state(), check_history.night_key(when)
        if state.get("night") == key or (job is not None and not job.done):
            return
        scenarios = self.tonight(when)
        try:
            engine.check.start(scenarios)
        except Exception as e:  # a check that does not start is said in the morning, the night goes on
            self.lines.append(f"The night check did not start: {e}")
            self._save({**state, "night": key})
            return
        ids = [s.id for s in check.SCENARIOS if s.type]
        self._save({**state, "night": key, "turn": (int(state.get("turn") or 0) + len(scenarios)) % len(ids),
                    "scenarios": scenarios})
        self.running = True

    def _finished(self, job) -> None:
        if job is not None and job.error:
            self.lines.append(f"The Mechanic's night check stopped: {job.error}")
            return
        last = self.host.bench.check.last()
        if not last:
            return
        titles = [sc["title"] for sc in (last.get("told") or {}).get("scenarios") or [] if sc.get("stories")]
        worse = [m for m in last.get("since") or [] if m["dir"] == "worse"]
        better = [m for m in last.get("since") or [] if m["dir"] == "better"]
        line = (f"The Mechanic checked {', '.join(titles) or 'the quiet town'}: "
                f"{'green' if last.get('green') else 'red'}")
        if worse:
            line += "; worse than before: " + "; ".join(f"{m['case']} ({m['said']})" for m in worse[:2])
        elif better:
            line += "; better than before: " + "; ".join(f"{m['case']} ({m['said']})" for m in better[:2])
        self.lines.append(line + " — the Test bench has what to change")

    def morning(self) -> list[str]:
        out, self.lines = self.lines, []
        return out
