"""A terminal inside a Textual widget: a child process on a PTY, rendered with pyte.

Every key goes to the process — Claude Code's and agy's own TUIs (polls, buttons,
`/model`, `/goal`, …) work as in a real terminal — except the keys in
`RESERVED_KEYS`, which stay with orkcraft so focus can leave the terminal.
"""
from __future__ import annotations

import asyncio
import fcntl
import os
import pty
import signal
import struct
import termios
import time

import pyte
from rich.segment import Segment
from rich.style import Style
from textual import events
from textual.geometry import Size
from textual.message import Message
from textual.strip import Strip
from textual.widget import Widget

# Stay with orkcraft even inside the terminal: window cycling, leaving it, the War Horn.
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
        self.screen_ = pyte.Screen(80, 24)
        self.stream = pyte.ByteStream(self.screen_)
        self.pid: int | None = None
        self.fd: int | None = None
        self.exit_code: int | None = None
        self.running = False
        self.last_output = time.monotonic()

    # -- process ------------------------------------------------------------------------

    def on_mount(self) -> None:
        self.call_after_refresh(self.start)

    def start(self) -> None:
        if self.pid is not None:
            return
        cols, rows = max(self.size.width, 20), max(self.size.height, 5)
        self.screen_.resize(rows, cols)
        env = {**os.environ, "TERM": "xterm-256color", "COLORTERM": "truecolor", **self.extra_env}
        pid, fd = pty.fork()
        if pid == 0:  # child
            try:
                if self.cwd:
                    os.chdir(self.cwd)
                os.execvpe(self.command[0], self.command, env)
            except Exception as e:  # exec failed: show why, then leave
                os.write(2, f"orkcraft: cannot run {self.command[0]}: {e}\r\n".encode())
            os._exit(127)
        self.pid, self.fd = pid, fd
        self.running = True
        self._set_winsize(rows, cols)
        os.set_blocking(fd, False)
        asyncio.get_running_loop().add_reader(fd, self._on_readable)

    def _set_winsize(self, rows: int, cols: int) -> None:
        if self.fd is not None:
            try:
                fcntl.ioctl(self.fd, termios.TIOCSWINSZ, struct.pack("HHHH", rows, cols, 0, 0))
            except OSError:
                pass

    def _on_readable(self) -> None:
        assert self.fd is not None
        try:
            data = os.read(self.fd, 65536)
        except BlockingIOError:
            return
        except OSError:
            data = b""
        if not data:
            self._finish()
            return
        self.stream.feed(data)
        self.last_output = time.monotonic()
        self.refresh()

    def _finish(self) -> None:
        if not self.running:
            return
        self.running = False
        if self.fd is not None:
            try:
                asyncio.get_running_loop().remove_reader(self.fd)
            except Exception:
                pass
            try:
                os.close(self.fd)
            except OSError:
                pass
        code = None
        if self.pid is not None:
            # EOF usually means the child is gone; never block the UI waiting for it.
            for _ in range(20):
                try:
                    pid, status = os.waitpid(self.pid, os.WNOHANG)
                except ChildProcessError:
                    break
                if pid:
                    code = os.waitstatus_to_exitcode(status)
                    break
                time.sleep(0.01)
        self.exit_code = code
        self.stream.feed(f"\r\n\x1b[2m[process exited{'' if code is None else f' with {code}'}]\x1b[0m".encode())
        self.refresh()
        self.post_message(self.Exited(self, code))

    def write(self, data: bytes) -> None:
        if self.running and self.fd is not None:
            try:
                os.write(self.fd, data)
            except OSError:
                pass

    def interrupt(self) -> bool:
        """Ctrl+C for the CLI: cancels its current turn / tool call, keeps the session."""
        if self.running and self.pid is not None:
            try:
                os.kill(self.pid, signal.SIGINT)
                return True
            except ProcessLookupError:
                pass
        return False

    def stop(self) -> None:
        if self.running and self.pid is not None:
            try:
                os.kill(self.pid, signal.SIGHUP)
            except ProcessLookupError:
                pass
            self._finish()

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
        cols, rows = max(event.size.width, 20), max(event.size.height, 5)
        if (rows, cols) != (self.screen_.lines, self.screen_.columns):
            self.screen_.resize(rows, cols)
            self._set_winsize(rows, cols)
            if self.pid is not None and self.running:
                try:
                    os.kill(self.pid, signal.SIGWINCH)
                except ProcessLookupError:
                    pass

    # -- rendering ------------------------------------------------------------------------

    def get_content_height(self, container: Size, viewport: Size, width: int) -> int:
        return container.height

    def render_line(self, y: int) -> Strip:
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
        return [line.rstrip() for line in self.screen_.display]
