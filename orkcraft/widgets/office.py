"""Widgets that speak the office's words, without emoji, in the office mode (`realm/modes.py`,
`realm/lexicon.py`).

    OfficeStatic       a Static: in the office its content in office words (War Map → Workspaces), no emoji
    OfficeOptionList   an OptionList whose options do the same as they are added
    OfficeFooter       the key footer: `📯 War Horn` → `Stop all`, `🔥 Orders` → `Answers`

The content stays as given, so switching back to the camp (`rewear`) brings its words and icons back.
"""
from __future__ import annotations

from textual.widgets import Footer, OptionList, Static
from textual.widgets._footer import FooterKey
from textual.widgets.option_list import Option

from orkcraft.realm import modes
from orkcraft.tui.text import office_rich


class OfficeStatic(Static):
    def __init__(self, content="", *args, **kwargs) -> None:
        self._raw = content
        super().__init__(self._dressed(content), *args, **kwargs)

    @staticmethod
    def _dressed(content):
        return office_rich(content) if modes.office() else content

    def update(self, content="", *args, **kwargs) -> None:
        self._raw = content
        super().update(self._dressed(content), *args, **kwargs)

    def rewear(self) -> None:
        super().update(self._dressed(self._raw))


class OfficeOptionList(OptionList):
    def add_options(self, items):
        if modes.office():
            items = [Option(office_rich(o.prompt), id=o.id, disabled=o.disabled) if isinstance(o, Option)
                     else office_rich(o) for o in items]
        return super().add_options(items)


class OfficeFooter(Footer):
    def compose(self):
        for widget in super().compose():
            if isinstance(widget, FooterKey):
                widget.description = modes.footer(widget.description)
            yield widget
