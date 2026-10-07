"""The Clan Roster: the accordion roster in Neutral, a building's garrison, an ork's 🎒 Inventory."""
from __future__ import annotations

from typing import TYPE_CHECKING

from rich.text import Text
from textual import events
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.message import Message
from textual.widgets import OptionList, Static
from textual.widgets.option_list import Option

from orkcraft.realm.orcs import BUILDER, COUNCIL, RESIDENT, WORKER, Orc
from orkcraft.screens.console.cards import STATUS_DISPLAY, _append_tier, orc_key
from orkcraft.tui.text import scheme_text
from orkcraft.widgets.office import WordedOptionList, WordedStatic

if TYPE_CHECKING:
    from orkcraft.app import FocusState
    from orkcraft.realm.roster import Roster


INVENTORY_W = 19     # the garrison's 22 columns less its border and the list's scrollbar


class ClanRoster(Vertical):
    """Centre column: accordion roster in Neutral, garrison in Building, card in Unit."""

    class BuildingSelected(Message):
        def __init__(self, building_id: str) -> None:
            super().__init__()
            self.building_id = building_id

    class OrcSelected(Message):
        def __init__(self, key: str) -> None:
            super().__init__()
            self.key = key

    def __init__(self, id: str | None = None, classes: str | None = None) -> None:
        super().__init__(id=id, classes=classes)
        self.folded_headers: set[str] = set()
        self.inventory_of: str | None = None      # the orc whose 🎒 inventory the list shows

    def compose(self) -> ComposeResult:
        yield WordedStatic("🧌 CLAN ROSTER", id="roster-title", classes="console-title")
        yield WordedOptionList(id="roster-list")
        yield WordedStatic("", markup=False, id="roster-card")
        yield WordedStatic("[Space] Fold   [1-9] Select", markup=False, id="roster-footer", classes="console-footer")

    @staticmethod
    def _render_garrison_row(o: Orc, number: int, seen: set[str] | frozenset = frozenset()) -> Text:
        """One line for the narrow garrison: number, ❓ when it has a question you have not opened
        yet, tier, name, its models as marks (✻ Claude orange, ✦ agy blue, ⌬ Codex green) and its state."""
        from orkcraft.realm import looks

        t = Text(no_wrap=True, overflow="ellipsis")
        name_style = "bold yellow" if o.status == "alert" else "bold"
        asks = o.alert.id not in seen if o.alert is not None else o.status == "alert"
        t.append(f"[{number}] ", style="dim")
        if asks:
            t.append("❓", style="bold black on yellow")
            t.append(" ")
        t.append("★ " if o.lead else "", style=name_style)
        _append_tier(t, o)
        t.append(o.name, style="bold yellow" if asks else name_style)
        scheme = scheme_text(o.harness, o.kind)
        if scheme.plain:
            t.append(" ")
            t.append(scheme)
        elif o.kind in ("chain", "script"):
            t.append(f" {looks.kind_icon(o.kind)}")
        if not asks:
            t.append(f" {o.status_icon}", style="dim")
        return t

    @staticmethod
    def _render_orc_row(o: Orc, number: int | None = None) -> Text:
        """Name and state only: what it does, its models and spend are in the Info panel."""
        t = Text(no_wrap=True, overflow="ellipsis")
        t.append(f"[{number}] " if number is not None else "  • ")
        star = "★ " if o.lead else ""
        name_style = "bold yellow" if o.status == "alert" else "bold"
        t.append(star, style=name_style)
        _append_tier(t, o)
        t.append(o.name, style=name_style)
        st = STATUS_DISPLAY.get(o.status, f"{o.status_icon} {o.status.capitalize()}")
        st_style = "bold yellow" if o.status == "alert" else ("bold green" if o.status == "busy" else "dim")
        t.append(f"  {st}", style=st_style)
        return t

    def update_content(self, focus_state: FocusState, roster: Roster) -> None:
        title = self.query_one("#roster-title", Static)
        footer = self.query_one("#roster-footer", Static)
        lst = self.query_one("#roster-list", OptionList)
        card = self.query_one("#roster-card", Static)

        if focus_state.mode == "neutral":
            title.update("🧌 CLAN ROSTER")
            footer.update("[Space] Fold")
            card.display = False
            lst.display = True

            highlighted = lst.highlighted
            lst.clear_options()

            # Raised buildings
            raised = [w for w in self.app.desktop.windows if not w.hidden]
            for w in raised:
                b = self.app.building(w.window_id)
                if b is None:
                    continue
                garrison = roster.garrison(w.window_id)
                garrison_count = len(garrison)
                hid = f"header:building:{b.id}"
                is_folded = hid in self.folded_headers
                arrow = "▶" if is_folded else "▼"
                lst.add_option(Option(Text(f"{arrow} {b.icon} {b.title} ({garrison_count})", style="bold",
                                           no_wrap=True, overflow="ellipsis"), id=hid))
                if not is_folded:
                    for o in garrison:
                        lst.add_option(Option(self._render_orc_row(o), id=orc_key(o)))

            # Other categories
            groups = (
                (WORKER, "⚔️ Warband"),
                (COUNCIL, "🏛️ Council"),
                (BUILDER, "🔨 Builders"),
            )
            for cat, cat_title in groups:
                members = [o for o in roster.orcs if o.category == cat]
                hid = f"header:{cat}"
                is_folded = hid in self.folded_headers
                arrow = "▶" if is_folded else "▼"
                lst.add_option(Option(Text(f"{arrow} {cat_title} ({len(members)})", style="bold dim"), id=hid))
                if not is_folded:
                    for o in members:
                        lst.add_option(Option(self._render_orc_row(o), id=orc_key(o)))

            if highlighted is not None and highlighted < lst.option_count:
                lst.highlighted = highlighted

        elif focus_state.mode == "unit" and (orc := next(
                (o for o in roster.orcs if orc_key(o) == focus_state.orc_key), None)) is not None \
                and orc.category in (RESIDENT, WORKER):
            self._show_inventory(orc)

        elif focus_state.mode in ("building", "road", "unit"):
            # The garrison stays: a selected orc is highlighted in it, its card is in the Info panel.
            orc = next((o for o in roster.orcs if orc_key(o) == focus_state.orc_key), None) \
                if focus_state.mode == "unit" else None
            b_id = focus_state.building_id or (orc.building if orc else "") or ""
            if orc is not None and orc.category != RESIDENT:
                members = [o for o in roster.orcs if o.category == orc.category]
                label = {WORKER: "⚔️ Warband", COUNCIL: "🏛️ Council", BUILDER: "🔨 Builders"}.get(orc.category, "Orks")
            else:
                members = roster.garrison(b_id)
                b = self.app.building(b_id)
                label = "🧌 GARRISON"
            title.update(label)
            footer.update("[1-9] · [Esc] Back" if focus_state.mode != "road" else "[H] · [U] · [Esc]")
            card.display = False
            lst.display = True
            prev = lst.highlighted
            lst.clear_options()
            for idx, o in enumerate(members, 1):
                lst.add_option(Option(self._render_garrison_row(o, idx, getattr(self.app, "seen_alerts", set())),
                                      id=orc_key(o)))
            if not members:
                lst.add_option(Option(Text("No orks yet\nR recruits", style="dim"), disabled=True))
            keys = [orc_key(o) for o in members]
            if orc is not None and orc_key(orc) in keys:
                lst.highlighted = keys.index(orc_key(orc))
            elif prev is not None and prev < lst.option_count:
                lst.highlighted = prev          # the 1 s refresh must not undo the operator's cursor

    def _show_inventory(self, orc: Orc) -> None:
        """🎒 The selected orc's inventory: its model and tier (a button to change them), then
        the tools it reached for lately — each opens its history with that tool."""
        from orkcraft.realm import inventory, tiers

        self.query_one("#roster-title", Static).update("🎒 INVENTORY")
        self.query_one("#roster-footer", Static).update("[Enter] · [Esc] Back")
        self.query_one("#roster-card", Static).display = False
        lst = self.query_one("#roster-list", OptionList)
        lst.display = True
        prev = lst.highlighted if self.inventory_of == orc_key(orc) else None
        self.inventory_of = orc_key(orc)
        lst.clear_options()

        snap = getattr(self.app, "snapshot", None)
        term = orc.session if orc.category == RESIDENT else orc.ref
        live = snap.model_by_terminal.get(term, "") if snap is not None and term else ""
        models = inventory.models_of(orc, live)
        row = Text(no_wrap=True, overflow="ellipsis")
        if not models:
            row.append("🪧 no model", style="dim")
        for i, (tier, model) in enumerate(models[:2]):
            if i:
                row.append("→", style="dim")
            if tier:
                row.append(f"{tiers.icon(tier)} ", style=tiers.TIER_STYLES.get(tier, ""))
            row.append(model, style="bold")
        if len(models) > 2:
            row.append(f"·{len(models)}", style="dim")
        can_change = orc.category == RESIDENT and orc.kind not in ("chain", "script")
        if can_change:                     # the whole row is the button; ⇄ says so
            row.append(" ")
            row.append(" ⇄ ", style="bold black on #f2c66d")
        lst.add_option(Option(row, id="inv:model"))
        lst.add_option(Option(Text("── tools ──", style="dim"), disabled=True))
        repo = getattr(self.app, "repo_root", None)
        tools = inventory.recent_tools(repo, orc) if repo is not None else []
        for use in tools:
            t = Text(no_wrap=True, overflow="ellipsis")
            t.append("🔧 ")
            t.append(inventory.short_tool(use.name))
            count = Text(f" ×{use.count}", style="dim")
            t.truncate(INVENTORY_W - count.cell_len, overflow="ellipsis")
            lst.add_option(Option(Text.assemble(t, count), id=f"inv:tool:{use.name}"))
        if not tools:
            lst.add_option(Option(Text("no tool calls yet", style="dim"), disabled=True))
        if prev is not None and prev < lst.option_count:
            lst.highlighted = prev

    def toggle_fold(self, header_id: str) -> None:
        if header_id in self.folded_headers:
            self.folded_headers.remove(header_id)
        else:
            self.folded_headers.add(header_id)
        self.update_content(self.app.focus_state, self.app.roster)

    def on_key(self, event: events.Key) -> None:
        if event.key == "space":
            lst = self.query_one("#roster-list", OptionList)
            if lst.has_focus and lst.highlighted is not None:
                opt = lst.get_option_at_index(lst.highlighted)
                oid = opt.id or ""
                if oid.startswith("header:"):
                    self.toggle_fold(oid)
            if lst.has_focus:
                # Space belongs to the roster (fold): on an orc row it must not reach Halt All.
                event.stop()
                event.prevent_default()
            return
        elif event.key in "123456789":
            lst = self.query_one("#roster-list", OptionList)
            if lst.has_focus and getattr(self.app, "focus_state", None) and self.app.focus_state.mode in ("building", "unit"):
                idx = int(event.key) - 1
                orc_ids = [o.id for o in (lst.get_option_at_index(i) for i in range(lst.option_count))
                           if o.id and o.id.startswith("orc:")]
                if idx < len(orc_ids):
                    self.post_message(self.OrcSelected(orc_ids[idx]))
                    event.stop()
                    return

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        oid = event.option_id or ""
        if oid.startswith("header:building:"):
            building_id = oid.split(":", 2)[2]
            self.post_message(self.BuildingSelected(building_id))
        elif oid.startswith("header:"):
            self.toggle_fold(oid)
        elif oid.startswith("orc:"):
            self.post_message(self.OrcSelected(oid))
        elif oid.startswith("inv:"):
            self._use_inventory(oid)
        event.stop()

    def _use_inventory(self, oid: str) -> None:
        orc = next((o for o in self.app.roster.orcs if orc_key(o) == self.inventory_of), None)
        if orc is None:
            return
        if oid == "inv:model":
            self.app.open_orc_model(orc)
        elif oid.startswith("inv:tool:"):
            from orkcraft.screens.chronicles_view import UnitChronicles
            self.app.push_screen(UnitChronicles(orc, self.app.repo_root, tool=oid.split(":", 2)[2]))
