"""The window's side of an orkspace's History (docs/design/projects.md §6, §7.3): one timeline of the map's
checkpoints and the snapshots of its project's files, newest first, and going back to one of them.

    history.list    {orkspace}                       {rows: [...], files: bool}
    history.revert  {orkspace, sha, what?, files?}   what: "map" (default) | "files" | "both"

A map row is {type: "map", sha, at, when, what, kind, building, files}: `files` is the project's snapshot of that
moment (the newest one not after it), when there is one. A files row is {type: "files", sha, at, when, what,
changed}: the files that differ from the snapshot before it.
"""
from __future__ import annotations

import datetime as dt
import re
from pathlib import Path
from typing import Any, Callable

from orkcraft.core import maps
from orkcraft.realm import halt, projects, snapshots

_SUBJECT = re.compile(r"^(?P<kind>[a-z-]+)\((?P<who>[^)]*)\):\s*(?P<what>.*)$")
CHANGED_SHOWN = 20


def _utc(at: str) -> dt.datetime:
    """A time git gave, in UTC, so the map's and the files' rows sort together."""
    try:
        return dt.datetime.fromisoformat(at).astimezone(dt.timezone.utc)
    except ValueError:
        return dt.datetime.min.replace(tzinfo=dt.timezone.utc)


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

    def _folder(self, oid: str):
        folder = projects.root_of(self.host.town.scroll, oid, self.host.town.repo_root)
        return folder if snapshots.has_git(folder) else None

    def _title(self, building_id: str) -> str:
        bs = self.host.town.scroll.building(building_id)
        return bs.title if bs is not None else ""

    def _list(self, args: dict) -> dict[str, Any]:
        oid = self._orkspace(args)
        folder = self._folder(oid)
        snaps = snapshots.listed(folder, oid) if folder is not None else []
        rows: list[dict[str, Any]] = []
        for i, s in enumerate(snaps):
            before = snaps[i + 1].sha if i + 1 < len(snaps) else None
            changed = snapshots.changed(folder, s.sha, before) if before else []
            rows.append({"type": "files", "sha": s.sha, "at": _utc(s.at).isoformat(), "when": maps.when(s.at), "what": s.why,
                         "changed": changed[:CHANGED_SHOWN], "changed_n": len(changed), "first": before is None})
        for c in maps.history(self.host.town, oid):
            m = _SUBJECT.match(c.message)
            kind, what = (m["kind"], m["what"]) if m else ("", c.message)
            building = c.building if c.building and c.building != "camp" else ""
            then = next((s.sha for s in snaps if _utc(s.at) <= _utc(c.at)), None)
            rows.append({"type": "map", "sha": c.sha, "at": _utc(c.at).isoformat(), "when": maps.when(c.at), "what": what,
                         "kind": kind, "building": self._title(building) or building, "files": then})
        rows.sort(key=lambda r: _utc(r["at"]), reverse=True)
        return {"rows": rows, "files": folder is not None}

    def _busy(self, folder) -> bool:
        live = getattr(getattr(self.host, "sessions", None), "live", {}) or {}
        here = str(folder.resolve())
        return halt.agents() > 0 or any(s.running and str(Path(s.cwd).resolve()) == here for s in live.values())

    def _revert(self, args: dict) -> dict[str, Any]:
        oid = self._orkspace(args)
        what = str(args.get("what") or "map")
        if what not in ("map", "files", "both"):
            raise HistoryError(f"Nothing to go back to as {what!r}")
        out: dict[str, Any] = {"back": [], "removed": [], "elsewhere": [], "files": False}
        if what in ("files", "both"):
            folder = self._folder(oid)
            snap = str(args.get("files") or (args.get("sha") if what == "files" else "") or "")[:40]
            if folder is None or not snap:
                raise HistoryError("This orkspace's project has no snapshots to go back to")
            if self._busy(folder):
                raise HistoryError("An ork is at work: the files go back once it is done, or after Stop all")
            try:
                snapshots.restore(folder, oid, snap)
            except snapshots.SnapshotError as e:
                raise HistoryError(str(e)) from None
            out["files"] = True
        if what in ("map", "both"):
            try:
                done = maps.revert(self.host.town, oid, str(args.get("sha") or "")[:40])
            except maps.MapError as e:
                raise HistoryError(str(e)) from None
            names = lambda ids: [self._title(b) or b for b in ids]      # noqa: E731
            out.update(back=names(done.back), removed=names(done.removed), elsewhere=names(done.elsewhere))
            self.host.refresh_roster()
        self.host.on_change()
        return out

    def commands(self) -> dict[str, Callable[[dict], Any]]:
        return {"history.list": self._list, "history.revert": self._revert}
