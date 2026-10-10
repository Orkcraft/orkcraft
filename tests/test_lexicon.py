"""One word for each concept: the Camp's when it says who, a plain one when it says what a thing does."""
from __future__ import annotations

from orkcraft.realm import catalog, lexicon, modes


def test_a_concept_has_one_word():
    assert lexicon.term("watchtower") == "External listeners"
    assert lexicon.term("road", many=True) == "roads"
    assert lexicon.term("ork") == "ork" and lexicon.term("ork", many=True) == "orks"
    assert lexicon.term("orc.town_hall") == "Warchief" and lexicon.term("town_hall") == "Town Hall"
    assert lexicon.term("chore", many=True) == "to-dos"


def test_every_building_type_and_its_ork_are_named_by_what_they_do():
    keys = {t.key for t in lexicon.TERMS}
    for t in catalog.TYPES.values():
        if t.id in ("custom", "town_hall"):
            continue
        assert (t.id in keys) or (t.id == "loot" and "loot_vault" in keys), t.id
        assert lexicon.words(t.title) != t.title, t.title
        assert lexicon.words(t.orc) != t.orc, t.orc


def test_an_old_camp_spelling_reads_in_todays_word():
    say = lexicon.words
    assert say("Spawn Ork") == "Add ork"
    assert say("3 orks in the Barracks") == "3 orks in the Agent pool"
    assert say("Orks wait on the road") == "Orks wait on the road"            # who keeps its word
    assert say("🧌 GARRISON") == "🧌 ORKS"
    assert say("No buildings in this orkspace yet.") == "No buildings in this orkspace yet."
    assert say("Ask the Warchief") == "Ask the Warchief"
    assert say("Standing orders & trigger") == "Instructions & trigger"
    assert say("📯 War Horn") == "📯 Stop all" and say("Not enough food") == "No ork slots left"


def test_a_word_inside_another_stays():
    say = lexicon.words
    assert say("Orkcraft: work downtown, a roadmap") == "Orkcraft: work downtown, a roadmap"
    assert say("the goldfish") == "the goldfish"


def test_plain_says_todays_words_without_emoji():
    assert modes.plain("🗼 Watchtower") == "External listeners"
    assert modes.plain("📯 War Horn") == "Stop all" and modes.plain("🔥 Orders") == "Answers"
    assert modes.plain("🧌 3 orks") == "3 orks"


def test_the_gui_gets_every_spelling():
    table = dict(lexicon.table())
    assert table["Watchtower"] == "External listeners" and table["Chores"] == "To-dos"
    assert table["GARRISON"] == "ORKS"
    assert "orks" not in table and "Warchief" not in table and "road" not in table   # nothing to change


def test_a_path_is_not_a_concept():
    say = lexicon.words
    assert say("./loot/ and loot/screenshots, src/roads.py") == "./loot/ and loot/screenshots, src/roads.py"
    assert say("the loot.") == "the output."


def test_the_heaviest_tier_stays_elder_and_the_night_s_elders_are_advisors():
    say = lexicon.words
    assert say("★★★ Elder — opus") == "★★★ Veteran — opus" and say("Default — Quality: Elder") == "Default — Quality: Veteran"
    assert say("The Elders advise") == "The Advisors advise" and say("the Elders' advice") == "the advisors' advice"
    assert ("Elder", "Advisor") not in lexicon.table()
    from orkcraft.realm import modes, tiers
    assert modes.plain(tiers.label("elder")) == "Veteran" and say("warrior") == "warrior"   # a setting's value stays


def test_the_glossary_says_what_each_word_replaced():
    rows = {key: (word, was) for key, word, was in lexicon.glossary()}
    assert rows["watchtower"] == ("External listeners", "Watchtower")
    assert rows["ork"] == ("ork", "")


def test_the_test_bench_reads_as_itself_under_every_name_it_had():
    """The Mechanic today, the Alchemist's Lab with a Brewmaster before: older towns keep those titles."""
    assert lexicon.words("🧪 Mechanic") == "🧪 Test bench"
    assert lexicon.words("Alchemist's Lab") == "Test bench"
    assert lexicon.words("Gearhead") == lexicon.words("Brewmaster") == "Tester"
    assert lexicon.words("a mechanic, a reference") == "a mechanic, a reference"
