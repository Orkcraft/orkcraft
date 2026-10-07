"""The War Map: the orkspaces of the town, the console's left column."""
from __future__ import annotations

from typing import TYPE_CHECKING

from rich.text import Text
from textual import events
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import OptionList, Static
from textual.widgets.option_list import Option

from orkcraft import theme
from orkcraft.realm.orcs import ALERT_ICON
from orkcraft.widgets.office import WordedOptionList, WordedStatic

if TYPE_CHECKING:
    from orkcraft.app import FocusState
    from orkcraft.realm.roster import Roster
    from orkcraft.scroll import Orkspace, TownScroll

ALERT_STYLE = "bold #ff8c1a"      # a place with a question waiting: the fire's orange


def orkspace_has_alert(scroll_obj: TownScroll | None, ork: Orkspace, roster: Roster) -> bool:
    if scroll_obj is None:
        return bool(roster.alerts)
    is_active = (ork.id == scroll_obj.active_orkspace_id)
    for alert in roster.alerts:
        orc = next((o for o in roster.orcs if o.alert and o.alert.id == alert.id), None)
        if orc is not None and orc.building:
            b_ork = scroll_obj.orkspace_of(orc.building)
            if b_ork is not None and b_ork.id == ork.id:
                return True
        else:
            if is_active:
                return True
    return False


class WarMap(Vertical):
    """Left column: shows camp/orkspace list in Neutral, card in Building/Unit."""

    def compose(self) -> ComposeResult:
        yield WordedStatic("🗺️ WAR MAP (Orkspaces)", id="warmap-title", classes="console-title")
        yield WordedOptionList(id="warmap-list")
        yield WordedStatic("[F1] 🏰 Main Camp", markup=False, id="warmap-content")
        yield WordedStatic("[F1-F8]   [N] New   [d] Del", markup=False, id="warmap-footer", classes="console-footer")

    def update_content(self, focus_state: FocusState, roster: Roster, biome: str) -> None:
        lst = self.query_one("#warmap-list", OptionList)
        content = self.query_one("#warmap-content", Static)
        scroll_obj = getattr(self.app, "scroll", None)

        lst.display = True
        content.display = False
        content.update(f"[F1] 🏰 Main Camp {theme.BIOME_ICONS.get(biome, '')}")

        highlighted = lst.highlighted
        lst.clear_options()
        if scroll_obj is not None:
            active_idx = 0
            for i, ork in enumerate(scroll_obj.orkspaces):
                is_active = (ork.id == scroll_obj.active_orkspace_id)
                if is_active:
                    active_idx = i
                prefix = "▶ " if is_active else "  "
                hk = f"[{ork.hotkey}] " if ork.hotkey else ""
                asks = orkspace_has_alert(scroll_obj, ork, roster)
                mark = f" {ALERT_ICON}" if asks else ""
                wt_mark = getattr(self.app, "worktree_marks", {}).get(ork.id, "")
                row_text = (f"{prefix}{hk}{ork.icon} {ork.name} {theme.BIOME_ICONS.get(ork.biome, '')}"
                            f"{' ' + wt_mark if wt_mark else ''}{mark}")
                style = ALERT_STYLE if asks else "bold" if is_active else ""   # a question lights the row
                lst.add_option(Option(Text(row_text, style=style), id=f"orkspace:{ork.id}"))
            # The cursor follows the active orkspace unless the operator is browsing the list.
            if lst.has_focus and highlighted is not None and highlighted < lst.option_count:
                lst.highlighted = highlighted
            else:
                lst.highlighted = active_idx
        else:
            alerts_mark = f" {ALERT_ICON}" if roster.alerts else ""
            lst.add_option(Option(Text(f"▶ [F1] 🏰 Main Camp {theme.BIOME_ICONS.get(biome, '')}{alerts_mark}", style="bold"),
                                  id="orkspace:main_camp"))

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        oid = event.option_id or ""
        if oid.startswith("orkspace:"):
            target_id = oid.split(":", 1)[1]
            self.app.desktop.switch_orkspace(target_id)
        event.stop()

    def on_click(self, event: events.Click) -> None:
        if event.widget and event.widget.id == "warmap-footer":
            self.app.action_new_orkspace()
            event.stop()

    def on_key(self, event: events.Key) -> None:
        if event.key == "d" and self.query_one("#warmap-list", OptionList).display:
            self.action_delete_orkspace()
            event.stop()

    def action_delete_orkspace(self) -> None:
        """Remove the highlighted orkspace if it is empty and not the last one."""
        from orkcraft import scroll as ts

        lst = self.query_one("#warmap-list", OptionList)
        if lst.highlighted is None or lst.highlighted >= lst.option_count:
            return
        oid = lst.get_option_at_index(lst.highlighted).id or ""
        if not oid.startswith("orkspace:"):
            return
        app = self.app
        target_id = oid.split(":", 1)[1]
        was_active = app.scroll.active_orkspace_id == target_id
        try:
            ts.remove_orkspace(app.scroll, target_id)
        except ValueError as e:
            app.notify(str(e), title="War Map", severity="warning")
            return
        if was_active:
            # The canvas under the operator changed: same path as a switch (neutral, refresh).
            app.desktop.apply_orkspace(app.scroll.active_orkspace_id)
            app.desktop.post_message(app.desktop.OrkspaceChanged(app.scroll.active_orkspace_id))
        app.desktop.save()
        app.refresh_roster()
