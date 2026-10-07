"""The terminal says today's words (`realm/lexicon.py`) and keeps its icons; what was written stays."""
from __future__ import annotations

import pytest
from rich.text import Text

from orkcraft.tui.text import worded_rich


def test_styled_text_keeps_its_style_in_todays_words():
    t = Text("▶ ")
    t.append("🌾 Task Fields", style="bold red")
    out = worded_rich(t)
    assert out.plain == "▶ 🌾 Task board" and any("red" in str(sp.style) for sp in out.spans)
    assert worded_rich("📯 War Horn") == "📯 Stop all"
    assert worded_rich(None) is None


@pytest.mark.asyncio
async def test_every_widget_says_todays_words_but_what_was_written_stays():
    from textual.app import App
    from textual.widgets import Button, OptionList, Static

    from orkcraft.tui import wording
    from orkcraft.widgets.office import WordedStatic

    wording.install()

    class Probe(App):
        def compose(self):
            yield Static("🧌 Garrison of the Barracks", id="label")
            yield Button("Spawn Ork", id="button")
            yield OptionList("Save Town Scroll", id="options")
            yield Static("my notes about the Barracks", id="note", classes=wording.AS_WRITTEN)
            yield WordedStatic(Text("🗼 Watchtower", style="bold"), id="rich")

    app = Probe()
    async with app.run_test() as pilot:
        await pilot.pause()
        shown = lambda sel: app.query_one(sel)._render().plain if not isinstance(app.query_one(sel), Static) \
            else app.query_one(sel).visual.plain                                  # noqa: E731
        assert shown("#label") == "🧌 Orks of the Agent pool"
        assert "Add ork" in shown("#button")
        assert "Save Project file" in str(app.query_one("#options").render_line(0).text)
        assert shown("#note") == "my notes about the Barracks"
        assert shown("#rich") == "🗼 External listeners"
