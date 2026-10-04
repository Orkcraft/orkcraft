"""🏛 How much the orcs do on their own: a slider of four stops and the guide for the agents' settings.

    AutonomyStep(level, tools, standalone=False)   onboarding step 2, and F10 → 🏛 Orc autonomy
        dismisses {"autonomy": n}, "back", "skip" or None

The stops are autonomy.LEVELS. At 0 nothing is judged; from 1 the Elders leave advice in quiet hours;
from 2 the guide shows what to paste into Claude Code's settings and how to start agy (the snippet
can be copied here); at 3 the Elders also answer routine questions themselves in quiet hours.
"""
from __future__ import annotations

from rich.text import Text
from textual import events, on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.message import Message
from textual.screen import ModalScreen
from textual.widget import Widget
from textual.widgets import Button, Label, Static

from orkcraft import autonomy
from orkcraft.screens.build_flow import MODAL_CSS

TRACK = 60                         # cells between the first and the last stop
STOPS = [round(i * TRACK / (len(autonomy.LEVELS) - 1)) for i in range(len(autonomy.LEVELS))]
TRACK_COLOR = "#c99a3e"


class AutonomySlider(Widget, can_focus=True):
    DEFAULT_CSS = f"""
    AutonomySlider {{ height: 2; width: {TRACK + 4}; padding: 0 1; }}
    AutonomySlider:focus {{ background: $boost; }}
    """
    BINDINGS = [Binding("left", "move(-1)", "Less", show=False), Binding("right", "move(1)", "More", show=False)]

    class Changed(Message):
        def __init__(self, slider: AutonomySlider) -> None:
            super().__init__()
            self.slider = slider

    def __init__(self, level: int = autonomy.DEFAULT_LEVEL, id: str | None = None) -> None:
        super().__init__(id=id)
        self.level = level

    def render(self) -> Text:
        knob = STOPS[self.level]
        t = Text()
        for x in range(TRACK + 1):
            if x == knob:
                t.append("●", style=f"bold {TRACK_COLOR}")
            elif x in STOPS:
                t.append("◆" if x < knob else "◇", style=TRACK_COLOR if x < knob else "dim")
            else:
                t.append("━" if x < knob else "─", style=TRACK_COLOR if x < knob else "dim")
        t.append("\n")
        line = Text()
        at = 0
        for lvl, x in zip(autonomy.LEVELS, STOPS):
            start = max(0, min(x - 1, TRACK - 1))
            if start > at:
                line.append(" " * (start - at))
                at = start
            line.append(lvl.icon, style="bold" if lvl.n == self.level else "dim")
            at += 2
        t.append_text(line)
        return t

    def set_level(self, level: int) -> None:
        level = max(0, min(len(autonomy.LEVELS) - 1, level))
        if level != self.level:
            self.level = level
            self.refresh()
            self.post_message(self.Changed(self))

    def action_move(self, by: int) -> None:
        self.set_level(self.level + int(by))

    def on_click(self, event: events.Click) -> None:
        at = event.get_content_offset(self)
        if at is None:
            return
        self.focus()
        self.set_level(min(range(len(STOPS)), key=lambda i: abs(STOPS[i] - at.x)))


class CopyIcon(Static):
    """📋 that copies on a click (a Button is three rows tall; this one is one)."""

    class Pressed(Message):
        def __init__(self, icon: CopyIcon) -> None:
            super().__init__()
            self.icon = icon

    def __init__(self, id: str) -> None:
        super().__init__("📋", id=id, classes="au-copy")

    def on_click(self) -> None:
        self.post_message(self.Pressed(self))


