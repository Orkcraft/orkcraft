"""📜 The town's day logs in the GUI (realm/day_log.py): every model call is kept by day and building while the window
is open, a building's day is a zip to download (gui/server.py `/api/logs/<building>?day=`), and each morning the days
nobody asked for and no 👎 marked are cleared — none is while the town keeps its logs for analysis (Town settings), and
a period of every building's days is one zip (realm/analytics.py, `/api/analytics?days=`). Yesterday waits for the
Elders' night reading (gui/day_review.py) before it is cleared."""
from __future__ import annotations

import dataclasses
import datetime as dt

from orkcraft.realm import analytics, call_log, day_log, day_review, event_log, fastpath, feedback


class DayLogs:
    def __init__(self, town) -> None:
        self.town = town
        self.root = town.repo_root
        self.cleared = ""                    # the day the last clearing ran on
        call_log.keep_days(self.root)

    def tick(self, today: dt.date | None = None) -> None:
        """Once a day, the first time the clock ticks in it: yesterday's logs and before, cleared."""
        today = today or dt.date.today()
        if self.cleared == today.isoformat():
            return
        self.cleared = today.isoformat()
        try:
            rows = feedback.incidents(self.root, 1000)
            yesterday = (today - dt.timedelta(days=1)).isoformat()
            unread = (bool(fastpath.settings(self.root).get("review_nightly", True))
                      and day_review.load(self.root, yesterday) is None)       # the Elders read it tonight first
            day_log.clear(self.root, today, lambda b, day: bool(self._dislikes(rows, b, day))
                          or (unread and day == yesterday), self.keeping())
        except OSError:
            pass

    def keeping(self) -> bool:
        """Whether every day is kept for analysis (the Council's `logs_for_analysis`)."""
        return bool(fastpath.settings(self.root).get("logs_for_analysis"))

    def keep(self, on: bool) -> None:
        fastpath.save_settings(self.root, {"logs_for_analysis": bool(on)})

    @staticmethod
    def _dislikes(rows, b: str, day: str) -> list[dict]:
        return [dataclasses.asdict(i) for i in rows if i.ts.startswith(day) and i.source not in feedback.NOT_QUALITY
                and (i.building == b or i.blames(b))]

    def state(self) -> dict:
        """{"on", "days": the days kept, "keep": how long while on}, for Town settings."""
        return {"on": self.keeping(), "days": len(analytics.days_kept(self.root)), "keep": day_log.KEEP_ANALYSIS}

    def pack_period(self, days: int = 7, today: dt.date | None = None) -> tuple[str, bytes] | None:
        """(file name, the zip) of every building's last `days` days (today among them); None when none is kept."""
        today = today or dt.date.today()
        days = max(1, min(int(days), day_log.KEEP_ANALYSIS))
        since = (today - dt.timedelta(days=days - 1)).isoformat()
        kept = [d for d in analytics.days_kept(self.root) if since <= d <= today.isoformat()]
        if not kept:       # no model call kept, but the board's events and ideas may be there (spec 33 §9)
            if not event_log.read(self.root, since) and not analytics._board_files(self.root):
                return None
            kept = [(today - dt.timedelta(days=n)).isoformat() for n in range(days)]
        titles = {b.id: b.title for b in self.town.scroll.buildings}
        titles.setdefault(call_log.TOWN, "The town (no building)")
        rows = feedback.incidents(self.root, 5000)
        data = analytics.pack(self.root, kept, titles, self.decisions, lambda b, day: self._dislikes(rows, b, day))
        return f"orkcraft-analytics-{kept[-1]}-to-{kept[0]}.zip", data

    def close(self) -> None:
        call_log.keep_days(None)

    def decisions(self, bid: str, day: str) -> list[dict]:
        """What the building's steward decided that day, when it keeps decisions (an Agent pool)."""
        state = getattr(self.town.workers.get(bid), "state", None)
        read = getattr(state, "decisions", None)
        if not callable(read):
            return []
        try:
            return [dataclasses.asdict(d) for d in reversed(read(2000)) if str(getattr(d, "at", "")).startswith(day)]
        except (TypeError, ValueError):
            return []

    def pack(self, bid: str, day: str = "") -> tuple[str, bytes] | None:
        """(file name, the zip) of the building's day (today when none is named); None for no such building."""
        bs = self.town.scroll.building(bid)
        day = day or dt.date.today().isoformat()
        if bs is None or day_log._day(day) is None:
            return None
        data = day_log.pack(self.root, bid, day, bs.title, self.decisions(bid, day))
        return f"orkcraft-{bid}-{day}.zip", data
