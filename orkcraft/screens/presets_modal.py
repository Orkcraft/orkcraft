"""Modal screen listing the buildings catalog (Core Presets & Migrated)."""
from __future__ import annotations

from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import OptionList, Static
from textual.widgets.option_list import Option

from orkcraft.realm.buildings import CORE, CUSTOM, MIGRATED, Building
from orkcraft.scroll import TownScroll


class PresetsModal(ModalScreen[str | None]):
    """Catalog of building presets. Enter raises/focuses the building, Esc cancels."""

    DEFAULT_CSS = """
    PresetsModal {
        align: center middle;
    }
    #presets-dialog {
        width: 60;
        height: auto;
        max-height: 80%;
        border: thick $accent;
        background: $surface;
        padding: 1 2;
    }
    #presets-title {
        text-style: bold;
        color: $accent;
        padding-bottom: 1;
    }
    #presets-list {
        height: auto;
        max-height: 20;
        background: transparent;
        border: none;
    }
    #presets-footer {
        color: $text-muted;
        padding-top: 1;
    }
    """

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
    ]

    def __init__(
        self,
        buildings: list[Building],
        built_or_scroll: set[str] | TownScroll,
        numbers: dict[str, int],
        scroll: TownScroll | None = None,
    ) -> None:
        super().__init__()
        self.buildings = buildings
        self.numbers = numbers
        if isinstance(built_or_scroll, TownScroll):
            self.scroll: TownScroll | None = built_or_scroll
            self.built = {b.id for b in self.scroll.buildings if not b.demolished}
        else:
            self.built = built_or_scroll
            self.scroll = scroll

    def compose(self) -> ComposeResult:
        with Vertical(id="presets-dialog"):
            yield Static("─── 📜 WINDOW PRESETS CATALOG ───", id="presets-title")
            yield OptionList(id="presets-list")
            yield Static("[Enter] Select / Build   [Esc] Cancel", id="presets-footer")

    def on_mount(self) -> None:
        lst = self.query_one("#presets-list", OptionList)
        lst.clear_options()
        from orkcraft.realm import catalog
        lst.add_option(Option(Text("[ What do you need? — a camp building, no model call ]", style="bold dim"),
                              disabled=True))
        for intent, ids in catalog.INTENTS:
            ids = tuple(t for t in ids if t not in catalog.GUI_ONLY)      # the window's alone (calm-town.md §9)
            if not ids:
                continue
            lst.add_option(Option(Text(f"  ▸ {intent}", style="bold"), disabled=True))
            for tid in ids:
                t = catalog.TYPES.get(tid)
                if t is None:
                    continue
                label = Text(no_wrap=True, overflow="ellipsis")
                label.append(f"     {t.icon} {t.title}")
                label.append(f"  {t.summary[:60]}", style="dim")
                lst.add_option(Option(label, id=f"type:{tid}"))
        for category, title in (
            (CORE, "[ Core Presets ]"),
            (MIGRATED, "[ Migrated from mg-tui ]"),
            (CUSTOM, "[ Your buildings ]"),            # every building raised from a spec
        ):
            lst.add_option(Option(Text(title, style="bold dim"), disabled=True))
            for b in self.buildings:
                if b.category != category:
                    continue
                n = self.numbers.get(b.id)
                key = f"[{n}]" if n and n <= 9 else "   "
                label = Text(no_wrap=True, overflow="ellipsis")
                if self.scroll is not None:
                    spec = self.scroll.building(b.id)
                    ork = self.scroll.orkspace_of(b.id)
                    is_demolished = spec is None or spec.demolished
                    is_active_raised = (not is_demolished and ork is not None and ork.id == self.scroll.active_orkspace_id)
                    label.append(f" {key} {b.icon} {b.title}", style="" if is_active_raised else "dim")
                    if is_demolished or ork is None:
                        label.append("  ○ build", style="dim")
                    else:
                        hk = ork.hotkey or ork.name
                        label.append(f"  ● {hk}", style="green")
                else:
                    is_built = b.id in self.built
                    label.append(f" {key} {b.icon} {b.title}", style="" if is_built else "dim")
                    label.append("  ●" if is_built else "  ○ build", style="green" if is_built else "dim")
                lst.add_option(Option(label, id=f"building:{b.id}"))
        lst.focus()

    def action_cancel(self) -> None:
        self.dismiss(None)

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        oid = event.option_id or ""
        if oid.startswith("building:"):
            self.dismiss(oid.split(":", 1)[1])
        elif oid.startswith("type:"):
            self.dismiss(oid)                         # a camp building to build from its type
        else:
            self.dismiss(None)
        event.stop()
