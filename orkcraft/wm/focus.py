"""The desktop's focus: z-order, the active window, a selected hut, and the preview that follows the selection.

A part of `Desktop` (desktop.py): its methods run with the desktop as `self`.
"""
from __future__ import annotations

import re
from pathlib import Path

from textual import events
from textual.widget import Widget
from textual.widgets import DataTable, ListView, OptionList, Select, Tree

from orkcraft.realm import pipes
from orkcraft.scroll import has_outgoing
from orkcraft.widgets.road_layer import RoadClicked
from orkcraft.wm import roadmap
from orkcraft.wm.window import Window

# Only graph nodes go to the preview; agent rows, systems and calendar events do not.
_NODE_ID = re.compile(r"^[CTP]\d+$")


def node_id_of(value: object) -> str | None:
    """Row keys, tree data and option ids → a graph node id, if they carry one."""
    if value is None:
        return None
    text = str(value).split("#", 1)[0]
    return text if _NODE_ID.match(text) else None



class FocusMixin:
    """Focus, z-order, clicks on the canvas and the preview link."""

    # -- focus & z-order ---------------------------------------------------------

    def _top_visible(self) -> Window | None:
        visible = [w for w in self.windows if self.in_view(w) and not w.hidden]
        return visible[-1] if visible else None

    def raise_window(self, w: Window) -> None:
        top = self.windows[-1]
        if w is not top:
            self.move_child(w, after=top)

    def select_hut(self, building_id: str | None) -> None:
        """Mark a collapsed hut as selected (None clears it); the building stays closed."""
        if self.selected_hut is not None and self.selected_hut in self.huts:
            self.huts[self.selected_hut].remove_class("-selected")
        self.selected_hut = building_id
        if building_id is not None and building_id in self.huts:
            self.huts[building_id].add_class("-selected")

    def set_active(self, w: Window | None) -> None:
        if self.selected_hut is not None:
            self.select_hut(None)       # opening a building or closing one ends a selection
        if w is self.active:
            return
        if self.active is not None:
            self.active.remove_class("-active")
        self.active = w
        if w is not None:
            w.add_class("-active")
        self._apply_single()  # Minimal mode shows the active window, whoever made it active
        self._apply_town()
        self.replan_roads()   # the active building's roads are drawn brighter
        self.post_message(self.LayoutChanged())

    def focus_window(self, w: Window) -> None:
        """Show, raise and focus a window (its last focused widget, else the first)."""
        if not self.in_view(w) and self.scroll is not None:
            ork = self.scroll.orkspace_of(w.window_id)
            if ork is not None:
                self.switch_orkspace(ork.id)
        if w.hidden:
            w.display = True
            self.sync_huts()
            self.replan_roads()
        self.raise_window(w)
        self.set_active(w)
        self._apply_single()
        if self.window_mode:
            return
        target = w.last_focused
        if target is None or not target.is_attached or self.window_of(target) is not w:
            # Not inside a hidden tab: focusing there would switch the tab (the Town Hall's Sessions).
            focusable = [d for d in w.query("*") if d.focusable
                         and all(a.display for a in d.ancestors_with_self if a is not w and w in a.ancestors)]
            # Prefer the list/table a window is about over filters and buttons.
            # (A Select's dropdown is an OptionList too — skip it.)
            target = next(
                (
                    d for d in focusable
                    if isinstance(d, (ListView, DataTable, Tree, OptionList))
                    and not any(isinstance(a, Select) for a in d.ancestors)
                ),
                None,
            )
            target = target or (focusable[0] if focusable else None)
        if target is not None:
            already = target.has_focus
            target.focus()
            if already:
                self.announce_selection(target)
        self.post_message(self.LayoutChanged())

    def announce_selection(self, widget: Widget) -> None:
        """Tell the linked preview what is selected in `widget`, if anything."""
        w = self.window_of(widget)
        if w is None or w.window_id == self.preview_id:
            return
        node_id = self._selected_node(widget)
        if node_id:
            self._route(widget, node_id)

    def on_descendant_focus(self, event: events.DescendantFocus) -> None:
        w = self.window_of(event.widget)
        if w is None:
            return
        if self.town_active and not w.visible:
            # Focus wandered into a collapsed building (start-up auto focus, tab): it stays a hut.
            event.widget.blur()
            self.post_message(self.CanvasClicked())
            return
        w.last_focused = event.widget
        if w is not self.active:
            self.raise_window(w)
            self.set_active(w)
        # Re-announce the current selection so the linked preview follows focus too.
        self.announce_selection(event.widget)

    @staticmethod
    def _selected_node(widget: Widget) -> str | None:
        if isinstance(widget, ListView):
            return node_id_of(getattr(widget.highlighted_child, "task_id", None))
        if isinstance(widget, DataTable) and widget.row_count:
            try:
                return node_id_of(widget.coordinate_to_cell_key(widget.cursor_coordinate).row_key.value)
            except Exception:
                return None
        if isinstance(widget, Tree) and widget.cursor_node is not None:
            return node_id_of(widget.cursor_node.data)
        if isinstance(widget, OptionList) and widget.highlighted is not None:
            try:
                return node_id_of(widget.get_option_at_index(widget.highlighted).id)
            except Exception:
                return None
        return None

    def on_window_activated(self, message: Window.Activated) -> None:
        w = message.window
        if self._rally_click(w):
            return
        if self.window_of(self.app.focused) is not w:
            # A click on the border or an unfocusable area still moves keyboard focus here.
            self.focus_window(w)
        elif w is not self.active or w is not self.windows[-1]:
            self.raise_window(w)
            self.set_active(w)

    def on_window_changed(self, message: Window.Changed) -> None:
        self.save()

    def on_window_maximize_toggled(self, message: Window.MaximizeToggled) -> None:
        self.toggle_maximize(message.window)

    def on_click(self, event: events.Click) -> None:
        # Decide by position: a click on a window's border bubbles here with a widget that is
        # not inside the window (the mouse was captured for dragging), so `event.widget` lies.
        x, y = event.screen_x, event.screen_y
        if any(not w.hidden and w.visible and w.region.contains(x, y) for w in self.windows):
            return
        if self.region.contains(x, y):
            key = roadmap.hit(self.road_paths, x - self.region.x, y - self.region.y)
            if key is not None and self.scroll is not None and self.scroll.preferences.get("roads", "faint") != "off":
                self.post_message(RoadClicked(key))
                return
            self.post_message(self.CanvasClicked())


    # -- preview link --------------------------------------------------------------

    def _from_preview(self, widget: Widget | None) -> bool:
        w = self.window_of(widget)
        return w is not None and w.window_id == self.preview_id

    def _route(self, source: Widget, value: object) -> None:
        if self._from_preview(source):
            return
        node_id = node_id_of(value)
        if not node_id:
            return
        w = self.window_of(source)
        source_id = w.window_id if w is not None else None
        self.post_message(self.NodeHighlighted(node_id, source_id=source_id))
        if source_id and self.scroll is not None:
            if has_outgoing(self.scroll, source_id, pipes.ON_SELECTION):
                self.post_message(self.PayloadEmitted(
                    pipes.Payload(kind=pipes.NODE, value=node_id, source=source_id, mode=pipes.ON_SELECTION)
                ))

    def on_list_view_highlighted(self, event: ListView.Highlighted) -> None:
        self._route(event.list_view, getattr(event.item, "task_id", None))

    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        self._route(event.data_table, event.row_key.value if event.row_key is not None else None)

    def on_tree_node_highlighted(self, event: Tree.NodeHighlighted) -> None:
        w = self.window_of(event.node.tree)
        if w is not None and w.window_id == "loot":
            node_data = event.node.data
            if hasattr(node_data, "path"):
                p = Path(node_data.path)
                if p.is_file():
                    if self.scroll is not None:
                        if has_outgoing(self.scroll, "loot", pipes.ON_SELECTION):
                            repo_root = getattr(self.app, "repo_root", None)
                            if repo_root is not None:
                                try:
                                    rel = str(p.resolve().relative_to(Path(repo_root).resolve()))
                                except ValueError:
                                    rel = str(p)
                                self.post_message(self.PayloadEmitted(
                                    pipes.Payload(kind=pipes.FILE, value=rel, source="loot", mode=pipes.ON_SELECTION)
                                ))
        self._route(event.node.tree, event.node.data)

    def on_option_list_option_highlighted(self, event: OptionList.OptionHighlighted) -> None:
        self._route(event.option_list, event.option_id)
