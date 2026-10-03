"""System menu [F10], keybindings cheat sheet, quit confirmation, and key table."""
from __future__ import annotations

from rich.console import Group
from rich.table import Table
from rich.text import Text
from textual import events
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, OptionList, Static
from textual.widgets.option_list import Option


MENU_ITEMS: list[tuple[str, str]] = [
    ("war_horn", "📯 Halt All Operations (War Horn)"),
    ("screenshot", "📸 Capture Screenshot (SVG → ./loot/screenshots/)"),
    ("keys", "⌨️ Keybindings Cheat Sheet"),
    ("immersion", "🎭 Immersion mode — ASCII town, orcs, fire, gold and lumber"),
    ("hidden", "🕶 Hidden mode (office) — frames, people, ❓, words"),
    ("terrain", "🌲 Toggle Terrain (Dim / Black)"),
    ("save", "💾 Save Town Scroll (.orkcraft.json)"),
    ("audit", "🔍 Audit the camp (security, usability, spend)"),
    ("cleanup", "🧹 Clean up — logs, gone buildings, stale worktrees, daemons"),
    ("improve", "🔧 Self-improvement — proposals for the camp"),
    ("weekly", "🗓 Weekly self-audit — the last report, or run it now"),
    ("settings", "⚙ Self-improvement settings — models and schedules"),
    ("quit", "🚪 Quit Orkcraft"),
]

KEY_GROUPS: list[tuple[str, list[tuple[str, str]]]] = [
    (
        "Orkspaces",
        [
            ("F1–F8", "Switch orkspace canvas"),
            ("N", "New orkspace"),
            ("d", "Delete empty orkspace (on War Map)"),
        ],
    ),
    (
        "Buildings & windows",
        [
            ("1–9 · alt+1–9", "Focus building N (press again for orders)"),
            ("F9 / shift+F9", "Cycle active window"),
            ("alt+hjkl / alt+←↑↓→", "Move window"),
            ("alt+⇧+hjkl / ←↑↓→", "Resize window"),
            ("alt+b", "📌 Pin / unpin window"),
            ("ctrl+w", "Window mode (snap, max, tile, demolish)"),
            ("ctrl+b", "Toggle RTS Console"),
            ("alt+- · alt+=", "Console smaller / taller (or drag its top edge)"),
            ("mouse", "Drag title, resize corner ◢, click badge"),
        ],
    ),
    (
        "Focus",
        [
            ("Esc / empty canvas", "Neutral mode / deselect"),
            ("Tab / shift+Tab", "Cycle windows (Minimal mode)"),
        ],
    ),
    (
        "Command Card — Neutral",
        [
            ("B", "🏗️ Build window (Mason & Artisan)"),
            ("P", "📜 Window presets catalog"),
            ("S", "🧌 Summon orc / warband"),
            ("T", "🌲 Toggle terrain (Dim / Black)"),
            ("G", "⎇ Worktree of the active orkspace"),
        ],
    ),
    (
        "Command Card — Building",
        [
            ("R", "Recruit orc: describe it (Recruiter) or by hand"),
            ("L", "📜 Building chronicles"),
            ("Y", "🛤 Listen to another window (road into this one)"),
            ("U", "🚧 Remove the incoming road"),
            ("P", "📌 Pin / unpin window"),
            ("M", "Window mode"),
            ("X", "Demolish window"),
            ("Z", "Revert building to its previous checkpoint"),
            ("K", "👍 Its last result is good (a reference)"),
            ("F", "👎 Its last result is bad: broken inputs or its logic"),
        ],
    ),
    (
        "Roads (click a road or a gate)",
        [
            ("H", "🔀 Handler of the selected road"),
            ("U", "🚧 Remove the selected road"),
            ("Esc", "Back to the building"),
            ("alt+c", "🛒 Carts: off / selected building / all"),
            ("alt+v", "🏘 View: town (huts, one building open) / tiles"),
        ],
    ),
    (
        "Command Card — Unit",
        [
            ("C", "Deploy / Chat / Orders"),
            ("T", "⚡ Triggers & orders"),
            ("D", "Dismiss orc from garrison"),
            ("H", "🛑 Halt running session"),
            ("L", "📜 Unit chronicles"),
            ("W", "🔎 Steward: watch now, proposals"),
            ("Enter", "❓ Resolve alert (orders)"),
        ],
    ),
    (
        "Chronicles overlay",
        [
            ("Enter", "Expand step details"),
            ("D", "Send diff to Scrying Spire"),
            ("R", "Resume run in War Tent"),
        ],
    ),
    (
        "Operations",
        [
            ("space / ctrl+p", "📯 War Horn (halt all operations)"),
            ("alt+t", "🌲 Toggle terrain (Dim / Black)"),
            ("F10", "⚙️ System menu"),
            ("?", "⌨️ This cheat sheet"),
            ("+", "Spawn orc (new Claude session in War Tent)"),
            ("!", "Answer the next 🔥 (an orc waiting for orders)"),
            ("F12", "Leave terminal (back to session list)"),
        ],
    ),
    (
        "General",
        [
            ("r", "Reload the buildings' data"),
            ("u", "Reload limits"),
            ("o", "Open a session in War Tent"),
            ("ctrl+k", "Command palette"),
            ("q", "Quit Orkcraft (graceful)"),
        ],
    ),
]


