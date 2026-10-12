"""One word for each concept: the Camp's when it says who, a plain one when it says what a thing does."""
from __future__ import annotations

from orkcraft.realm import catalog, lexicon, modes


def test_a_concept_has_one_word():
    assert lexicon.term("watchtower") == "External listeners"
    assert lexicon.term("road", many=True) == "roads"
    assert lexicon.term("ork") == "ork" and lexicon.term("ork", many=True) == "orks"
    assert lexicon.term("orc.town_hall") == "Warchief" and lexicon.term("town_hall") == "Town Hall"
    assert lexicon.term("chore", many=True) == "to-dos"


def test_a_building_is_named_by_what_it_does_and_its_ork_by_its_orkish_name():
    """CLAUDE.md, Wording: a building's name says what it does (Office's way), its ork keeps its Camp name —
    whatever the look."""
    keys = {t.key for t in lexicon.TERMS}
    for t in catalog.TYPES.values():
        if t.id in ("custom", "town_hall"):
            continue
        assert (t.id in keys) or (t.id == "loot" and "loot_vault" in keys), t.id
        key = "loot_vault" if t.id == "loot" else t.id
        assert lexicon.words(t.title) == lexicon.term(key), t.title
        assert lexicon.words(t.orc) == t.orc, t.orc                     # an ork's name is never rewritten
        if f"orc.{t.id}" in keys:
            assert t.orc.rstrip("s") in (lexicon.term(f"orc.{t.id}"), lexicon.term(f"orc.{t.id}", many=True).rstrip("s")), t.id


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
    assert say("Wandering Ghost") == "Wandering Ghost" and say("Inbox Ghost") == "Inbox Ghost"   # a kin, never a preview


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


def test_the_heaviest_tier_is_a_veteran_and_the_nights_council_are_the_elders():
    say = lexicon.words
    assert say("★★★ Elder — opus") == "★★★ Veteran — opus" and say("Default — Quality: Elder") == "Default — Quality: Veteran"
    assert say("The Elders advise") == "The Elders advise" and lexicon.term("elders", many=True) == "Elders"
    from orkcraft.realm import modes, tiers
    assert modes.plain(tiers.label("elder")) == "Veteran" and say("warrior") == "warrior"   # a setting's value stays


def test_the_glossary_says_what_each_word_replaced():
    rows = {key: (word, was) for key, word, was in lexicon.glossary()}
    assert rows["watchtower"] == ("External listeners", "Watchtower")
    assert rows["ork"] == ("ork", "")


def test_the_test_bench_and_its_mechanic_under_every_name_they_had():
    """The Test bench was the Alchemist's Lab and its ork a Brewmaster, then a Gearhead: the Mechanic now."""
    assert lexicon.words("Alchemist's Lab") == "Test bench"
    assert lexicon.words("Gearhead") == lexicon.words("Brewmaster") == "Mechanic"
    assert lexicon.words("🧪 Mechanic") == "🧪 Mechanic" and lexicon.words("Alchemist") == "Alchemist"
    from orkcraft.realm import catalog
    assert catalog.migrate({"id": "lab", "type": "lab", "title": "Mechanic"})["title"] == "Test bench"


def test_the_town_scroll_is_the_town_file_and_a_project_is_its_folder():
    """docs/design/projects.md §2: "Project" is the folder an orkspace works in, so the scroll is the Town file."""
    assert lexicon.term("town_scroll") == "Town file" and lexicon.term("town_scroll", many=True) == "Town files"
    assert lexicon.words("Saved to the Town Scroll") == "Saved to the Town file"
    assert lexicon.term("project") == "Project" and lexicon.term("project", many=True) == "Projects"
