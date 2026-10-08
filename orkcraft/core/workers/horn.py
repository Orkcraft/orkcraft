"""📯 The Horn's work: which sound answers which road, and every call, heard or kept quiet.

A cart down one of its roads picks its sound from the table (realm/horn.py) and plays it unless the
horn is muted, in its quiet hours, within its cooldown or the person asked not to be disturbed
(`town.hushed`, docs/design/portrait.md §4); every call goes to `calls.jsonl`, and a
call that sounded goes out as `horn.sounded`. `cycle` walks a row to the next sound and plays it,
`set_sound` gives a row a sound or an audio file, `mute` flips it.

Who plays is the face's: the TUI sets `player` (the system's player, else the terminal bell); with
none set the page plays it — `plays` counts the sounds it was asked for, `played` is the last.
"""
from __future__ import annotations

import time
from pathlib import Path
from typing import Callable

from orkcraft.core.workers import Worker
from orkcraft.realm import horn, jobs

PAGE = "page"                 # how a sound went when the page plays it


class HornWorker(Worker):
    TYPE = "horn"

    def __init__(self, town, building_id: str) -> None:
        super().__init__(town, building_id)
        self.calls: list[horn.Call] = []
        self.player: Callable[[Path | None, str], str] | None = None   # the face's: (file, sound) -> how
        self.plays = 0                       # sounds the page was asked to play
        self.played = ""                     # the last of them
        self._last: dict[str, float] = {}

    # -- settings -------------------------------------------------------------------------------

    @property
    def lines(self) -> list[str]:
        return [str(x) for x in (self.config.get("sounds") or [])]

    @property
    def table(self) -> dict[str, str]:
        return horn.parse(self.lines)[0]

    @property
    def problems(self) -> list[str]:
        return horn.parse(self.lines)[1]

    @property
    def default(self) -> str:
        sound = str(self.config.get("default") or horn.DEFAULT)
        return sound if horn.sound_ok(sound) else horn.DEFAULT

    @property
    def muted(self) -> bool:
        return bool(self.config.get("muted"))

    @property
    def quiet(self) -> str:
        return str(self.config.get("quiet") or "")

    @property
    def cooldown(self) -> int:
        return int(self.config.get("cooldown", 2))

    def incoming(self) -> list[tuple[str, str]]:
        """(source, event) of every road into the horn, in road order, once each."""
        scroll = self.town.scroll
        me = scroll.building(self.building_id) if scroll is not None else None
        return list(dict.fromkeys((r.source, r.event) for r in (me.roads if me is not None else [])))

    def rows(self) -> list[tuple[str, str]]:
        """The table as it shows: a row per incoming road, then everything else (`("", "*")`)."""
        return [*self.incoming(), ("", "*")]

    def titles(self) -> dict[str, str]:
        scroll = self.town.scroll
        return {b.id: b.title for b in getattr(scroll, "buildings", [])} if scroll is not None else {}

    def sound_of(self, source: str, event: str) -> str:
        if event == "*":
            return self.table.get("*", self.default)
        return horn.pick(self.table, source, event, self.default)[0]

    def key_of(self, source: str, event: str) -> str:
        """The line of the table a change to this row goes to: the one that decides it when it is about
        this event (`event` or `source/event`), else a new `event` line."""
        if event == "*":
            return "*"
        key = horn.pick(self.table, source, event, self.default)[1]
        return key if key in (event, f"{source}/{event}") else event

    # -- its life -------------------------------------------------------------------------------

    def start(self) -> None:
        self.refresh()

    def refresh(self) -> None:
        self.calls = horn.calls(self.state_dir)
        self.changed()

    def status(self) -> str:
        return "MUTED" if self.muted else ""

    # -- choosing -------------------------------------------------------------------------------

    def cycle(self, source: str, event: str) -> str:
        """The row of `event` from `source` (or *) takes the next sound; it plays at once so you hear it."""
        sound = horn.next_sound(self.sound_of(source, event))
        if self.set_sound(source, event, sound):
            self.sound(sound)
        return sound

    def set_sound(self, source: str, event: str, sound: str) -> bool:
        """The row's sound: a built-in one or an audio file. False when the spec refused it."""
        if self.save_config({"sounds": horn.put(self.lines, self.key_of(source, event), sound)}):
            self.changed()
            return True
        return False

    def mute(self, on: bool | None = None) -> bool:
        """Mute or unmute (`on` None flips it); whether it is muted now."""
        want = (not self.muted) if on is None else bool(on)
        if want != self.muted:
            self.save_config({"muted": want})
            self.changed()
        return self.muted

    def test(self, source: str = "", event: str = "*") -> str:
        """Play a row's sound now."""
        return self.sound(self.sound_of(source, event))

    # -- sounding -------------------------------------------------------------------------------

    def sound(self, sound: str) -> str:
        """Play `sound` now; how it went: player | bell | page | none."""
        if sound == horn.NONE:
            return "none"
        if self.player is not None:
            return self.player(horn.sound_file(self.repo_root, sound), sound)
        self.plays += 1
        self.played = sound
        self.changed()
        return PAGE

    def receive(self, payload, title: str, markdown: str) -> None:
        sound, key = horn.pick(self.table, payload.source, payload.mode, self.default)
        now = time.monotonic()
        heard_key = key or "default"
        if self.muted:
            how = "muted"
        elif horn.in_quiet(self.quiet):
            how = "quiet"
        elif getattr(self.town, "hushed", lambda: False)():
            how = "dnd"
        elif now - self._last.get(heard_key, -1e9) < self.cooldown:
            how = "cooldown"
        else:
            self._last[heard_key] = now
            how = self.sound(sound)
        call = horn.Call(jobs.now_iso(), payload.source, payload.mode, payload.title or title, sound, how)
        horn.log(self.state_dir, call)
        if call.heard:
            self.emit("horn.sounded", f"{sound} for {payload.mode} from {payload.source}\n\n{payload.value[:2000]}",
                      f"♪ {sound} · {payload.title or title}")
        self.refresh()

    # -- the hut --------------------------------------------------------------------------------

    def last_heard(self) -> horn.Call | None:
        return next((c for c in self.calls if c.heard), None)

    def hut_lines(self, widths: list[int]) -> list[str]:
        """One short line: muted, the last sound that played, else the default."""
        if self.muted:
            return ["🔇 muted"]
        last = self.last_heard()
        return [f"♪ {last.sound if last else self.sound_of('', '*')}"]

    def mini_status(self) -> list[str]:
        lines = ["🔇 muted" if self.muted else f"♪ {len(self.incoming())} events → sounds"]
        if self.calls:
            c = self.calls[0]
            lines.append(f"last: {c.sound} for {c.event}")
        return lines
