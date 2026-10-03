"""📯 The Horn: every cart that comes down its roads sounds — a sound of your choice per event.

The open building is one list: a row per road that comes in, its sound first, then `everything
else` (realm/horn.py). Enter walks a row to the next sound and plays it; `t` plays the row; `m`
mutes and unmutes; `e` edits the whole table as text (`building/event`, `event`, `building` or
`*`, then a sound or an audio file). One line under it says what sounded last; every call, heard
or kept quiet and why, is in `.orkcraft/horn/<id>/calls.jsonl`.
"""
from __future__ import annotations

import time

from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.widgets import OptionList, Static
from textual.widgets.option_list import Option

from orkcraft.realm import catalog, horn, jobs
from orkcraft.screens.dialogs import TextBlock
from orkcraft.screens.typed.base import TypedView

HELP = ("one line each, the most precise wins: building/event: sound · event: sound · building: sound · *: sound\n"
        f"sounds: {', '.join(horn.SOUNDS)} — or a path to an audio file (.wav, .mp3, .ogg…)")


class HornView(TypedView):
    TYPE = "horn"
    BINDINGS = [Binding("t", "test", "Play"), Binding("m", "toggle_mute", "Mute / unmute"),
                Binding("e", "edit_table", "Edit the table")]
    player = None                        # tests put a fake player here: (path | None, sound) -> how

    def __init__(self, *a, **kw) -> None:
        super().__init__(*a, **kw)
        self.calls: list[horn.Call] = []
        self.rows: list[tuple[str, str]] = []    # (source, event) of each row; ("", "*") is everything else
        self._last: dict[str, float] = {}

    # -- settings -----------------------------------------------------------------------------------

    @property
    def lines(self) -> list[str]:
        return [str(x) for x in (self.config.get("sounds") or [])]

    @property
    def table(self) -> dict[str, str]:
        return horn.parse(self.lines)[0]

    @property
    def default(self) -> str:
        sound = str(self.config.get("default") or horn.DEFAULT)
        return sound if horn.sound_ok(sound) else horn.DEFAULT

    @property
    def muted(self) -> bool:
        return bool(self.config.get("muted"))

    @property
    def cooldown(self) -> int:
        return int(self.config.get("cooldown", 2))

    def incoming(self) -> list[tuple[str, str]]:
        """(source, event) of every road into the horn, in road order, once each."""
        scroll = getattr(getattr(self, "app", None), "scroll", None)
        me = scroll.building(self.building_id) if scroll is not None else None
        return list(dict.fromkeys((r.source, r.event) for r in (me.roads if me is not None else [])))

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

    # -- the view -----------------------------------------------------------------------------------

    DEFAULT_CSS = """
    HornView #horn-table { height: 1fr; border: none; padding: 0 1; background: transparent; }
    HornView .horn-line { height: auto; padding: 0 2; color: $text-muted; }
    """

    def compose_body(self) -> ComposeResult:
        yield OptionList(id="horn-table")
        yield Static("", id="horn-last", classes="horn-line")
        yield Static("", id="horn-keys", classes="horn-line")

    def refresh_data(self) -> None:
        self.calls = horn.calls(self.state_dir)
        self._redraw()

    def _redraw(self) -> None:
        try:
            lst = self.query_one("#horn-table", OptionList)
            last, keys = self.query_one("#horn-last", Static), self.query_one("#horn-keys", Static)
        except Exception:
            return
        names = self._titles()
        keep = lst.highlighted
        lst.clear_options()
        self.rows = []
        for source, event in [*self.incoming(), ("", "*")]:
            row = Text(no_wrap=True, overflow="ellipsis")
            row.append(f"{self.sound_of(source, event):<7}", style="bold cyan")
            if event == "*":
                row.append("everything else", style="dim italic")
            else:
                row.append(f"{catalog.event_label(event) or event}")
                row.append(f" · {names.get(source, source)}", style="dim")
            lst.add_option(Option(row))
            self.rows.append((source, event))
        lst.highlighted = min(keep or 0, len(self.rows) - 1)
        c = next((x for x in self.calls if x.heard), None)
        last.update(Text(
            f"last: {c.sound} · {names.get(c.source, c.source)} · "
            f"{catalog.event_label(c.event) or c.event} · {c.at[11:16]}" if c else
            "no road comes here yet — Y on the Horn draws one" if len(self.rows) == 1 else "nothing has sounded yet",
            style="dim"))
        state = [s for s in ("🔇 muted" if self.muted else "",
                             f"quiet {self.config['quiet']}" if self.config.get("quiet") else "",
                             "" if self._player_cmd() or type(self).player else "terminal bell") if s]
        state += [f"⚠ {p}" for p in horn.parse(self.lines)[1]]
        keys.update(Text(" · ".join(state + ["⏎ next sound  t play  m mute  e edit"]), style="dim"))

    def _titles(self) -> dict[str, str]:
        scroll = getattr(getattr(self, "app", None), "scroll", None)
        return {b.id: b.title for b in getattr(scroll, "buildings", [])} if scroll is not None else {}

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        if event.option_list.id == "horn-table" and event.option_index < len(self.rows):
            event.stop()
            self.cycle(*self.rows[event.option_index])

    def _highlighted(self) -> tuple[str, str]:
        try:
            i = self.query_one("#horn-table", OptionList).highlighted
        except Exception:
            i = None
        return self.rows[i] if i is not None and i < len(self.rows) else ("", "*")

    # -- choosing ----------------------------------------------------------------------------------

    def cycle(self, source: str, event: str) -> str:
        """The row of `event` from `source` (or *) takes the next sound; it plays at once so you hear it."""
        sound = horn.next_sound(self.sound_of(source, event))
        if self.save_config({"sounds": horn.put(self.lines, self.key_of(source, event), sound)}):
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

        self.app.push_screen(TextBlock("📯 The Horn — which event plays which sound", "\n".join(self.lines), HELP), done)

    # -- sounding -----------------------------------------------------------------------------------

    def _player_cmd(self) -> tuple[str, ...] | None:
        return None if type(self).player is not None else horn.player()

    def _sound(self, sound: str) -> str:
        """Play `sound` now; how it went: player | bell | none."""
        if sound == horn.NONE:
            return "none"
        path = horn.sound_file(self._get_repo_root(), sound)
        fake = type(self).player
        if fake is not None:
            return fake(path, sound)
        if path is not None and horn.play(path, self._player_cmd()):
            return "player"
        self.app.bell()
        return "bell"

    def receive(self, payload, title: str, markdown: str) -> None:
        sound, key = horn.pick(self.table, payload.source, payload.mode, self.default)
        now = time.monotonic()
        heard_key = key or "default"
        if self.muted:
            how = "muted"
        elif horn.in_quiet(str(self.config.get("quiet") or "")):
            how = "quiet"
        elif now - self._last.get(heard_key, -1e9) < self.cooldown:
            how = "cooldown"
        else:
            self._last[heard_key] = now
            how = self._sound(sound)
        call = horn.Call(jobs.now_iso(), payload.source, payload.mode, payload.title or title, sound, how)
        horn.log(self.state_dir, call)
        if call.heard:
            self.emit("horn.sounded", f"{sound} for {payload.mode} from {payload.source}\n\n{payload.value[:2000]}",
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
        if action_id == "horn.test":
            self.action_test()
            return True
        if action_id == "horn.mute":
            self.action_toggle_mute()
            self.app.notify("muted" if self.muted else "sounding again", title="📯 The Horn")
            return True
        return False
