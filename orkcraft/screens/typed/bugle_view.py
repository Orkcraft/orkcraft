"""🎺 The Bugle: every cart that comes down its roads sounds — a sound of your choice per event.

The open building lists what comes in (one row per event on its roads, then `*` for everything
else) with the sound each one plays (realm/bugle.py). Enter walks a row to the next sound and
plays it; `t` plays the highlighted row; `m` mutes and unmutes; `e` edits the whole table as
text (`building/event`, `event`, `building` or `*`, then a sound or an audio file). The calls are
on the right: what came, what sounded, and why one stayed quiet (muted, quiet hours, cooldown).
"""
from __future__ import annotations

import time

from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, VerticalScroll
from textual.widgets import OptionList, Static
from textual.widgets.option_list import Option

from orkcraft.realm import bugle, catalog, jobs
from orkcraft.screens.dialogs import TextBlock
from orkcraft.screens.typed.base import TypedView

HELP = ("one line each, the most precise wins: building/event: sound · event: sound · building: sound · *: sound\n"
        f"sounds: {', '.join(bugle.SOUNDS)} — or a path to an audio file (.wav, .mp3, .ogg…)")


class BugleView(TypedView):
    TYPE = "bugle"
    BINDINGS = [Binding("t", "test", "Play"), Binding("m", "toggle_mute", "Mute / unmute"),
                Binding("e", "edit_table", "Edit the table")]
    player = None                        # tests put a fake player here: (path | None, sound) -> how

    def __init__(self, *a, **kw) -> None:
        super().__init__(*a, **kw)
        self.calls: list[bugle.Call] = []
        self.rows: list[tuple[str, str]] = []    # (source, event) of each row; ("", "*") is everything else
        self._last: dict[str, float] = {}

    # -- settings -----------------------------------------------------------------------------------

    @property
    def lines(self) -> list[str]:
        return [str(x) for x in (self.config.get("sounds") or [])]

    @property
    def table(self) -> dict[str, str]:
        return bugle.parse(self.lines)[0]

    @property
    def default(self) -> str:
        sound = str(self.config.get("default") or bugle.DEFAULT)
        return sound if bugle.sound_ok(sound) else bugle.DEFAULT

    @property
    def muted(self) -> bool:
        return bool(self.config.get("muted"))

    @property
    def cooldown(self) -> int:
        return int(self.config.get("cooldown", 2))

    def incoming(self) -> list[tuple[str, str]]:
        """(source, event) of every road into the bugle, in road order, once each."""
        scroll = getattr(getattr(self, "app", None), "scroll", None)
        me = scroll.building(self.building_id) if scroll is not None else None
        return list(dict.fromkeys((r.source, r.event) for r in (me.roads if me is not None else [])))

    def sound_of(self, source: str, event: str) -> str:
        if event == "*":
            return self.table.get("*", self.default)
        return bugle.pick(self.table, source, event, self.default)[0]

    def key_of(self, source: str, event: str) -> str:
        """The line of the table a change to this row goes to: the one that decides it when it is about
        this event (`event` or `source/event`), else a new `event` line."""
        if event == "*":
            return "*"
        key = bugle.pick(self.table, source, event, self.default)[1]
        return key if key in (event, f"{source}/{event}") else event

    # -- the view -----------------------------------------------------------------------------------

    def compose_body(self) -> ComposeResult:
        yield Static("", id="bugle-head", classes="typed-head")
        with Horizontal(classes="typed-row"):
            yield OptionList(id="bugle-table", classes="typed-list")
            with VerticalScroll(classes="typed-detail"):
                yield Static("", id="bugle-calls")

    def refresh_data(self) -> None:
        self.calls = bugle.calls(self.state_dir)
        self._redraw()

    def _redraw(self) -> None:
        try:
            head, lst = self.query_one("#bugle-head", Static), self.query_one("#bugle-table", OptionList)
            log = self.query_one("#bugle-calls", Static)
        except Exception:
            return
        cmd = self._player_cmd()
        quiet = str(self.config.get("quiet") or "")
        problems = bugle.parse(self.lines)[1]
        t = Text(style="dim")
        t.append("🔇 muted · " if self.muted else "🎺 on · ", style="bold yellow" if self.muted else "bold green")
        t.append(f"cooldown {self.cooldown}s · quiet hours {quiet or '—'} · plays with "
                 f"{cmd[0] if cmd else 'the terminal bell'}\nEnter: next sound · t: play · m: mute · e: edit the table")
        for p in problems:
            t.append(f"\n⚠ {p}", style="yellow")
        head.update(t)
        keep = lst.highlighted
        lst.clear_options()
        self.rows = []
        names = self._titles()
        for source, event in self.incoming():
            row = Text(no_wrap=True, overflow="ellipsis")
            row.append(f"♪ {self.sound_of(source, event):<6} ", style="bold cyan")
            row.append(f"{catalog.event_label(event) or event}  ")
            row.append(names.get(source, source), style="dim")
            lst.add_option(Option(row))
            self.rows.append((source, event))
        row = Text(no_wrap=True, overflow="ellipsis")
        row.append(f"♪ {self.sound_of('', '*'):<6} ", style="bold cyan")
        row.append("everything else", style="italic")
        if not self.rows:
            row.append("  (no road comes here yet — Y on the Bugle draws one)", style="dim")
        lst.add_option(Option(row))
        self.rows.append(("", "*"))
        lst.highlighted = min(keep or 0, len(self.rows) - 1)
        out = Text()
        for c in self.calls[:60]:
            out.append(f"{c.at[11:19]} ", style="dim")
            out.append(f"♪ {c.sound}" if c.heard else f"· {c.sound} ({c.played})",
                       style="bold cyan" if c.heard else "dim")
            out.append(f"  {names.get(c.source, c.source)} · {catalog.event_label(c.event) or c.event}")
            if c.title:
                out.append(f" · {c.title[:60]}", style="dim")
            out.append("\n")
        log.update(out if self.calls else Text("nothing has sounded yet", style="dim"))

    def _titles(self) -> dict[str, str]:
        scroll = getattr(getattr(self, "app", None), "scroll", None)
        return {b.id: b.title for b in getattr(scroll, "buildings", [])} if scroll is not None else {}

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        if event.option_list.id == "bugle-table" and event.option_index < len(self.rows):
            event.stop()
            self.cycle(*self.rows[event.option_index])

    def _highlighted(self) -> tuple[str, str]:
        try:
            i = self.query_one("#bugle-table", OptionList).highlighted
        except Exception:
            i = None
        return self.rows[i] if i is not None and i < len(self.rows) else ("", "*")

    # -- choosing ----------------------------------------------------------------------------------

    def cycle(self, source: str, event: str) -> str:
        """The row of `event` from `source` (or *) takes the next sound; it plays at once so you hear it."""
        sound = bugle.next_sound(self.sound_of(source, event))
        if self.save_config({"sounds": bugle.put(self.lines, self.key_of(source, event), sound)}):
            self._sound(sound)
            self._redraw()
        return sound

    def action_test(self) -> None:
        self._sound(self.sound_of(*self._highlighted()))

    def action_toggle_mute(self) -> None:
        if self.save_config({"muted": not self.muted}):
            self._redraw()

    def action_edit_table(self) -> None:
        def done(text: str | None) -> None:
            if text is None:
                return
            if self.save_config({"sounds": [ln.strip() for ln in text.splitlines() if ln.strip()]}):
                self._redraw()

        self.app.push_screen(TextBlock("🎺 The Bugle — which event plays which sound", "\n".join(self.lines), HELP), done)

    # -- sounding -----------------------------------------------------------------------------------

    def _player_cmd(self) -> tuple[str, ...] | None:
        return None if type(self).player is not None else bugle.player()

    def _sound(self, sound: str) -> str:
        """Play `sound` now; how it went: player | bell | none."""
        if sound == bugle.NONE:
            return "none"
        path = bugle.sound_file(self._get_repo_root(), sound)
        fake = type(self).player
        if fake is not None:
            return fake(path, sound)
        if path is not None and bugle.play(path, self._player_cmd()):
            return "player"
        self.app.bell()
        return "bell"

    def receive(self, payload, title: str, markdown: str) -> None:
        sound, key = bugle.pick(self.table, payload.source, payload.mode, self.default)
        now = time.monotonic()
        heard_key = key or "default"
        if self.muted:
            how = "muted"
        elif bugle.in_quiet(str(self.config.get("quiet") or "")):
            how = "quiet"
        elif now - self._last.get(heard_key, -1e9) < self.cooldown:
            how = "cooldown"
        else:
            self._last[heard_key] = now
            how = self._sound(sound)
        call = bugle.Call(jobs.now_iso(), payload.source, payload.mode, payload.title or title, sound, how)
        bugle.log(self.state_dir, call)
        if call.heard:
            self.emit("bugle.sounded", f"{sound} for {payload.mode} from {payload.source}\n\n{payload.value[:2000]}",
                      f"♪ {sound} · {payload.title or title}")
        self.refresh_data()

    # -- the hut ------------------------------------------------------------------------------------

    def hut_lines(self, widths: list[int]) -> list[str]:
        """One short line: muted, the last sound that played, else the default."""
        if self.muted:
            return ["🔇 muted"]
        last = next((c for c in self.calls if c.heard), None)
        return [f"♪ {last.sound if last else self.sound_of('', '*')}"]

    def mini_status(self) -> list[str]:
        lines = ["🔇 muted" if self.muted else f"♪ {len(self.incoming())} events → sounds"]
        if self.calls:
            c = self.calls[0]
            lines.append(f"last: {c.sound} for {c.event}")
        return lines

    def quick_action(self, action_id: str) -> bool:
        if action_id == "bugle.test":
            self.action_test()
            return True
        if action_id == "bugle.mute":
            self.action_toggle_mute()
            self.app.notify("muted" if self.muted else "sounding again", title="🎺 The Bugle")
            return True
        return False
