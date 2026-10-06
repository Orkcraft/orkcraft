"""Every concept has two words: the camp's (a game) and the office's (a work tool)."""
from __future__ import annotations

import pytest
from rich.text import Text

from orkcraft.realm import catalog, lexicon, modes
from orkcraft.tui.text import office_rich


@pytest.fixture(autouse=True)
def camp():
    modes.set_current(modes.CAMP)
    yield
    modes.set_current(modes.CAMP)


def test_a_concept_has_a_word_per_mode():
    assert lexicon.term("watchtower", modes.CAMP) == "Watchtower"
    assert lexicon.term("watchtower", modes.OFFICE) == "External listeners"
    assert lexicon.term("road", modes.OFFICE, many=True) == "links"
    assert lexicon.term("ork") == "ork"
    modes.set_current(modes.OFFICE)
    assert lexicon.term("ork") == "agent"


def test_every_building_type_and_its_ork_have_an_office_name():
    keys = {t.key for t in lexicon.TERMS}
    for t in catalog.TYPES.values():
        if t.id == "custom":
            continue
        assert (t.id in keys) or (t.id == "loot" and "loot_vault" in keys), t.id
        assert lexicon.office_words(t.title) != t.title, t.title
        assert lexicon.office_words(t.orc) != t.orc, t.orc


def test_the_office_says_the_interface_in_its_words():
    say = lexicon.office_words
    assert say("Spawn Ork") == "Add agent"
    assert say("3 orks in the Barracks") == "3 agents in the Agent pool"
    assert say("Orks wait on the road") == "Agents wait on the link"
    assert say("🧌 GARRISON") == "🧌 AGENTS"
    assert say("No buildings in this orkspace yet.") == "No blocks in this workspace yet."
    assert say("New in an orkspace") == "New in a workspace"
    assert say("Audit the camp") == "Audit the project"
    assert say("Standing orders & trigger") == "Instructions & trigger"


def test_a_word_inside_another_and_the_mode_names_stay():
    say = lexicon.office_words
    assert say("Orkcraft: work downtown, a roadmap") == "Orkcraft: work downtown, a roadmap"
    assert say("🧌 Camp · 👔 Office") == "🧌 Camp · 👔 Office"


def test_modes_text_speaks_the_office_without_emoji_and_keeps_the_camp():
    assert modes.text("🗼 Watchtower") == "🗼 Watchtower"
    assert modes.text("🗼 Watchtower", modes.OFFICE) == "External listeners"
    assert modes.words("🗼 Watchtower", modes.OFFICE) == "🗼 External listeners"
    assert modes.footer("📯 War Horn", modes.OFFICE) == "Stop all"
    assert modes.footer("🔥 Orders", modes.OFFICE) == "Answers"


def test_styled_text_keeps_its_style_in_office_words():
    t = Text("▶ ")
    t.append("🌾 Task Fields", style="bold red")
    out = office_rich(t)
    assert out.plain == "▶ Task board" and any("red" in str(sp.style) for sp in out.spans)


def test_the_gui_gets_every_spelling():
    table = dict(lexicon.table())
    assert table["Watchtower"] == "External listeners" and table["orks"] == "agents" and table["Orks"] == "Agents"
    assert table["ROADS"] == "LINKS"


def test_a_path_is_not_a_concept():
    say = lexicon.office_words
    assert say("./loot/ and loot/screenshots, src/roads.py") == "./loot/ and loot/screenshots, src/roads.py"
    assert say("the loot.") == "the output."


@pytest.mark.asyncio
async def test_every_widget_says_the_office_words_but_what_was_written_stays():
    from textual.app import App
    from textual.widgets import Button, OptionList, Static
    from orkcraft.tui import wording

    wording.install()

    class Probe(App):
        def compose(self):
            yield Static("🧌 Garrison of the Barracks", id="label")
            yield Button("Spawn Ork", id="button")
            yield OptionList("Save Town Scroll", id="options")
            yield Static("my notes about the Barracks", id="note", classes=wording.AS_WRITTEN)

    app = Probe()
    async with app.run_test() as pilot:
        shown = lambda sel: app.query_one(sel)._render().plain if not isinstance(app.query_one(sel), Static) \
            else app.query_one(sel).visual.plain
        assert shown("#label") == "🧌 Garrison of the Barracks"
        modes.set_current(modes.OFFICE)
        wording.rewear(app)
        await pilot.pause()
        assert shown("#label") == "Agents of the Agent pool"
        assert "Add agent" in shown("#button")
        assert "Project file" in str(app.query_one("#options").render_line(0).text)
        assert shown("#note") == "my notes about the Barracks"
        modes.set_current(modes.CAMP)
        wording.rewear(app)
        await pilot.pause()
        assert shown("#label") == "🧌 Garrison of the Barracks" and "Spawn Ork" in shown("#button")
