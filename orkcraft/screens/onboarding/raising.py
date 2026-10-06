"""🧭 Onboarding, raising the town over the map with a progress bar along the bottom."""
from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widget import Widget
from textual.widgets import ProgressBar, Static

from orkcraft.screens.onboarding.common import CUSTOM


class RaiseBar(Horizontal):
    """The progress of raising the town, along the bottom of the map."""

    DEFAULT_CSS = """
    RaiseBar {
        dock: bottom;
        height: 3;
        width: 100%;
        background: $panel;
        border-top: solid $accent;
        padding: 0 2;
        layer: overlay;
    }
    RaiseBar #raise-label { width: 1fr; padding-top: 0; }
    RaiseBar ProgressBar { width: 40; }
    """

    def __init__(self, total: int | None) -> None:     # None: it runs until told (the Town Builder thinking)
        super().__init__(id="raise-bar")
        self.total = total
        self.label = "🏗 Raising the town…"
        self.done = 0

    def compose(self) -> ComposeResult:
        yield Static(self.label, id="raise-label", markup=False)
        yield ProgressBar(total=self.total, show_eta=False, id="raise-progress")

    def on_mount(self) -> None:
        self._show()

    def say(self, label: str) -> None:
        self.label = label
        self._show()

    def step(self, label: str, done: int) -> None:
        self.label, self.done = f"🏗 {label}", done
        self._show()

    def _show(self) -> None:
        """Safe before the bar's children are in (mounted from the same handler)."""
        for w in self.query("#raise-label").results(Static):
            w.update(self.label)
        for bar in self.query("#raise-progress").results(ProgressBar):
            if self.total is not None:
                bar.update(progress=self.done)


def raising_steps(choice: dict) -> list[str]:
    """What raising the town does, in order — each a real piece of work. An intent's buildings and
    the Town Builder's plan are raised after it, on their own bar."""
    steps = ["Opening the camp's records"]
    if choice.get("warder"):
        steps.append("Installing the 🛡 Warder")
    if choice.get("preset") == CUSTOM:
        steps.append("Leaving your order in the Town Hall")
    return steps



def mount_raise_bar(screen: Widget, total: int | None) -> RaiseBar:
    bar = RaiseBar(total)
    screen.mount(bar)
    return bar
