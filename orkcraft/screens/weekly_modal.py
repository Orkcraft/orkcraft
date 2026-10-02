"""🗓 The weekly self-audit's report: tick the items, Apply makes them.

Items the camp can apply come with a checkbox (ticked); advice and items that failed their check
are listed below with the reason. Dismisses the list of ticked item numbers, or None.
"""
from __future__ import annotations

from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Label, SelectionList, Static

from orkcraft.realm import weekly
from orkcraft.screens.build_flow import MODAL_CSS


def item_label(i: weekly.Item) -> str:
    where = f"{i.building} · " if i.building else ""
    return f"{i.title} — {where}{i.change}: {i.why}"[:150]


class WeeklyReportModal(ModalScreen[list[int] | None]):
    BINDINGS = [Binding("escape", "close", "Close"), Binding("ctrl+s", "apply", "Apply", priority=True)]
    DEFAULT_CSS = MODAL_CSS.format(cls="WeeklyReportModal", border_color="$accent", title_color="$accent") + """
    WeeklyReportModal > Vertical { width: 120; }
    WeeklyReportModal VerticalScroll { height: auto; max-height: 30; }
    WeeklyReportModal SelectionList { height: auto; max-height: 14; }
    """

    def __init__(self, report: weekly.Report) -> None:
        super().__init__()
        self.report = report

    def compose(self) -> ComposeResult:
        r = self.report
        cost = f" · ${r.cost_usd:.2f}" if r.cost_usd is not None else ""
        doable = [i for i in r.items if i.applicable and i.n not in r.applied]
        other = [i for i in r.items if not i.applicable]
        with Vertical():
            yield Label(f"🗓 Weekly self-audit · {r.ts[:16].replace('T', ' ')} · {r.model or 'model'}{cost}",
                        classes="build-title")
            with VerticalScroll():
                yield Static(Text(r.summary or "no summary"), classes="build-text")
                yield Label(f"To apply ({len(doable)}) — each a checkpoint, Z on the building takes it back",
                            classes="build-section")
                if doable:
                    yield SelectionList(*[(item_label(i), i.n, True) for i in doable], id="weekly-items")
                else:
                    yield Static(Text("nothing to apply", style="dim"))
                if other:
                    yield Label("Advice and items that failed their check", classes="build-section")
                    t = Text()
                    for i in other:
                        t.append(f"· {item_label(i)}\n")
                        for p in i.problems:
                            t.append(f"   ✗ {p}\n", style="red")
                    yield Static(t, classes="build-text")
            with Horizontal():
                yield Button("✓ Apply ticked [ctrl+s]", variant="success", id="weekly-apply", disabled=not doable)
                yield Button("Close [Esc]", id="weekly-close")

    def action_apply(self) -> None:
        lists = self.query("#weekly-items")
        picked = list(lists.first(SelectionList).selected) if lists else []
        self.dismiss(picked)

    def action_close(self) -> None:
        self.dismiss(None)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        event.stop()
        if event.button.id == "weekly-apply":
            self.action_apply()
        else:
            self.action_close()
