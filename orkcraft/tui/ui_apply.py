"""A building's UI document (design/ui.py) drawn by the TUI.

The terminal has one font, so a font role becomes a text style (`tokens.json` → `tui`) and a tone the
role's colour in the look on screen (camp or office). Sizes become `fr` shares along the pane's real
parent, order is kept among siblings, a title goes on the pane's frame. A view names which widget draws
each pane of its contract (`TypedView.UI_PANES`); the TUI keeps its own nesting, so a group the
document moves elsewhere is drawn where the view has it — a GUI honours the groups as written.
"""
from __future__ import annotations

from textual.widget import Widget

from orkcraft.design import tokens, ui
from orkcraft.realm import modes


def _theme() -> str:
    return modes.current()


def _along_row(widget: Widget) -> bool:
    parent = widget.parent
    layout = getattr(getattr(parent, "styles", None), "layout", None)
    return getattr(layout, "name", "vertical") == "horizontal"


def style_pane(widget: Widget, pane: dict, sized: bool = True) -> None:
    """Font, tone, size, title and visibility of one pane, as inline styles (a later document replaces them)."""
    styles = widget.styles
    look = tokens.font(pane["font"]).get("tui", "") if pane.get("font") else ""
    if look:
        styles.text_style = look
    else:
        styles.clear_rule("text_style")
    if pane.get("tone"):
        styles.color = tokens.color(pane["tone"], _theme())
    else:
        styles.clear_rule("color")
    size = pane.get("size")
    if sized and size is not None:
        value = "auto" if size == "auto" else f"{int(size)}fr"
        if _along_row(widget):
            styles.width = value
        else:
            styles.height = value
    widget.border_title = pane.get("title") or None
    if "hidden" in pane:
        widget.display = not pane["hidden"]


def apply(view: Widget, doc: dict, panes: dict[str, str]) -> list[str]:
    """Draw `doc` over `view`: `panes` maps a pane id to the CSS selector of its widget inside the view
    ("" or a missing id: the view itself). Returns the pane ids it could not find."""
    missing: list[str] = []
    placed: list[Widget] = []
    for leaf in ui.leaves(doc):
        pid = leaf.pane["id"]
        selector = panes.get(pid, "")
        if not selector:
            style_pane(view, leaf.pane, sized=False)          # the view's size is its window's
            continue
        try:
            widget = view.query_one(selector)
        except Exception:
            missing.append(pid)
            continue
        style_pane(widget, leaf.pane)
        placed.append(widget)
    # The document's order, among widgets that share a parent.
    by_parent: dict[int, list[Widget]] = {}
    for w in placed:
        if w.parent is not None:
            by_parent.setdefault(id(w.parent), []).append(w)
    for widgets in by_parent.values():
        parent = widgets[0].parent
        current = [c for c in parent.children if c in widgets]
        if current == widgets:
            continue
        for before, w in zip(widgets, widgets[1:]):
            parent.move_child(w, after=before)
    return missing
