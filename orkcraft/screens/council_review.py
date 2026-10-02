"""🏛 The Council's verdict: five councillors on one new building, agent or road.

A rule's block cannot be approved — Back returns to the edit. The light model's objections are
opinions: Approve anyway goes ahead and the review log says so.
"""
from __future__ import annotations

from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Label, LoadingIndicator, Static

from orkcraft.realm import fastpath
from orkcraft.screens.build_flow import MODAL_CSS

_MARK = {"block": ("✗ ", "bold red"), "object": ("? ", "yellow"), "warn": ("⚠ ", "yellow")}


def verdict_text(verdict: fastpath.Verdict) -> Text:
    out = Text()
    for rid, icon, name, duty, _ in fastpath.ROLES:
        found = verdict.of(rid)
        out.append(f"{icon} {name}", style="bold")
        out.append(f" · {duty}\n", style="dim")
        if not found:
            out.append("   ✓ nothing to add\n", style="green")
        for n in found:
            mark, style = _MARK.get(n.severity, ("· ", ""))
            out.append(f"   {mark}{n.text}\n", style=style)
    if verdict.model:
        cost = f" · ${verdict.cost_usd:.3f}" if verdict.cost_usd is not None else ""
        out.append(f"\nrules + {verdict.model}{cost}", style="dim")
    elif verdict.error:
        out.append(f"\nrules only — the light model did not answer: {verdict.error[:120]}", style="dim")
    else:
        out.append("\nrules only", style="dim")
    return out


class CouncilProgress(ModalScreen[None]):
    BINDINGS = [Binding("escape", "dismiss(None)", "Hide")]
    DEFAULT_CSS = MODAL_CSS.format(cls="CouncilProgress", border_color="$accent", title_color="$accent")

    def __init__(self, label: str) -> None:
        super().__init__()
        self.label = label

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label(f"🏛 The Council reviews the {self.label}…", classes="build-title")
            yield LoadingIndicator()
            yield Static("Esc hides it — the review keeps running", classes="build-hint")


class CouncilVerdict(ModalScreen[bool]):
    """True: approved (or approved anyway); False: back to the edit."""

    BINDINGS = [Binding("enter", "approve", "Approve"), Binding("escape", "back", "Back")]
    DEFAULT_CSS = MODAL_CSS.format(cls="CouncilVerdict", border_color="$accent", title_color="$accent")

    def __init__(self, verdict: fastpath.Verdict) -> None:
        super().__init__()
        self.verdict = verdict

    def compose(self) -> ComposeResult:
        v = self.verdict
        head = "rejected" if v.blocked else "has objections" if v.objections else "approves with notes" \
            if not v.clean else "approves"
        with Vertical():
            yield Label(Text(f"🏛 Council · fast review of the {v.subject.label}: {head}"), classes="build-title")
            with VerticalScroll():
                yield Static(verdict_text(v), id="council-notes", classes="build-text")
            with Horizontal():
                if not v.blocked:
                    yield Button("Approve anyway [Enter]" if v.objections else "Approve [Enter]",
                                 variant="warning" if v.objections else "primary", id="council-approve")
                yield Button("Back [Esc]", id="council-back")
            yield Static("✗ a rule blocks it — fix the reason and try again" if v.blocked else
                         "? the light model objects — your call" if v.objections else
                         "⚠ notes only — nothing blocks it", classes="build-hint")

    def action_approve(self) -> None:
        if not self.verdict.blocked:
            self.dismiss(True)

    def action_back(self) -> None:
        self.dismiss(False)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(event.button.id == "council-approve" and not self.verdict.blocked)
