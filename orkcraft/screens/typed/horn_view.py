"""📯 The Horn: every cart that comes down its roads sounds — a sound of your choice per event.

The open building is one list: a row per road that comes in, its sound first, then `everything
else` (realm/horn.py). Enter walks a row to the next sound and plays it; `t` plays the row; `m`
mutes and unmutes; `e` edits the whole table as text (`building/event`, `event`, `building` or
`*`, then a sound or an audio file). One line under it says what sounded last; every call, heard
or kept quiet and why, is in `.orkcraft/horn/<id>/calls.jsonl`.

The table, the calls and choosing a sound are the building's worker's (core/workers/horn.py); the
view draws them and plays what the worker asks for: the system's player, else the terminal bell.
"""
from __future__ import annotations

from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.widgets import OptionList, Static
from textual.widgets.option_list import Option

from orkcraft.core.workers.horn import HornWorker
from orkcraft.realm import catalog, horn
from orkcraft.screens.dialogs import TextBlock
from orkcraft.screens.typed.base import TypedView

HELP = ("one line each, the most precise wins: building/event: sound · event: sound · building: sound · *: sound\n"
        f"sounds: {', '.join(horn.SOUNDS)} — or a path to an audio file (.wav, .mp3, .ogg…)")


class HornView(TypedView):
    TYPE = "horn"
    UI_PANES = {"settings": "#horn-keys", "table": "#horn-table"}     # the log is the one line under it
    BINDINGS = [Binding("t", "test", "Play"), Binding("m", "toggle_mute", "Mute / unmute"),
                Binding("e", "edit_table", "Edit the table")]
    player = None                        # tests put a fake player here: (path | None, sound) -> how

    def __init__(self, *a, **kw) -> None:
        super().__init__(*a, **kw)
        self.rows: list[tuple[str, str]] = []    # (source, event) of each row; ("", "*") is everything else

    @property
    def worker(self) -> HornWorker:
        return super().worker

    # -- the worker's state, as the view's own (tests and other views read these) -------------------

    @property
    def calls(self) -> list[horn.Call]:
        return self.worker.calls

    @property
    def lines(self) -> list[str]:
        return self.worker.lines

    @property
    def table(self) -> dict[str, str]:
        return self.worker.table

    @property
    def default(self) -> str:
        return self.worker.default

    @property
    def muted(self) -> bool:
        return self.worker.muted

    @property
    def cooldown(self) -> int:
        return self.worker.cooldown

    def incoming(self) -> list[tuple[str, str]]:
        return self.worker.incoming()

    def sound_of(self, source: str, event: str) -> str:
        return self.worker.sound_of(source, event)

    def key_of(self, source: str, event: str) -> str:
        return self.worker.key_of(source, event)

    def save_config(self, changes: dict) -> bool:
        if not self.worker.save_config(changes):
            return False
        self.spec = self.worker.spec
        self._redraw()
        return True

    def receive(self, payload, title: str, markdown: str) -> None:
        self.worker.receive(payload, title, markdown)

    def cycle(self, source: str, event: str) -> str:
        return self.worker.cycle(source, event)

    # -- the view -----------------------------------------------------------------------------------

    DEFAULT_CSS = """
    HornView #horn-table { height: 1fr; border: none; padding: 0 1; background: transparent; }
    HornView .horn-line { height: auto; padding: 0 2; color: $text-muted; }
    """

    def compose_body(self) -> ComposeResult:
        yield OptionList(id="horn-table")
        yield Static("", id="horn-last", classes="horn-line")
        yield Static("", id="horn-keys", classes="horn-line")

    def on_mount(self) -> None:
        w = self.worker
        if w is not None:
            w.player = self._play            # this face plays what the worker sounds
        super().on_mount()

    def refresh_data(self) -> None:
        if self.worker is not None:
            self.worker.refresh()
        self._redraw()

    def redraw(self) -> None:
        self._redraw()

    def _redraw(self) -> None:
        try:
            lst = self.query_one("#horn-table", OptionList)
            last, keys = self.query_one("#horn-last", Static), self.query_one("#horn-keys", Static)
        except Exception:
            return
        w = self.worker
        names = w.titles()
        keep = lst.highlighted
        lst.clear_options()
        self.rows = []
        for source, event in w.rows():
            row = Text(no_wrap=True, overflow="ellipsis")
            row.append(f"{w.sound_of(source, event):<7}", style="bold cyan")
            if event == "*":
                row.append("everything else", style="dim italic")
            else:
                row.append(f"{catalog.event_label(event) or event}")
                row.append(f" · {names.get(source, source)}", style="dim")
            lst.add_option(Option(row))
            self.rows.append((source, event))
        lst.highlighted = min(keep or 0, len(self.rows) - 1)
        c = w.last_heard()
        last.update(Text(
            f"last: {c.sound} · {names.get(c.source, c.source)} · "
            f"{catalog.event_label(c.event) or c.event} · {c.at[11:16]}" if c else
            "no road comes here yet — Y on the Horn draws one" if len(self.rows) == 1 else "nothing has sounded yet",
            style="dim"))
        state = [s for s in ("🔇 muted" if w.muted else "",
                             f"quiet {w.quiet}" if w.quiet else "",
                             "" if self._player_cmd() or type(self).player else "terminal bell") if s]
        state += [f"⚠ {p}" for p in w.problems]
        keys.update(Text(" · ".join(state + ["⏎ next sound  t play  m mute  e edit"]), style="dim"))

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

    def action_test(self) -> None:
        self.worker.test(*self._highlighted())

    def action_toggle_mute(self) -> None:
        self.worker.mute()

    def action_edit_table(self) -> None:
        def done(text: str | None) -> None:
            if text is None:
                return
            self.save_config({"sounds": [ln.strip() for ln in text.splitlines() if ln.strip()]})

        self.app.push_screen(TextBlock("📯 The Horn — which event plays which sound", "\n".join(self.lines), HELP), done)

    # -- sounding: what the worker asks this face to play -------------------------------------------

    def _player_cmd(self) -> tuple[str, ...] | None:
        return None if type(self).player is not None else horn.player()

    def _play(self, path, sound: str) -> str:
        """Play `sound` now; how it went: player | bell."""
        fake = type(self).player
        if fake is not None:
            return fake(path, sound)
        if path is not None and horn.play(path, self._player_cmd()):
            return "player"
        self.app.bell()
        return "bell"

    # -- the hut ------------------------------------------------------------------------------------

    def hut_lines(self, widths: list[int]) -> list[str]:
        return self.worker.hut_lines(widths)

    def mini_status(self) -> list[str]:
        return self.worker.mini_status()

    def quick_action(self, action_id: str) -> bool:
        if action_id == "horn.test":
            self.action_test()
            return True
        if action_id == "horn.mute":
            self.action_toggle_mute()
            self.app.notify("muted" if self.muted else "sounding again", title="📯 The Horn")
            return True
        return False
