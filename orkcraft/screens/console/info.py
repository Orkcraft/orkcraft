"""The Info panel: what the selected ork, building or road is, with its buttons."""
from __future__ import annotations

from typing import TYPE_CHECKING

from rich.text import Text
from textual import events
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Static

from orkcraft.realm.orcs import RESIDENT
from orkcraft.screens.console.cards import (
    _append_tier, building_about, building_listens, building_runs, orc_about, orc_info, orc_key, orc_runs,
    road_card,
)
from orkcraft.scroll import GOAL_ICONS, GOAL_TITLES
from orkcraft.widgets.office import WordedStatic

if TYPE_CHECKING:
    from orkcraft.app import FocusState
    from orkcraft.realm.roster import Roster


class UnitInfo(Vertical):
    """The Info panel: what the selected orc, building or road is, its models, its spend.
    A building: its name with 👍 / 👎 / its goal (🪙 / ⚖️ / 💎, a click cycles it) / 🗑, why it is here, a quiet line of its runs (📜 history)
    and who it listens to (➕ adds a road)."""

    def compose(self) -> ComposeResult:
        yield WordedStatic("ℹ INFO", id="info-title", classes="console-title")
        with Vertical(id="info-building"):
            with Horizontal(id="ib-head", classes="ib-row"):
                yield WordedStatic("", id="ib-name", markup=False)
                yield WordedStatic(" 👍 ", id="ib-like", classes="ib-button")
                yield WordedStatic(" 👎 ", id="ib-dislike", classes="ib-button")
                yield WordedStatic(" ⚖️ ", id="ib-goal", classes="ib-button")
                yield WordedStatic(" 🗑 ", id="ib-demolish", classes="ib-button")
            yield WordedStatic("", id="ib-about", markup=False)
            with Horizontal(id="ib-runs-row", classes="ib-row"):
                yield WordedStatic("", id="ib-runs", markup=False)
                yield WordedStatic(" 📜 History ", id="ib-history", classes="ib-button")
            with Horizontal(id="ib-listens-row", classes="ib-row"):
                yield WordedStatic("", id="ib-listens", markup=False)
                yield WordedStatic(" ➕ Listen ", id="ib-listen", classes="ib-button")
        with Vertical(id="info-orc"):
            with Horizontal(classes="ib-row"):
                yield WordedStatic("", id="io-name", markup=False)
                yield WordedStatic(" 👍 ", id="io-like", classes="ib-button")
                yield WordedStatic(" 👎 ", id="io-dislike", classes="ib-button")
                yield WordedStatic(" 🗑 ", id="io-dismiss", classes="ib-button")
            yield WordedStatic("", id="io-about", markup=False)
            with Horizontal(classes="ib-row"):
                yield WordedStatic("", id="io-runs", markup=False)
                yield WordedStatic(" 📜 History ", id="io-history", classes="ib-button")
        yield WordedStatic("", markup=False, id="info-body")

    def update_content(self, focus_state: FocusState, roster: Roster) -> None:
        title = self.query_one("#info-title", Static)
        body = self.query_one("#info-body", Static)
        building = self.query_one("#info-building", Vertical)
        orc_box = self.query_one("#info-orc", Vertical)
        self.building_id = None
        self.orc = None
        building.display = orc_box.display = False
        body.display = True
        if focus_state.mode == "unit":
            orc = next((o for o in roster.orcs if orc_key(o) == focus_state.orc_key), None)
            title.update("ℹ INFO" if orc and orc.category == RESIDENT else f"ℹ {orc.name}" if orc else "ℹ INFO")
            if orc is not None and orc.category == RESIDENT:
                self.orc = orc
                orc_box.display, body.display = True, False
                head = Text(no_wrap=True, overflow="ellipsis")
                head.append(f"{orc.icon} ")
                _append_tier(head, orc)
                head.append(("★ " if orc.lead else "") + orc.name, style="bold")
                b = self.app.building(orc.building) if orc.building else None
                if b is not None:
                    head.append(f"  · {b.icon} {b.title}", style="dim")
                self.query_one("#io-name", Static).update(head)
                self.query_one("#io-about", Static).update(orc_about(self.app, orc))
                self.query_one("#io-runs", Static).update(orc_runs(self.app, orc))
                self.query_one("#io-dismiss").display = not orc.lead       # a steward stays
            else:
                body.update(orc_info(self.app, orc) if orc else Text("This ork is gone.", style="dim"))
        elif focus_state.mode == "building":
            bid = focus_state.building_id or ""
            b = self.app.building(bid)
            title.update("ℹ INFO")
            if b is None:
                body.update(Text("This building is gone.", style="dim"))
                return
            self.building_id = bid
            building.display, body.display = True, False
            self.query_one("#ib-name", Static).update(Text(f"{b.icon} {b.title}", style="bold"))
            spec = self.app.scroll.building(bid) if self.app.scroll is not None else None
            aim = spec.aim if spec is not None else "balance"
            self.query_one("#ib-goal", Static).update(f" {GOAL_ICONS[aim]} {GOAL_TITLES[aim]} ")
            self.query_one("#ib-about", Static).update(building_about(self.app, bid))
            self.query_one("#ib-runs", Static).update(building_runs(self.app, bid, roster))
            self.query_one("#ib-listens", Static).update(building_listens(self.app, bid))
        elif focus_state.mode == "road":
            title.update("ℹ 🛤 Road")
            body.update(road_card(self.app, focus_state.road_key or ""))
        else:
            title.update("ℹ INFO")
            body.update(Text("Select a building or an orc: what it does, its models and what it cost show here.",
                             style="dim"))

    def on_click(self, event: events.Click) -> None:
        wid = getattr(event.widget, "id", "") or ""
        orc = getattr(self, "orc", None)
        if orc is not None and wid.startswith("io-"):
            app = self.app
            if wid == "io-like":
                app.like_orc(orc)
            elif wid == "io-dislike":
                app.dislike_orc(orc)
            elif wid in ("io-dismiss", "io-history"):
                app.action_command_card("D" if wid == "io-dismiss" else "L")
            else:
                return
            event.stop()
            return
        bid = getattr(self, "building_id", None)
        if not bid or not wid.startswith("ib-"):
            return
        app = self.app
        if wid == "ib-like":
            app.like_building(bid)
        elif wid == "ib-dislike":
            app.dislike_building(bid)
        elif wid == "ib-goal":
            app.cycle_goal(bid)
        elif wid in ("ib-demolish", "ib-history", "ib-listen"):
            app.action_command_card({"ib-demolish": "X", "ib-history": "L", "ib-listen": "Y"}[wid])
        else:
            return
        event.stop()
