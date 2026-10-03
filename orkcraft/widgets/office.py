"""Widgets that lose their emoji in the hidden (office) mode (`realm/modes.py`).

    OfficeStatic       a Static: what it shows is its content without emoji while the mode is hidden
    OfficeOptionList   an OptionList whose options lose their emoji as they are added
    OfficeFooter       the key footer: `📯 War Horn` → `Stop all`, `🔥 Orders` → `Answers`

The content stays as given, so switching back to immersion (`rewear`) brings the icons back.
"""
from __future__ import annotations

from textual.widgets import Footer, OptionList, Static
from textual.widgets._footer import FooterKey
from textual.widgets.option_list import Option

from orkcraft.realm import modes


class OfficeStatic(Static):
    def __init__(self, content="", *args, **kwargs) -> None:
        self._raw = content
        super().__init__(self._dressed(content), *args, **kwargs)

    @staticmethod
    def _dressed(content):
        return modes.strip_rich(content) if modes.hidden() else content

    def update(self, content="", *args, **kwargs) -> None:
        self._raw = content
        super().update(self._dressed(content), *args, **kwargs)

    def rewear(self) -> None:
        super().update(self._dressed(self._raw))


class OfficeOptionList(OptionList):
    def add_options(self, items):
        if modes.hidden():
            items = [Option(modes.strip_rich(o.prompt), id=o.id, disabled=o.disabled) if isinstance(o, Option)
                     else modes.strip_rich(o) for o in items]
        return super().add_options(items)


class OfficeFooter(Footer):
    def compose(self):
        for widget in super().compose():
            if isinstance(widget, FooterKey):
                widget.description = modes.footer(widget.description)
            yield widget
