"""📜 The town's day logs in the GUI (realm/day_log.py): every model call is kept by day and building while the window
is open, a building's day is a zip to download (gui/server.py `/api/logs/<building>?day=`), and each morning the days
nobody asked for and no 👎 marked are cleared."""
from __future__ import annotations

import dataclasses
import datetime as dt

from orkcraft.realm import call_log, day_log, feedback


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
            day_log.clear(self.root, today, lambda b, day: any(
                i.ts.startswith(day) and i.source not in feedback.NOT_QUALITY and (i.building == b or i.blames(b))
                for i in rows))
        except OSError:
            pass

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
