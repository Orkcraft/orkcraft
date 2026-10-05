"""A terminal inside a Textual widget: an ork's session (core/sessions.py), drawn with pyte.

The process, its PTY and its screen are the core's (the GUI draws the same sessions with
xterm.js); the widget opens its session on mount, draws the session's screen, and sends it keys,
pastes and its size. The app passes what the session prints and when it ends (`output`,
`finished`).

Every key goes to the process — Claude Code's and agy's own TUIs (polls, buttons,
`/model`, `/goal`, …) work as in a real terminal — except the keys in
`RESERVED_KEYS`, which stay with orkcraft so focus can leave the terminal.
"""
from __future__ import annotations

import time

import pyte
from rich.segment import Segment
from rich.style import Style
from textual import events
from textual.geometry import Size
from textual.message import Message
from textual.strip import Strip
from textual.widget import Widget

# Stay with orkcraft even inside the terminal: window cycling, leaving it, Halt All.
RESERVED_KEYS = {
    *(f"f{i}" for i in range(1, 11)),
    "shift+f9",
    "f12",
    "ctrl+p",
}

_SPECIAL = {
    "enter": "\r", "tab": "\t", "shift+tab": "\x1b[Z", "escape": "\x1b", "backspace": "\x7f",
    "up": "\x1b[A", "down": "\x1b[B", "right": "\x1b[C", "left": "\x1b[D",
    "home": "\x1b[H", "end": "\x1b[F", "pageup": "\x1b[5~", "pagedown": "\x1b[6~",
    "insert": "\x1b[2~", "delete": "\x1b[3~",
    "f1": "\x1bOP", "f2": "\x1bOQ", "f3": "\x1bOR", "f4": "\x1bOS", "f5": "\x1b[15~",
    "f7": "\x1b[18~", "f8": "\x1b[19~", "f9": "\x1b[20~", "f10": "\x1b[21~", "f11": "\x1b[23~",
    "shift+up": "\x1b[1;2A", "shift+down": "\x1b[1;2B", "shift+right": "\x1b[1;2C", "shift+left": "\x1b[1;2D",
    "ctrl+up": "\x1b[1;5A", "ctrl+down": "\x1b[1;5B", "ctrl+right": "\x1b[1;5C", "ctrl+left": "\x1b[1;5D",
    "ctrl+space": "\x00", "ctrl+@": "\x00",
}
_PYTE_COLORS = {
    "black", "red", "green", "yellow", "blue", "magenta", "cyan", "white",
}


def key_to_bytes(event: events.Key) -> bytes | None:
    """Translate a Textual key event to what a terminal would send."""
    key = event.key
    if key in _SPECIAL:
        return _SPECIAL[key].encode()
    if key.startswith("ctrl+") and len(key) == 6 and key[5].isalpha():
        return bytes([ord(key[5].lower()) - 96])
    if key.startswith("alt+") and event.character:
        return b"\x1b" + event.character.encode()
    if event.character and event.is_printable:
        return event.character.encode()
    if event.character and len(event.character) == 1 and ord(event.character) < 32:
        return event.character.encode()  # other control characters, passed as is
    return None


def _color(value: str) -> str | None:
    if value in ("default", ""):
        return None
    if value in _PYTE_COLORS:
        return value
    if value.startswith("bright"):
        base = value[6:].lstrip("_")
        return f"bright_{base}" if base in _PYTE_COLORS else None
    if len(value) == 6:
        try:
            int(value, 16)
            return f"#{value}"
        except ValueError:
            return None
    return None


