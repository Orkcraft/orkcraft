"""Recruiter and steward screens: progress, the recruit preview, the steward's report."""
from __future__ import annotations

import json

from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Label, LoadingIndicator, OptionList, Static
from textual.widgets.option_list import Option

from orkcraft.realm import looks, pipes
from orkcraft.realm.recruiter import RecruitResult
from orkcraft.screens.build_flow import MODAL_CSS


class OrcProgress(ModalScreen[None]):
    """Shown while the Recruiter or a steward works in a background thread; Esc hides it."""

    BINDINGS = [Binding("escape", "dismiss(None)", "Hide")]
    DEFAULT_CSS = MODAL_CSS.format(cls="OrcProgress", border_color="$accent", title_color="$accent")

    def __init__(self, title: str) -> None:
        super().__init__()
        self.title_text = title

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label(self.title_text, classes="build-title")
            yield LoadingIndicator()
            yield Static("Esc hides it — the work goes on", classes="build-hint")


def _chain_lines(chain: list[dict]) -> list[str]:
    out = []
    for op in chain:
        args = ", ".join(f"{k}={json.dumps(v, ensure_ascii=False)}" for k, v in op.items() if k != "op")
        out.append(f"  • {op.get('op')}({args})")
    return out


class RecruitPreview(ModalScreen[bool]):
    """The recruited handler before it joins: kind and why, orders, harness, chain, roads, cost."""

    BINDINGS = [Binding("enter", "confirm", "Recruit"), Binding("escape", "cancel", "Discard")]
    DEFAULT_CSS = MODAL_CSS.format(cls="RecruitPreview", border_color="$accent", title_color="$accent") + """
    RecruitPreview VerticalScroll { height: auto; max-height: 32; }
    """

    def __init__(self, building_title: str, result: RecruitResult, titles: dict[str, str]) -> None:
        super().__init__()
        self.building_title, self.result, self.titles = building_title, result, titles

    def compose(self) -> ComposeResult:
        orc = self.result.orc or {}
        kind = orc.get("kind", "agent")
        cost = f"${self.result.cost_usd:.2f}" if self.result.cost_usd is not None else "—"
        head = Text()
        head.append(f"{looks.kind_icon(kind)} {orc.get('name', '?')}", style="bold")
        scheme = looks.scheme_text(orc.get("harness"), kind)
        if scheme.plain:
            head.append("  ")
            head.append(scheme)
        head.append(f"  · {looks.KIND_LABELS.get(kind, kind)}\n")
        head.append(f"Role: {orc.get('role', '')}\n", style="dim")
        head.append(f"Why {kind}: {orc.get('why', '')}\n", style="italic")
        head.append(f"Attempts: {len(self.result.attempts)}  ·  Cost: {cost}")
        with Vertical():
            yield Label(f"🧌 New handler for {self.building_title}", classes="build-title")
            with VerticalScroll():
                yield Static(head, classes="build-text")
                yield Label("Roads:", classes="build-section")
                lines = []
                for r in self.result.roads:
                    flt = f"  filter {json.dumps(r['filter'], ensure_ascii=False)}" if r.get("filter") else ""
                    lines.append(f"  ◂ {self.titles.get(r['from'], r['from'])} · {pipes.label(r['event'])}{flt}")
                yield Static(Text("\n".join(lines) or "  none"), classes="build-text")
                if kind == "chain":
                    yield Label("Chain:", classes="build-section")
                    yield Static(Text("\n".join(_chain_lines(orc.get("chain", [])))), classes="build-text")
                if orc.get("orders"):
                    yield Label("Orders:", classes="build-section")
                    yield Static(Text(orc["orders"]), classes="build-text")
                if kind in ("agent", "hybrid"):
                    yield Static(Text(f"Harness: {looks.scheme_long(orc.get('harness'), kind)}"), classes="build-text")
                if self.result.script_source:
                    yield Label("Script (runs once you approve it and the Council passes it; a later edit holds it again):",
                                classes="build-section")
                    yield Static(Text(self.result.script_source[:1500]), classes="build-text")
            with Horizontal():
                yield Button("Recruit [Enter]", variant="primary", id="btn-recruit")
                yield Button("Discard [Esc]", id="btn-discard")

    def action_confirm(self) -> None:
        self.dismiss(True)

    def action_cancel(self) -> None:
        self.dismiss(False)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(event.button.id == "btn-recruit")