def _format_column(groups: list[tuple[str, list[tuple[str, str]]]]) -> Group:
    """One column of the cheat sheet: a grid per group, so a long description wraps inside its
    own column instead of under the keys."""
    parts: list = []
    for idx, (title, rows) in enumerate(groups):
        if idx > 0:
            parts.append(Text(""))
        parts.append(Text(f"── {title} ──", style="bold yellow"))
        grid = Table.grid(padding=(0, 1))
        grid.add_column(style="bold cyan", no_wrap=True)
        grid.add_column(overflow="fold")
        for key, desc in rows:
            grid.add_row(Text(key), Text(desc))
        parts.append(grid)
    return Group(*parts)


class SystemMenu(ModalScreen[str | None]):
    """System menu modal [F10]."""

    DEFAULT_CSS = """
    SystemMenu {
        align: center middle;
    }
    #system-menu-dialog {
        width: 64;
        height: auto;
        border: thick $accent;
        background: $surface;
        padding: 1 2;
    }
    #system-menu-title {
        text-style: bold;
        color: $accent;
        padding-bottom: 1;
        text-align: center;
        width: 100%;
    }
    #system-menu-list {
        height: auto;
        max-height: 10;
        background: transparent;
        border: none;
    }
    #system-menu-footer {
        color: $text-muted;
        text-align: center;
        padding-top: 1;
        width: 100%;
    }
    """

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
        Binding("f10", "cancel", "Close", priority=True),
        Binding("1", "pick('war_horn')", show=False),
        Binding("2", "pick('screenshot')", show=False),
        Binding("3", "pick('keys')", show=False),
        Binding("4", "pick('immersion')", show=False),
        Binding("5", "pick('hidden')", show=False),
        Binding("6", "pick('terrain')", show=False),
        Binding("7", "pick('save')", show=False),
    ]

    def __init__(self, plain: bool = False) -> None:
        super().__init__()
        self.plain = plain          # which of the two modes is on (marked ●)

    def compose(self) -> ComposeResult:
        with Vertical(id="system-menu-dialog"):
            yield Static("⚙️ SYSTEM & CLAN OPERATIONS", id="system-menu-title", markup=False)
            yield OptionList(id="system-menu-list")
            yield Static("[1-9] action · [Esc] cancel", id="system-menu-footer", markup=False)

    def on_mount(self) -> None:
        lst = self.query_one("#system-menu-list", OptionList)
        lst.clear_options()
        for i, (action_id, label) in enumerate(MENU_ITEMS, 1):
            on = (action_id == "hidden") == self.plain if action_id in ("immersion", "hidden") else False
            lst.add_option(Option(Text(f"[{i}] {label}" + ("  ●" if on else "")), id=action_id))
        lst.focus()

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        event.stop()
        self.dismiss(event.option_id)

    def on_key(self, event: events.Key) -> None:
        if event.key in tuple("123456789"):
            idx = int(event.key) - 1
            if 0 <= idx < len(MENU_ITEMS):
                event.stop()
                event.prevent_default()
                self.dismiss(MENU_ITEMS[idx][0])
        elif event.key in ("escape", "f10"):
            event.stop()
            event.prevent_default()
            self.dismiss(None)

    def action_cancel(self) -> None:
        self.dismiss(None)

    def action_pick(self, action_id: str) -> None:
        self.dismiss(action_id)


