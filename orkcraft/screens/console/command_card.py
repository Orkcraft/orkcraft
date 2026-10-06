"""The Command Card: the clickable actions for the current focus state."""
from __future__ import annotations

from typing import TYPE_CHECKING

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import OptionList
from textual.widgets.option_list import Option

from orkcraft.realm.orcs import RESIDENT
from orkcraft.screens.console.cards import orc_key
from orkcraft.widgets.office import OfficeOptionList, OfficeStatic

if TYPE_CHECKING:
    from orkcraft.app import FocusState
    from orkcraft.realm.roster import Roster


NEUTRAL_ACTIONS = [
    ("B", "[B] 🏗️ Build"),
    ("P", "[P] 📜 Window Presets Catalog"),
    ("S", "[S] 🧌 Summon Ork / Warband"),
    ("T", "[T] 🌲 Toggle Terrain (Dim / Black)"),
    ("G", "[G] ⎇ Worktree of this Orkspace"),
]

BUILDING_ACTIONS = [
    ("R", "[R] ➕ Recruit Ork"),
    ("L", "[L] 📜 Building Chronicles"),
    ("Y", "[Y] 🛤 Listen to Another Window (Road)"),
    ("U", "[U] 🚧 Remove the Incoming Road"),
    ("P", "[P] 📌 Pin / Unpin Window"),
    ("M", "[M] 🗖 Window Mode (Move / Resize)"),
    ("X", "[X] 💥 Demolish Window"),
    ("Z", "[Z] ↶ Revert to Previous Checkpoint"),
    ("K", "[K] 👍 Good Result (a Reference)"),
    ("F", "[F] 👎 Bad Result — What Went Wrong?"),
    ("D", "[D] 🎨 Redesign its Window (Steward)"),
]

ROAD_ACTIONS = [
    ("H", "[H] 🔀 Handler of this Road"),
    ("U", "[U] 🚧 Remove this Road"),
]


QUICK_KEYS = ("[", "]")     # a selected building's two quick actions

RESIDENT_ACTIONS = [
    ("C", "[C] 💬 Deploy / Open Session"),
    ("T", "[T] ⚡ Orders & Trigger"),
    ("D", "[D] 🗑 Dismiss"),
    ("H", "[H] 🛑 Halt"),
    ("L", "[L] 📜 Unit Chronicles"),
]

UNIT_ACTIONS = [
    ("C", "[C] 💬 Unit Chat / Orders"),
    ("L", "[L] 📜 Unit Chronicles"),
    ("T", "[T] ⚡ Triggers"),
    ("H", "[H] 🛑 Halt Unit"),
]



class CommandCard(Vertical):
    """Right column: clickable actions for the current focus state."""

    def compose(self) -> ComposeResult:
        yield OfficeStatic("⚒️ COMMAND CARD", id="command-title", classes="console-title")
        yield OfficeOptionList(id="command-actions")
        yield OfficeStatic("[Esc] Deselect / Neutral Mode", markup=False, id="command-footer", classes="console-footer")

    def update_content(self, focus_state: FocusState, roster: Roster) -> None:
        actions_list = self.query_one("#command-actions", OptionList)
        highlighted = actions_list.highlighted
        actions_list.clear_options()

        if focus_state.mode == "neutral":
            actions = NEUTRAL_ACTIONS
        elif focus_state.mode == "building":
            # Only what this building can do: the common commands are keys (and Info's buttons).
            actions = []
            b_id = focus_state.building_id
            spec = getattr(self.app, "custom_specs", {}).get(b_id) if b_id else None
            if spec and "actions" in spec:
                for act in spec["actions"]:
                    actions.append((act["key"], f"[{act['key']}] {act['label']}"))
            spec = self.app.spec_of(b_id) if hasattr(self.app, "spec_of") else spec
            if spec:                                         # the hut's quick actions
                from orkcraft.realm import catalog
                quick = [(f"QA{key}", f"[{key}] {qa.glyph} {qa.label}")
                         for key, qa in zip(QUICK_KEYS, catalog.quick_actions_of(spec))]
                actions = quick + actions
        elif focus_state.mode == "unit":
            orc = next((o for o in roster.orcs if orc_key(o) == focus_state.orc_key), None)
            if orc and orc.category == RESIDENT:
                actions = list(RESIDENT_ACTIONS)
                if orc.lead:
                    actions.append(("W", "[W] 🔎 Watch now (steward)"))
            else:
                actions = list(UNIT_ACTIONS)
            if orc and orc.alert:
                actions.insert(0, ("ENTER", "[Enter] ❓ Resolve Alert"))
        elif focus_state.mode == "road":
            actions = ROAD_ACTIONS
        else:
            actions = NEUTRAL_ACTIONS

        for key, label in actions:
            actions_list.add_option(Option(Text(label), id=f"action:{key}"))
        # A building with no commands of its own leaves the room to the Info panel; a garrison or
        # War Tent orc is commanded in its chat, which stands where the card was.
        chat = False
        if focus_state.mode == "unit":
            from orkcraft.screens.orc_chat import OrcChat
            chat = OrcChat.supports(next((o for o in roster.orcs if orc_key(o) == focus_state.orc_key), None))
        self.set_class((not actions and focus_state.mode == "building") or chat, "-empty")

        if highlighted is not None and highlighted < actions_list.option_count:
            actions_list.highlighted = highlighted

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        oid = event.option_id or ""
        if oid.startswith("action:"):
            key = oid.split(":", 1)[1]
            if key.startswith("QA"):
                self.app.action_quick_action(QUICK_KEYS.index(key[2:]))
            elif key == "ENTER":
                orc = next((o for o in self.app.roster.orcs if orc_key(o) == self.app.focus_state.orc_key), None)
                if orc and orc.alert:
                    self.app.open_alert(orc.alert, orc.name)
            elif (
                getattr(self.app, "focus_state", None)
                and self.app.focus_state.mode == "building"
                and any(a.get("key") == key for a in getattr(self.app, "custom_specs", {}).get(self.app.focus_state.building_id, {}).get("actions", []))
            ):
                self.app.action_custom_action(key)
            else:
                self.app.action_command_card(key)
        event.stop()
