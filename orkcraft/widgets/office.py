"""Widgets that speak today's words (`realm/lexicon.py`) for what the wording hook does not reach
(`tui/wording.py` rewords Textual's own content, not a rich Text): emoji stay.

    WordedStatic       a Static: its content in today's words (Garrison → Orks)
    WordedOptionList   an OptionList whose options do the same as they are added
    WordedFooter       the key footer: `📯 War Horn` → `📯 Stop all`, `🔥 Orders` → `🔥 Answers`
"""
from __future__ import annotations

from textual.widgets import Footer, OptionList, Static
from textual.widgets._footer import FooterKey
from textual.widgets.option_list import Option

from orkcraft.realm import lexicon
from orkcraft.tui.text import worded_rich


class WordedStatic(Static):
    def __init__(self, content="", *args, **kwargs) -> None:
        super().__init__(worded_rich(content), *args, **kwargs)

    def update(self, content="", *args, **kwargs) -> None:
        super().update(worded_rich(content), *args, **kwargs)


class WordedOptionList(OptionList):
    def add_options(self, items):
        items = [Option(worded_rich(o.prompt), id=o.id, disabled=o.disabled) if isinstance(o, Option)
                 else worded_rich(o) for o in items]
        return super().add_options(items)


class WordedFooter(Footer):
    def compose(self):
        for widget in super().compose():
            if isinstance(widget, FooterKey):
                widget.description = lexicon.words(widget.description)
            yield widget
