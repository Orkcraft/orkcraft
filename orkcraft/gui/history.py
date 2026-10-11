"""The window's side of an orkspace's History (docs/design/projects.md §6, §7.3): the map's checkpoints, newest
first, and going back to one of them.

    history.list    {orkspace}        [{sha, at, when, what, building, kind}]
    history.revert  {orkspace, sha}   the map as it was then: {back, removed, elsewhere} (building titles)
"""
from __future__ import annotations

import re
from typing import Any, Callable

from orkcraft.core import maps

_SUBJECT = re.compile(r"^(?P<kind>[a-z-]+)\((?P<who>[^)]*)\):\s*(?P<what>.*)$")


class HistoryError(Exception):
    """A refusal said to the person."""


class History:
    def __init__(self, host) -> None:
        self.host = host

    def _orkspace(self, args: dict) -> str:
        oid = str(args.get("orkspace") or "")
        if self.host.town.scroll.orkspace(oid) is None:
            raise HistoryError(f"No orkspace {oid!r}")
        return oid

    def _title(self, building_id: str) -> str:
        bs = self.host.town.scroll.building(building_id)
        return bs.title if bs is not None else ""

    def _list(self, args: dict) -> list[dict[str, Any]]:
        rows = []
        for c in maps.history(self.host.town, self._orkspace(args)):
            m = _SUBJECT.match(c.message)
            kind, what = (m["kind"], m["what"]) if m else ("", c.message)
            building = c.building if c.building and c.building != "camp" else ""
            rows.append({"sha": c.sha, "at": c.at, "when": maps.when(c.at), "what": what, "kind": kind,
                         "building": self._title(building) or building})
        return rows

    def _revert(self, args: dict) -> dict[str, Any]:
        oid = self._orkspace(args)
        try:
            done = maps.revert(self.host.town, oid, str(args.get("sha") or "")[:40])
        except maps.MapError as e:
            raise HistoryError(str(e)) from None
        self.host.refresh_roster()
        self.host.on_change()
        names = lambda ids: [self._title(b) or b for b in ids]      # noqa: E731
        return {"back": names(done.back), "removed": names(done.removed), "elsewhere": names(done.elsewhere)}

    def commands(self) -> dict[str, Callable[[dict], Any]]:
        return {"history.list": self._list, "history.revert": self._revert}