class Terminal(Widget, can_focus=True):
    """Runs `command` on a PTY. Posts `Terminal.Exited` when the process ends."""

    DEFAULT_CLASSES = "-as-written"          # what the program prints stays as printed, in any mode

    DEFAULT_CSS = """
    Terminal {
        width: 100%;
        height: 100%;
        background: $background;
    }
    Terminal:focus {
        background: $background;
    }
    """

    class Exited(Message):
        def __init__(self, terminal: Terminal, code: int | None) -> None:
            super().__init__()
            self.terminal = terminal
            self.code = code

    def __init__(
        self,
        command: list[str],
        *,
        cwd: str | None = None,
        env: dict[str, str] | None = None,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        super().__init__(name=name, id=id, classes=classes)
        self.command = command
        self.cwd = cwd
        self.extra_env = env or {}
        self.key = ""                         # the session's key in the War Tent (ChatView sets it)
        self.harness, self.title = "claude", ""
        self.session = None                   # core.sessions.Session, once opened
        self._placeholder = pyte.Screen(80, 24)

    # -- the session --------------------------------------------------------------------

    @property
    def screen_(self) -> pyte.Screen:
        return self.session.screen if self.session is not None else self._placeholder

    @property
    def running(self) -> bool:
        return self.session is not None and self.session.running

    @property
    def exit_code(self) -> int | None:
        return self.session.exit_code if self.session is not None else None

    @property
    def last_output(self) -> float:
        return self.session.last_output if self.session is not None else time.monotonic()

    @property
    def pid(self) -> int | None:
        return self.session.pid if self.session is not None else None

    def _sessions(self):
        return getattr(self.app, "tent", None)

    def on_mount(self) -> None:
        self.call_after_refresh(self.start)

    def start(self) -> None:
        if self.session is not None:
            return
        tent = self._sessions()
        if tent is None:
            return
        cols, rows = max(self.size.width, 20), max(self.size.height, 5)
        key = self.key or self.id or f"term:{id(self)}"
        ork = self.extra_env.get("ORKCRAFT_ORC", "")
        self.session = tent.open(key, self.command, self.harness, self.title, env=self.extra_env,
                                 ork=ork, cwd=self.cwd, size=(cols, rows))
        self.refresh()

    def output(self) -> None:
        """The session printed something: draw it again."""
        self.refresh()

    def finished(self, code: int | None) -> None:
        """The session ended."""
        self.refresh()
        self.post_message(self.Exited(self, code))

    def write(self, data: bytes) -> None:
        tent = self._sessions()
        if tent is not None and self.session is not None:
            tent.write(self.session.key, data)

    def interrupt(self) -> bool:
        """Ctrl+C for the CLI: cancels its current turn / tool call, keeps the session."""
        tent = self._sessions()
        return bool(tent is not None and self.session is not None and tent.interrupt(self.session.key))

    def stop(self) -> None:
        tent = self._sessions()
        if tent is not None and self.session is not None:
            tent.stop(self.session.key)

    def on_unmount(self) -> None:
        self.stop()

    # -- input ---------------------------------------------------------------------------

    def check_consume_key(self, key: str, character: str | None) -> bool:
        # Claim every key but the reserved ones, so orkcraft's bindings (q, n, digits,
        # ctrl+c …) never fire while typing to the CLI.
        return key not in RESERVED_KEYS

    def on_key(self, event: events.Key) -> None:
        if event.key in RESERVED_KEYS:
            return  # bubble to orkcraft (window cycling, leaving the terminal)
        data = key_to_bytes(event)
        if data is not None:
            self.write(data)
        event.stop()
        event.prevent_default()

    def on_paste(self, event: events.Paste) -> None:
        # Bracketed paste so multi-line text arrives as one prompt.
        self.write(b"\x1b[200~" + event.text.encode() + b"\x1b[201~")
        event.stop()

    def on_resize(self, event: events.Resize) -> None:
        tent = self._sessions()
        if tent is not None and self.session is not None:
            tent.resize(self.session.key, event.size.width, event.size.height)

    # -- rendering ------------------------------------------------------------------------

    def get_content_height(self, container: Size, viewport: Size, width: int) -> int:
        return container.height

    def render_line(self, y: int) -> Strip:
        if self.session is not None:            # the core's reader thread feeds this screen
            with self.session.lock:
                return self._render_line(y)
        return self._render_line(y)

    def _render_line(self, y: int) -> Strip:
        screen = self.screen_
        if y >= screen.lines:
            return Strip.blank(self.size.width)
        row = screen.buffer[y]
        cursor_here = self.has_focus and not screen.cursor.hidden and y == screen.cursor.y
        segments: list[Segment] = []
        text, style = "", None
        for x in range(min(screen.columns, self.size.width)):
            ch = row[x]
            reverse = ch.reverse != (cursor_here and x == screen.cursor.x)
            st = Style(
                color=_color(ch.fg), bgcolor=_color(ch.bg), bold=ch.bold, italic=ch.italics,
                underline=ch.underscore, strike=ch.strikethrough, reverse=reverse,
            )
            if st != style and text:
                segments.append(Segment(text, style))
                text = ""
            style = st
            text += ch.data or " "
        if text:
            segments.append(Segment(text, style))
        return Strip(segments, self.size.width)

    def text_lines(self) -> list[str]:
        """Plain screen contents (tests, debugging)."""
        if self.session is not None:
            return self.session.text_lines()
        return [line.rstrip() for line in self._placeholder.display]