class AutonomyStep(ModalScreen[dict | str | None]):
    BINDINGS = [Binding("escape", "back", "Back"), Binding("c", "copy('claude')", "Copy Claude settings"),
                Binding("g", "copy('agy')", "Copy the agy command")]
    DEFAULT_CSS = MODAL_CSS.format(cls="AutonomyStep", border_color="$accent", title_color="$accent") + """
    AutonomyStep > Vertical { width: 84; }
    AutonomyStep #au-row { height: auto; align-horizontal: center; margin-top: 1; }
    AutonomyStep #au-level { height: auto; margin-top: 1; }
    AutonomyStep #au-guide-box { height: auto; border: round $panel-lighten-2; padding: 0 1; margin-top: 1; }
    AutonomyStep .au-head { text-style: bold; color: $text-muted; }
    AutonomyStep .au-tool { height: auto; }
    AutonomyStep .au-line { width: 1fr; height: auto; padding-top: 0; }
    AutonomyStep .au-copy { width: 3; height: 1; margin: 0 1 0 0; }
    AutonomyStep .au-copy:hover { background: $boost; }
    AutonomyStep .au-gap { width: 4; height: 1; margin: 0 1 0 0; }
    AutonomyStep .ob-buttons { height: auto; margin-top: 1; align-horizontal: right; }
    AutonomyStep .ob-buttons Button { margin-left: 1; }
    """

    def __init__(self, level: int = autonomy.DEFAULT_LEVEL, tools: tuple[str, ...] = ("claude", "agy"),
                 standalone: bool = False, step: str = "step 2 of 4") -> None:
        super().__init__()
        self.level = level
        self.tools = tools
        self.standalone = standalone
        self.step = step

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label("🏛 Ork autonomy — how much they do on their own" if self.standalone
                        else f"🧭 How much should your orks do on their own?  ·  {self.step}", classes="build-title")
            with Horizontal(id="au-row"):
                yield AutonomySlider(self.level, id="au-slider")
            yield Static("", id="au-level")
            with Vertical(id="au-guide-box"):
                yield Label("The agents' own settings", classes="au-head")
                if "claude" in self.tools:
                    with Horizontal(classes="au-tool"):
                        yield CopyIcon("au-copy")
                        yield Static("", id="au-claude-gap", classes="au-gap")
                        yield Static("", id="au-claude", classes="au-line", markup=False)
                if "agy" in self.tools:
                    with Horizontal(classes="au-tool"):
                        yield CopyIcon("au-copy-agy")
                        yield Static("", id="au-agy-gap", classes="au-gap")
                        yield Static("", id="au-agy", classes="au-line", markup=False)
            yield Static("←/→ or a click moves the slider · 📋 or c / g copies · you can change it at any time: F10.",
                         classes="build-hint")
            with Horizontal(classes="ob-buttons"):
                if self.standalone:
                    yield Button("Cancel", id="au-cancel")
                    yield Button("Save", id="au-save", variant="success")
                else:
                    yield Button("← Back", id="au-back")
                    yield Button("Skip", id="au-skip")
                    yield Button("Next →", id="au-next", variant="primary")

    def on_mount(self) -> None:
        self.show()
        self.query_one(AutonomySlider).focus()

    def show(self) -> None:
        lvl = autonomy.LEVELS[self.level]
        t = Text()
        t.append(f"{lvl.icon} {lvl.title}\n", style="bold")
        t.append("❓ Questions: ", style="bold")
        t.append(lvl.questions + "\n")
        t.append("🔧 Improvements: ", style="bold")
        t.append(lvl.improves)
        if autonomy.LEVELS[self.level].n >= 2:
            t.append("\n   Each goes through ", style="dim")
            t.append(autonomy.SAFEGUARDS, style="dim")
        self.query_one("#au-level", Static).update(t)
        for wid, line, copy_id, can in (("#au-claude", autonomy.claude_line, "#au-copy",
                                         bool(autonomy.claude_snippet(self.level))),
                                        ("#au-agy", autonomy.agy_line, "#au-copy-agy",
                                         bool(autonomy.agy_command(self.level)))):
            for w in self.query(wid).results(Static):
                name = "Claude Code" if wid == "#au-claude" else "Antigravity"
                w.update(Text.assemble((f"{name}: ", "bold"), line(self.level)))
            for b in self.query(copy_id):
                b.display = can
            for gap in self.query(f"{wid}-gap"):                # the line keeps its place without a 📋
                gap.display = not can

    @on(AutonomySlider.Changed)
    def _moved(self, event: AutonomySlider.Changed) -> None:
        event.stop()
        self.level = event.slider.level
        self.show()

    @on(CopyIcon.Pressed)
    def _copy_icon(self, event: CopyIcon.Pressed) -> None:
        event.stop()
        self.action_copy("agy" if event.icon.id == "au-copy-agy" else "claude")

    def action_copy(self, tool: str) -> None:
        """📋 The Claude Code permissions, or the agy command, for this level onto the clipboard."""
        text = autonomy.claude_snippet(self.level) if tool == "claude" else autonomy.agy_command(self.level)
        if not text or tool not in self.tools:
            return
        self.app.copy_to_clipboard(text)
        self.copied = text
        self.notify(f"paste it into {autonomy.CLAUDE_FILE} or {autonomy.CLAUDE_FILE_ALL}" if tool == "claude"
                    else "start agy with it", title="📋 Copied")

    def action_back(self) -> None:
        self.dismiss(None if self.standalone else "back")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        event.stop()
        bid = event.button.id
        if bid in ("au-next", "au-save"):
            self.dismiss({"autonomy": self.level})
        elif bid == "au-skip":
            self.dismiss("skip")
        elif bid == "au-back":
            self.dismiss("back")
        else:
            self.dismiss(None)