class RecruitFailed(ModalScreen[None]):
    BINDINGS = [Binding("escape", "dismiss(None)", "Close"), Binding("enter", "dismiss(None)", "Close")]
    DEFAULT_CSS = MODAL_CSS.format(cls="RecruitFailed", border_color="$error", title_color="$error")

    def __init__(self, result: RecruitResult) -> None:
        super().__init__()
        self.result = result

    def compose(self) -> ComposeResult:
        if self.result.error:
            text = self.result.error
        elif self.result.attempts and self.result.attempts[-1].errors:
            text = "\n".join(f"• {e}" for e in self.result.attempts[-1].errors)
        else:
            text = "No valid handler after the maximum attempts."
        cost = f"\nCost: ${self.result.cost_usd:.2f}" if self.result.cost_usd is not None else ""
        with Vertical():
            yield Label("💥 The Recruiter found no valid handler", classes="build-title")
            with VerticalScroll():
                yield Static(Text(text + cost), classes="build-text")
            yield Static("Esc / Enter closes · R tries again", classes="build-hint")


class StewardView(ModalScreen[int | None]):
    """The steward's findings and proposals; Enter applies the highlighted ready proposal
    (dismisses its index)."""

    BINDINGS = [Binding("escape", "dismiss(None)", "Close")]
    DEFAULT_CSS = MODAL_CSS.format(cls="StewardView", border_color="$accent", title_color="$accent") + """
    StewardView OptionList { height: auto; max-height: 12; background: transparent; border: none; }
    """

    def __init__(self, building_title: str, report: dict) -> None:
        super().__init__()
        self.building_title, self.report = building_title, report

    def compose(self) -> ComposeResult:
        r = self.report
        cost = f"${r['cost_usd']:.2f}" if isinstance(r.get("cost_usd"), (int, float)) else "—"
        head = Text()
        for f in r.get("findings", []):
            head.append(f"• [{f['kind']}] {f['summary']}\n")
        if not r.get("findings"):
            head.append("Nothing to report — no model was asked.\n", style="dim")
        head.append(f"{'Asked the model' if r.get('escalated') else 'Metrics only'} · cost {cost}", style="dim")
        if r.get("error"):
            head.append(f"\n{r['error']}", style="yellow")
        with Vertical():
            yield Label(f"🔎 Steward · {self.building_title}", classes="build-title")
            yield Static(head, classes="build-text")
            yield Label("Proposals:", classes="build-section")
            yield OptionList(id="steward-proposals")
            yield Static("Enter applies a ready proposal · Esc closes", classes="build-hint")

    def on_mount(self) -> None:
        lst = self.query_one("#steward-proposals", OptionList)
        for i, p in enumerate(self.report.get("proposals", [])):
            rep = p.get("replay")
            ready = p.get("type") != "demote" or (rep and rep.get("score", 0) >= 0.8 and rep.get("total", 0) >= 1)
            t = Text()
            t.append("✅ " if ready else "🔍 ")
            t.append(f"{p.get('type')}", style="bold")
            if rep:
                t.append(f"  replay {rep.get('exact', 0)}/{rep.get('total', 0)} exact · agrees {rep.get('score', 0):.0%}",
                         style="green" if ready else "yellow")
            t.append(f"\n   {p.get('why', '')}", style="dim")
            lst.add_option(Option(t, id=str(i) if ready and p.get("type") != "note" else None,
                                  disabled=not ready or p.get("type") == "note"))
        if not lst.option_count:
            lst.add_option(Option(Text("none", style="dim"), disabled=True))
        first = next((i for i in range(lst.option_count) if not lst.get_option_at_index(i).disabled), None)
        if first is not None:
            lst.highlighted = first   # without a highlighted row Enter selects nothing
        lst.focus()

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        event.stop()
        if event.option_id is not None:
            self.dismiss(int(event.option_id))
