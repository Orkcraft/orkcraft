"""Mission 1's quest log in the GUI (docs/design/first-mission.md §3; core/mission.py does the work): the
Warchief's line shows the quest under way, its one press and the way out (js/mission.js).

    face = MissionFace(host)
    host.commands.update(face.commands())    # mission.raise · mission.leave · mission.seen
    face.snapshot()                          # the snapshot's `mission`, None when there is none
    face.tick()                              # from the host's clock: a quest done moves the log on
"""
from __future__ import annotations

from typing import Any, Callable

from orkcraft.core.mission import Mission


class MissionError(Exception):
    """A quest that cannot be done now: its text is shown to the person."""


class MissionFace:
    def __init__(self, host) -> None:
        self.host = host

    @property
    def mission(self) -> Mission:
        return Mission(self.host.town)          # the town may be another after a project switch

    def commands(self) -> dict[str, Callable[[dict], Any]]:
        return {"mission.raise": self.raise_it, "mission.leave": self.leave, "mission.seen": self.seen}

    def begin(self) -> None:
        self.mission.begin()
        self.host.on_change()

    def raise_it(self, args: dict) -> str:
        built = self.mission.raise_it()
        if not built:
            raise MissionError("Nothing to raise for this quest")
        self.host.on_change()
        return built

    def leave(self, args: dict) -> None:
        self.mission.leave()
        self.host.on_change()

    def seen(self, args: dict) -> None:
        self.mission.seen_end()
        self.host.on_change()

    def snapshot(self) -> dict | None:
        try:
            return self.mission.view()
        except (OSError, ValueError):            # the quest log never breaks the page
            return None

    def tick(self) -> None:
        try:
            moved = self.mission.tick()
        except (OSError, ValueError):
            return
        if moved:
            self.host.on_change()
