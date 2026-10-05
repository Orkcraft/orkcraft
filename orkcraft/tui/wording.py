"""The Office's words everywhere in the terminal: one hook where Textual turns a widget's text into
what it draws, so every label, button, tab, list and dialog says the Office name of a concept
(`realm/lexicon.py`), without emoji, without each screen asking for it.

    install()            # once, before the app runs (OrkcraftApp does it)
    rewear(app)          # the mode changed: every widget draws its text again in the new words
    AS_WRITTEN           # the class of a widget that shows what someone wrote: it keeps its words

What people and agents wrote stays as written: a widget with the `-as-written` class (or inside one),
and Markdown, inputs, text areas and logs, are never translated. The text a widget was given is
kept as given; only what it draws changes, so going back to the camp brings the camp's words back.
"""
from __future__ import annotations

import re

from textual import widget as _widget
from textual.content import Content, Span
from textual.widgets import Input, Log, Markdown, RichLog, Static, TextArea
from textual.widgets import OptionList, _option_list, _static

from orkcraft.realm import lexicon, modes

AS_WRITTEN = "-as-written"
_WRITTEN_TYPES = (Markdown, Input, TextArea, Log, RichLog)

_installed = False


def as_written(widget) -> bool:
    """Does `widget` show what someone wrote (its own class, an ancestor's, or its kind)?"""
    node = widget
    while node is not None:
        if isinstance(node, _WRITTEN_TYPES) or AS_WRITTEN in getattr(node, "classes", ()):
            return True
        node = getattr(node, "parent", None)
    return False


def _swapped(content: Content) -> Content:
    found = lexicon.spans(content.plain)
    if not found:
        return content
    parts, at = [], 0
    for a, b, word in found:
        parts.append(content[at:a])
        styles = [s.style for s in content[a:b].spans]
        parts.append(Content(word, spans=[Span(0, len(word), styles[0])] if styles else None))
        at = b
    parts.append(content[at:])
    return Content.assemble(*parts)


def _unpictured(content: Content) -> Content:
    """Without emoji, as `modes.strip_emoji`: an icon goes with the space after it; `👍 3` reads `+3`."""
    plain = content.plain
    if not modes._EMOJI.search(plain):
        return content
    if plain.strip() in modes._WORDS or re.search(r"[👍👎]", plain):     # they turn into words: +1, -1, +3
        return Content(modes.strip_emoji(plain))
    parts, at = [], 0
    for m in modes._EMOJI.finditer(plain):
        a, b = m.start(), m.end()
        while b < len(plain) and plain[b] == " " and (a == 0 or plain[a - 1] in " [(" or b + 1 == len(plain)):
            b += 1
        if a > at:
            parts.append(content[at:a])
        at = max(at, b)
    parts.append(content[at:])
    return Content.assemble(*parts)


def office_content(content: Content) -> Content:
    """`content` as the office shows it: in its words (each keeping the style of the one it replaces),
    without emoji."""
    return _unpictured(_swapped(content))


def _wrap(visualize):
    def office_visualize(widget, obj, *args, **kwargs):
        visual = visualize(widget, obj, *args, **kwargs)
        if isinstance(visual, Content) and modes.office() and not as_written(widget):
            return office_content(visual)
        return visual
    office_visualize.__wrapped__ = visualize
    return office_visualize


def install() -> None:
    """Hook Textual once: a Static's content (labels, tabs, toggles), an option of a list and any
    other widget's render (buttons) pass through the office's words while the mode is office."""
    global _installed
    if _installed:
        return
    _installed = True
    _static.visualize = _wrap(_static.visualize)
    _option_list.visualize = _wrap(_option_list.visualize)     # menus and lists, option by option
    plain = _widget.visualize
    words = _wrap(plain)

    def widget_visualize(widget, obj, *args, **kwargs):
        if isinstance(widget, Static):          # its visual came through `_static` already
            return plain(widget, obj, *args, **kwargs)
        return words(widget, obj, *args, **kwargs)
    _widget.visualize = widget_visualize


def rewear(app) -> None:
    """Draw every widget's text again in the current mode's words (all screens, not only the top one)."""
    for screen in list(getattr(app, "screen_stack", ())):
        for w in screen.walk_children(with_self=False):
            if hasattr(w, "rewear"):             # an OfficeStatic keeps its own raw content
                w.rewear()
            elif isinstance(w, Static):
                w.update(w.content)
            elif isinstance(w, OptionList):
                for option in w.options:             # each option keeps its own visual
                    option._visual = None
                w._clear_caches()
                w.refresh(layout=True)
            else:
                w._layout_cache.clear()
                w.refresh(layout=True)