class KeysCheatSheet(ModalScreen[None]):
    """Keybindings cheat sheet modal displayed in two columns."""

    DEFAULT_CSS = """
    KeysCheatSheet {
        align: center middle;
    }
    #cheat-sheet-dialog {
        width: 104;
        max-width: 95%;
        height: 85%;
        border: thick $accent;
        background: $surface;
        padding: 1 2;
    }
    #cheat-sheet-title {
        text-style: bold;
        color: $accent;
        padding-bottom: 1;
        text-align: center;
        width: 100%;
    }
    #cheat-sheet-scroll {
        height: 1fr;
    }
    #cheat-sheet-columns {
        height: auto;
    }
    .cheat-sheet-col {
        width: 1fr;
        height: auto;
        padding: 0 1;
    }
    #cheat-sheet-footer {
        color: $text-muted;
        text-align: center;
        padding-top: 1;
        width: 100%;
    }
    """

    BINDINGS = [
        Binding("escape", "dismiss_sheet", "Close"),
        Binding("q", "dismiss_sheet", "Close"),
        Binding("question_mark", "dismiss_sheet", "Close"),
    ]

    def compose(self) -> ComposeResult:
        mid = 5
        col1_groups = KEY_GROUPS[:mid]
        col2_groups = KEY_GROUPS[mid:]
        with Vertical(id="cheat-sheet-dialog"):
            yield Static("─── ⌨️ KEYBINDINGS CHEAT SHEET ───", id="cheat-sheet-title", markup=False)
            with VerticalScroll(id="cheat-sheet-scroll"):
                with Horizontal(id="cheat-sheet-columns"):
                    yield Static(_format_column(col1_groups), id="cheat-sheet-col1", classes="cheat-sheet-col")
                    yield Static(_format_column(col2_groups), id="cheat-sheet-col2", classes="cheat-sheet-col")
            yield Static("[Esc] / [q] / [?] Close", id="cheat-sheet-footer", markup=False)

    def on_mount(self) -> None:
        self.query_one("#cheat-sheet-scroll", VerticalScroll).focus()

    def on_key(self, event: events.Key) -> None:
        if event.key in ("escape", "q", "question_mark"):
            event.stop()
            event.prevent_default()
            self.dismiss(None)

    def action_dismiss_sheet(self) -> None:
        self.dismiss(None)

    @property
    def text(self) -> str:
        lines: list[str] = []
        for title, rows in KEY_GROUPS:
            lines.append(f"── {title} ──")
            for k, d in rows:
                lines.append(f"{k}  {d}")
        return "\n".join(lines)

    def __str__(self) -> str:
        return self.text


class QuitConfirm(ModalScreen[bool]):
    """Confirmation modal for quitting with active sessions."""

    DEFAULT_CSS = """
    QuitConfirm {
        align: center middle;
    }
    #quit-dialog {
        width: 62;
        height: auto;
        border: thick $accent;
        background: $surface;
        padding: 1 2;
    }
    #quit-title {
        text-style: bold;
        color: $accent;
        padding-bottom: 1;
        text-align: center;
        width: 100%;
    }
    #quit-message {
        padding: 1 0;
        text-align: center;
        width: 100%;
    }
    #quit-buttons {
        width: 100%;
        height: auto;
        align-horizontal: center;
        padding-top: 1;
    }
    #quit-buttons > Button {
        margin: 0 1;
    }
    """

    BINDINGS = [
        Binding("y", "confirm", "Quit"),
        Binding("Y", "confirm", "Quit"),
        Binding("n", "cancel", "Stay"),
        Binding("N", "cancel", "Stay"),
        Binding("escape", "cancel", "Stay"),
    ]

    def __init__(self, running_count: int) -> None:
        super().__init__()
        self.running_count = running_count

    def compose(self) -> ComposeResult:
        with Vertical(id="quit-dialog"):
            yield Static("─── 🚪 QUIT ORKCRAFT ───", id="quit-title", markup=False)
            msg = f"🚪 {self.running_count} running session(s) will be stopped — quit?"
            yield Static(msg, id="quit-message", markup=False)
            with Horizontal(id="quit-buttons"):
                yield Button(Text("[Y] Quit"), variant="error", id="btn-quit")
                yield Button(Text("[N] Stay"), variant="default", id="btn-stay")

    def on_mount(self) -> None:
        self.query_one("#btn-stay", Button).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        event.stop()
        if event.button.id == "btn-quit":
            self.dismiss(True)
        else:
            self.dismiss(False)

    def on_key(self, event: events.Key) -> None:
        if event.key in ("y", "Y"):
            event.stop()
            event.prevent_default()
            self.dismiss(True)
        elif event.key in ("n", "N", "escape"):
            event.stop()
            event.prevent_default()
            self.dismiss(False)

    def action_confirm(self) -> None:
        self.dismiss(True)

    def action_cancel(self) -> None:
        self.dismiss(False)
