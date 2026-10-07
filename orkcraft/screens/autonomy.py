"""🏛 How much the orks do on their own: a slider of three stops and the guide for the agents' settings.

    AutonomyStep(level, tools, standalone=False, wait=7, rebuild=12)   F10 → 🏛 Ork autonomy
        dismisses {"autonomy": n, "autonomy_wait": minutes, "rebuild_wait": hours}, "back", "skip" or None
    AutonomyStep(level, tools, look=machine)       onboarding's camp rules: the quiet hours below the
        slider; dismisses {"autonomy", "autonomy_wait", "rebuild_wait", "quiet"}

The stops are autonomy.LEVELS: ⛓️ chains — decisions wait for the operator, the Elders only advise in
quiet hours; 🕰 on the clock — a question waits the minutes, a change the hours the operator is around
picked under the slider, then the orks decide; ⛓️‍💥 unchained
orks — at once. From ⏳ the guide shows what to paste into Claude Code's settings and how to start
agy and Codex (the snippet can be copied here).
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
from textual.widgets import Button, Checkbox, Label, RadioButton, Static

from orkcraft import autonomy, schedule, settings
from orkcraft.screens.build_flow import MODAL_CSS

TRACK = 60                         # cells between the first and the last stop
STOPS = [round(i * TRACK / (len(autonomy.LEVELS) - 1)) for i in range(len(autonomy.LEVELS))]
TRACK_COLOR = "#c99a3e"
WAITS = autonomy.QUESTION_WAITS            # 🕰 a question: the minutes to pick from
REBUILDS = autonomy.REBUILD_WAITS          # 🕰 a change: the hours to pick from


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
                Binding("g", "copy('agy')", "Copy the agy command"), Binding("o", "copy('codex')", "Copy the Codex command")]
    TOOLS = {"claude": ("Claude Code", "#au-claude", "au-copy"), "agy": ("Antigravity", "#au-agy", "au-copy-agy"),
             "codex": ("Codex", "#au-codex", "au-copy-codex")}            # name, its line, its 📋
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
    AutonomyStep #au-wait, AutonomyStep #au-rebuild { height: auto; margin-top: 0; }
    AutonomyStep #au-rebuild RadioButton { width: auto; height: 1; border: none; padding: 0; margin-right: 3;
                                           background: transparent; }
    AutonomyStep #au-wait RadioButton { width: auto; height: 1; border: none; padding: 0; margin-right: 3;
                                        background: transparent; }
    AutonomyStep #au-wait RadioButton:focus { text-style: bold; border: none; }
    AutonomyStep #au-quiet { height: 1; border: none; padding: 0; background: transparent; margin-top: 1; }
    AutonomyStep .ob-buttons { height: auto; margin-top: 1; align-horizontal: right; }
    AutonomyStep .ob-buttons Button { margin-left: 1; }
    """

    def __init__(self, level: int = autonomy.DEFAULT_LEVEL, tools: tuple[str, ...] = ("claude", "agy"),
                 standalone: bool = False, step: str = "", look: settings.MachineSettings | None = None,
                 wait: int | None = None, rebuild: int | None = None) -> None:
        super().__init__()
        self.level = level
        self.wait = autonomy.wait_of(wait if wait is not None else look.autonomy_wait if look is not None else None)
        self.rebuild = autonomy.rebuild_of(rebuild if rebuild is not None else look.rebuild_wait if look is not None
                                           else None)
        self.tools = tools
        self.standalone = standalone
        self.step = step
        self.look = look                  # the camp rules of onboarding: the quiet hours too

    def compose(self) -> ComposeResult:
        with Vertical():
            title = ("🏛 Ork autonomy — how much they do on their own" if self.standalone
                     else "🧭 Camp rules — how free the orks are, when they keep quiet" if self.look is not None
                     else "🧭 How much should your orks do on their own?")
            yield Label(f"{title}  ·  {self.step}" if self.step else title, classes="build-title")
            with Horizontal(id="au-row"):
                yield AutonomySlider(self.level, id="au-slider")
            yield Static("", id="au-level")
            with Horizontal(id="au-wait"):
                yield Label("a question waits ")
                for m in WAITS:
                    yield RadioButton(f"{m} min", value=self.wait == m, id=f"au-wait-{m}")
            with Horizontal(id="au-rebuild"):
                yield Label("a change waits   ")
                for h in REBUILDS:
                    yield RadioButton(f"{h} h", value=self.rebuild == h, id=f"au-rebuild-{h}")
            with Vertical(id="au-guide-box"):
                yield Label("The agents' own settings", classes="au-head")
                if "claude" in self.tools:
                    with Horizontal(classes="au-tool"):
                        yield CopyIcon("au-copy")
                        yield Static("", id="au-claude-gap", classes="au-gap")
                        yield Static("", id="au-claude", classes="au-line", markup=False)
                for tool in ("agy", "codex"):
                    if tool in self.tools:
                        with Horizontal(classes="au-tool"):
                            yield CopyIcon(f"au-copy-{tool}")
                            yield Static("", id=f"au-{tool}-gap", classes="au-gap")
                            yield Static("", id=f"au-{tool}", classes="au-line", markup=False)
            if self.look is not None:
                yield Checkbox(f"🌙 Quiet hours {schedule.DEFAULT_QUIET.label()} — no fires, only ❓",
                               value=self.look.quiet is not None, id="au-quiet")
            yield Static("←/→ or a click moves the slider · 📋 or c / g / o copies · you can change it at any time: F10"
                         + (" (the hours: 🕰 Your day)." if self.look is not None else "."), classes="build-hint")
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

    def pick_rebuild(self, hours: int) -> None:
        self.rebuild = hours
        for b in self.query("#au-rebuild RadioButton").results(RadioButton):
            on_ = b.id == f"au-rebuild-{hours}"
            if b.value != on_:
                with b.prevent(RadioButton.Changed):
                    b.value = on_

    def pick_wait(self, minutes: int) -> None:
        self.wait = minutes
        for b in self.query("#au-wait RadioButton").results(RadioButton):
            on_ = b.id == f"au-wait-{minutes}"
            if b.value != on_:
                with b.prevent(RadioButton.Changed):
                    b.value = on_

    @on(RadioButton.Changed)
    def _picked(self, event: RadioButton.Changed) -> None:
        event.stop()
        bid = event.radio_button.id or ""
        if bid.startswith("au-wait-"):
            self.pick_wait(int(bid.removeprefix("au-wait-")) if event.value else self.wait)
            return
        if bid.startswith("au-rebuild-"):
            self.pick_rebuild(int(bid.removeprefix("au-rebuild-")) if event.value else self.rebuild)

    def result(self) -> dict:
        out: dict = {"autonomy": self.level, "autonomy_wait": self.wait, "rebuild_wait": self.rebuild}
        if self.look is not None:
            out["quiet"] = schedule.DEFAULT_QUIET if self.query_one("#au-quiet", Checkbox).value else None
        return out

    def show(self) -> None:
        lvl = autonomy.LEVELS[self.level]
        t = Text()
        t.append(f"{lvl.icon} {lvl.title}\n", style="bold")
        t.append("❓ Questions: ", style="bold")
        t.append(lvl.questions + "\n")
        t.append("🔧 Improvements: ", style="bold")
        t.append(lvl.improves)
        self.query_one("#au-wait").display = self.query_one("#au-rebuild").display = self.level == autonomy.CLOCK
        if self.level >= autonomy.CLOCK:
            t.append("\n   Each goes through ", style="dim")
            t.append(autonomy.SAFEGUARDS, style="dim")
        self.query_one("#au-level", Static).update(t)
        lines = {"claude": autonomy.claude_line, "agy": autonomy.agy_line, "codex": autonomy.codex_line}
        for tool, (name, wid, copy_id) in self.TOOLS.items():
            can = bool(self.copy_text(tool))
            for w in self.query(wid).results(Static):
                w.update(Text.assemble((f"{name}: ", "bold"), lines[tool](self.level)))
            for b in self.query(f"#{copy_id}"):
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
        self.action_copy(next((t for t, (_, _, c) in self.TOOLS.items() if c == event.icon.id), "claude"))

    def copy_text(self, tool: str) -> str:
        """The Claude Code permissions, or the command that starts agy / Codex, for this level."""
        return {"claude": autonomy.claude_snippet, "agy": autonomy.agy_command,
                "codex": autonomy.codex_command}[tool](self.level)

    def action_copy(self, tool: str) -> None:
        """📋 The Claude Code permissions, or the agy / Codex command, for this level onto the clipboard."""
        text = self.copy_text(tool)
        if not text or tool not in self.tools:
            return
        self.app.copy_to_clipboard(text)
        self.copied = text
        self.notify(f"paste it into {autonomy.CLAUDE_FILE} or {autonomy.CLAUDE_FILE_ALL}" if tool == "claude"
                    else f"start {self.TOOLS[tool][0]} with it", title="📋 Copied")

    def action_back(self) -> None:
        self.dismiss(None if self.standalone else "back")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        event.stop()
        bid = event.button.id
        if bid in ("au-next", "au-save"):
            self.dismiss(self.result())
        elif bid == "au-skip":
            self.dismiss("skip")
        elif bid == "au-back":
            self.dismiss("back")
        else:
            self.dismiss(None)
