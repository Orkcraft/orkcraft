"""Today's words everywhere in the terminal: one hook where Textual turns a widget's text into what
it draws, so every label, button, tab, list and dialog says a concept by its one word
(`realm/lexicon.py`: `🗼 Watchtower` → `🗼 External listeners`), without each screen asking for it.
Emoji stay: the terminal keeps the camp's look.

    install()            # once, before the app runs (OrkcraftApp does it)
    AS_WRITTEN           # the class of a widget that shows what someone wrote: it keeps its words

What people and agents wrote stays as written: a widget with the `-as-written` class (or inside one),
and Markdown, inputs, text areas and logs, are never translated. The text a widget was given is
kept as given; only what it draws changes.
"""
from __future__ import annotations

from textual import widget as _widget
from textual.content import Content, Span
from textual.widgets import Input, Log, Markdown, RichLog, Static, TextArea
from textual.widgets import _option_list, _static

from orkcraft.realm import lexicon

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


def worded_content(content: Content) -> Content:
    """`content` in today's words, each keeping the style of the one it replaces."""
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


def _wrap(visualize):
    def worded_visualize(widget, obj, *args, **kwargs):
        visual = visualize(widget, obj, *args, **kwargs)
        if isinstance(visual, Content) and not as_written(widget):
            return worded_content(visual)
        return visual
    worded_visualize.__wrapped__ = visualize
    return worded_visualize


def install() -> None:
    """Hook Textual once: a Static's content (labels, tabs, toggles), an option of a list and any
    other widget's render (buttons) pass through today's words."""
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
