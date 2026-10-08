"""The product's words: one word for each concept (CLAUDE.md, Wording).

    term("watchtower")             == "External listeners"
    term("ork", many=True)         == "orks"
    words("Spawn Ork in the Barracks") == "Add ork in the Agent pool"

Camp and Office were two vocabularies once; now there is one. A concept keeps its Camp word when it
says *who* (the orks, the Warchief, the town, its buildings and roads, renown) and takes a plain word
when it says *what a thing does, what it costs or what it risks* (a building's function, the spend,
autonomy, a file). `TERMS` is the glossary (docs/reference.md shows it as a table). A concept that
took a plain word keeps the Camp spelling it had in `was`: older code and older towns still write it,
and `words` says such a label in today's word. It is meant for the interface (titles, labels, hints,
toasts), not for what people or agents wrote.

Pure module, no Textual.
"""
from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class Term:
    key: str        # the concept: a building type id, a resource, a screen
    word: str       # its word (singular)
    many: str = ""  # its plural, when it has one
    was: str = ""   # the Camp word the code wrote for it before, when that differs ("" when the same)
    was_many: str = ""


def _t(key: str, word: str, many: str = "", was: str = "", was_many: str = "") -> Term:
    return Term(key, word, many, was, was_many)


# The glossary. Building types are keyed by their catalog id (realm/catalog.py), their resident
# orks by `orc.<type id>`; the rest by what they are.
TERMS: tuple[Term, ...] = (
    # -- who: the world keeps the Camp's words -------------------------------------------------------
    _t("ork", "ork", "orks"),
    _t("orkspace", "orkspace", "orkspaces"),
    _t("orkestration", "orkestration"),
    _t("orkestrate", "orkestrate"),
    _t("town", "town", "towns"),
    _t("building", "building", "buildings"),
    _t("hut", "hut", "huts"),
    _t("road", "road", "roads"),
    _t("cart", "cart", "carts"),
    _t("biome", "biome", "biomes"),
    _t("terrain", "terrain"),
    _t("clan", "clan"),
    _t("steward", "steward", "stewards"),
    _t("keeper", "steward", "stewards", "keeper", "keepers"),     # a building's steward, asked in plain words
    _t("war_map", "War Map"),
    _t("orc.town_hall", "Warchief"),                               # the hall's steward: the chat behind Ask me anything
    _t("town_hall", "Town Hall"),
    _t("road_planner", "Road planner"),                            # lays a road from words (realm/road_planner.py)
    _t("road_rule", "Road rule", "Road rules"),                    # what a building's steward does with a road's carts (a `steward` handler)
    _t("building_retro", "Building retro"),
    _t("ork_work", "Ork work"),                                    # the Task Fields' orks' kanban
    # -- growth (docs/design/growth.md) ---------------------------------------------------------------
    _t("renown", "Renown"),                                        # a building's level I–III (realm/growth.py)
    _t("mascot", "mascot", "mascots"),                             # the operator's, from the onboarding
    _t("deed", "deed", "deeds"),                                   # what the camp learned to do
    # -- what a thing does, costs or risks: plain words ---------------------------------------------
    _t("ghost", "preview", "", "ghost"),
    _t("loot", "output", "", "loot"),
    _t("cart_type", "content type", "content types"),            # message, doc, ticket… (realm/content.py)
    _t("fog_of_war", "new orkspace", "", "fog of war"),            # the War Map's foot: + Orkspace
    # resources (HUD)
    _t("gold", "spend", "", "gold"),
    _t("lumber", "context", "", "lumber"),
    _t("meat", "ork slots", "", "meat"),
    _t("food", "ork slots", "", "food"),
    _t("treasury", "Budget", "", "Treasury"),
    _t("logins", "Login", "Logins"),
    _t("main_tool", "Main tool", "Main tools"),                    # the AI tool decisions run on (realm/harnesses.py)                               # tokens kept on this machine (realm/logins.py)
    # screens and actions
    _t("war_horn", "Stop all", "", "War Horn"),
    _t("war_tent", "Terminals", "", "War Tent"),
    _t("orders", "Answers", "", "Orders"),
    _t("war_raven", "Phone", "Phones", "War Raven", "War Ravens"),   # a phone paired with the town (docs/design/mobile.md)
    _t("update", "update", "updates"),                             # a newer Orkcraft (core/updates.py, docs/updates.md)
    _t("critical_update", "critical update", "critical updates"),  # …that installs by itself when the town opens
    _t("standing_orders", "Instructions", "", "Standing orders"),   # what an ork is told to do
    _t("awaiting_orders", "Awaiting an answer", "", "Awaiting Orders"),
    _t("garrison", "Orks", "", "Garrison"),
    _t("spawn_ork", "Add ork", "", "Spawn Ork"),
    _t("recruit", "Add ork", "", "Recruit"),
    _t("recruiter", "Ork setup", "", "Recruiter"),
    _t("raise", "Set up", "", "Raise"),
    _t("raising", "Setting up the town", "", "Raising the town"),
    _t("town_scroll", "Project file", "Project files", "Town Scroll", "Town Scrolls"),
    _t("town_builder", "Town planner", "", "Town Builder"),
    _t("town_retro", "Weekly retro", "", "Town retro"),
    _t("retro_freedom", "Autonomy", "", "Freedom"),                 # how freely a steward applies its retro's changes
    _t("freedom.chains", "Propose only", "", "In chains"),
    _t("freedom.clock", "Apply if unanswered", "", "On the clock"),
    _t("freedom.free", "Apply at once", "", "Unchained"),
    _t("chronicles", "History", "", "Chronicles"),
    # the night's advisors were only ever "the Elders": a lone "Elder" is the heaviest model tier (realm/tiers.py)
    _t("elders", "Advisor", "Advisors", "", "Elders"),
    _t("builders", "Building designer", "", "Mason & Artisan"),
    # the Town Hall's own orks
    _t("orc.mason", "Data planner", "", "Mason"),
    _t("orc.artisan", "Layout designer", "", "Artisan"),
    _t("orc.warder", "Security reviewer", "", "Warder"),
    _t("orc.pathfinder", "Usability reviewer", "", "Pathfinder"),
    _t("orc.treasurer", "Cost reviewer", "", "Treasurer"),
    _t("council_word", "Review board", "", "Council"),
    # the Task Fields' other two parts (one board: the orks' kanban, the person's checklist, the notes)
    _t("chore", "to-do", "to-dos", "chore", "chores"),             # a to-do of the person's own
    _t("scribble", "note", "notes", "scribble", "scribbles"),       # an idea or a note on the board
    _t("card_context", "context"),                                 # a card's wiki pages, 📜 (realm/cardlore.py)
    _t("todo_plan", "plan", "plans"),                              # a to-do's steps from a light model, 🧭
    _t("personal_card", "personal"),                               # a card that never reaches a model, 🔒
    # the Wiki's librarian (docs/design/wiki-librarian.md)
    _t("quick_note", "Quick note", "Quick notes"),                  # a note left for the wiki with one click
    _t("to_discuss", "To discuss"),                                 # an item a meeting should cover
    _t("open_item", "Open item", "Open items"),                     # an item waiting for a meeting with someone
    _t("quality_check", "Quality check", "Quality checks"),         # the wiki's lint on a schedule
    _t("fold", "Fold"),                                             # a hut shows its title bar only (docs/design/folded-cards.md)
    # -- building types (catalog ids): named by what they do -----------------------------------------
    _t("pit", "Drop file here", "", "The Pit"),
    _t("watchtower", "External listeners", "External listeners", "Watchtower", "Watchtowers"),
    _t("signpost", "Router", "Routers", "Signpost", "Signposts"),
    _t("mill", "Transformer", "", "The Mill"),
    _t("horn", "Sound alerts", "", "The Horn"),
    _t("fields", "Task board", "", "Task Fields"),
    _t("barracks", "Agent pool", "", "Barracks"),
    _t("council", "Review board", "", "Clan Fire"),
    _t("war_drum", "Calendar", "", "War Drum"),
    _t("forest", "File tree", "", "File Forest"),
    _t("scrolls", "Wiki", "", "Scroll Dump"),
    _t("lake", "Inspector", "", "Lake of Insight"),
    _t("forge", "Branches & PRs", "", "The Forge"),
    _t("loot_vault", "Review gate", "", "Loot Vault"),
    _t("crag", "Metrics", "", "Tally Crag"),
    _t("catapult", "Publisher", "", "The Catapult"),
    _t("workshop", "Script", "Scripts", "Workshop", "Workshops"),
    # -- the orks who live in them: named by their role ---------------------------------------------
    _t("orc.pit", "Sorter", "", "Scavenger"),
    _t("orc.watchtower", "Listener", "", "Lookout"),
    _t("orc.signpost", "Router", "", "Grot Pointa"),
    _t("orc.mill", "Transformer", "", "Miller"),
    _t("orc.horn", "Notifier", "", "Hornblower"),
    _t("orc.fields", "Task manager", "", "Taskmaster"),
    _t("orc.barracks", "Worker", "Workers", "Grunt", "Grunts"),
    _t("orc.council", "Reviewer", "Reviewers", "Chieftain", "Chieftains"),
    _t("orc.war_drum", "Scheduler", "", "Drummer"),
    _t("orc.forest", "File picker", "", "Woodcutter"),
    _t("orc.scrolls", "Librarian", "", "Scroll Scrapper"),
    _t("orc.lake", "Inspector", "", "Seer"),
    _t("orc.forge", "Merger", "Mergers", "Smith", "Smiths"),
    _t("orc.loot", "Gatekeeper", "", "Quartermaster"),
    _t("orc.crag", "Metrics ork", "", "Crag Carver"),
    _t("orc.catapult", "Publisher", "", "Loader"),
    _t("orc.workshop", "Script runner", "", "Tinker"),
    _t("orc.custom", "Worker", "Workers", "Peon", "Peons"),
)

# Short names the interface uses for a building as well as its full title.
_ALSO = {"lake": ("Lake",), "pit": ("Pit",), "mill": ("Mill",), "horn": ("Horn",), "forge": ("Forge",),
         "catapult": ("Catapult",), "town_hall": ("Town hall",)}

# Whole phrases first: where a word for word would read wrong.
_PHRASES = {"Into the pit": "Dropped", "the Elders' advice": "the advisors' advice",
            "Not enough food": "No ork slots left", "Treasury empty": "Budget spent",
            "Halt All Operations": "Stop all", "Halt All": "Stop all"}

_BY_KEY = {t.key: t for t in TERMS}


def term(key: str, many: bool = False) -> str:
    """The word for `key`: `term("road", many=True)` → roads."""
    t = _BY_KEY[key]
    return (t.many or t.word) if many else t.word


def _pairs() -> list[tuple[str, str]]:
    """Every old spelling with today's word, longest first."""
    out: dict[str, str] = dict(_PHRASES)
    for t in TERMS:
        if not t.was and not t.was_many:
            continue
        if t.was:
            out.setdefault(t.was, t.word)
        if t.was_many:
            out.setdefault(t.was_many, t.many or t.word)
        if t.was.startswith("The "):                        # "The Mill" is also "the Mill" mid-sentence
            out.setdefault("the " + t.was[4:], t.word)
        for short in _ALSO.get(t.key, ()):
            out.setdefault(short, t.word)
    return sorted(out.items(), key=lambda kv: len(kv[0]), reverse=True)


_PAIRS = _pairs()
_TODAY = dict(_PAIRS)
_LOWER = {old.lower(): new for old, new in _PAIRS if old[:1].islower()}
_UPPER = {old.upper(): new for old, new in _PAIRS}


def _alternation() -> str:
    names: list[str] = []
    for old, _ in _PAIRS:
        names += [old, old.upper()]                         # a heading may shout: 🧌 GARRISON
        if old[:1].islower():                               # a common noun also opens a sentence
            names.append(old[:1].upper() + old[1:])
    return "|".join(re.escape(n) for n in sorted(set(names), key=len, reverse=True))


# A name stands alone: not inside another word (`ork` in `work` or in `Orkcraft`, `town` in `downtown`)
# nor in a path (`./loot/`, `loot/screenshots`, `src/roads.py`): those name files, not concepts.
_WORD = re.compile(rf"(?<![\w\-/\\.])(?:{_alternation()})(?![\w\-/\\]|\.\w)")


def _swap(m: re.Match) -> str:
    found = m.group(0)
    if found in _TODAY:
        return _TODAY[found]
    if found.isupper() and found in _UPPER:
        return _UPPER[found].upper()
    word = _LOWER[found.lower()]                            # `Chores` opening a sentence → `To-dos`
    return word[:1].upper() + word[1:]


def words(text: str) -> str:
    """`text` in today's words: `🗼 Watchtower` → `🗼 External listeners`, `3 chores` → `3 to-dos`.

    Proper names (Watchtower, War Horn) match as written; common nouns (chore, loot) in any case,
    keeping it (`Chores` → `To-dos`, `GARRISON` → `ORKS`). Emoji stay — `modes.plain` takes them off."""
    if not text:
        return text
    return _WORD.sub(_swap, str(text))


def spans(text: str) -> list[tuple[int, int, str]]:
    """Where `words` changes `text`: (start, end, today's word), left to right (for styled text)."""
    return [(m.start(), m.end(), _swap(m)) for m in _WORD.finditer(text or "")]


def table() -> list[tuple[str, str]]:
    """Every way an old word is written, with today's, longest first: what a face that cannot import
    this module (the GUI's page) needs to do `words` itself."""
    out = {}
    for old, _ in _PAIRS:
        for found in (old, old.upper(), old[:1].upper() + old[1:]):
            m = _WORD.fullmatch(found)
            if m:
                out.setdefault(found, _swap(m))
    return sorted(out.items(), key=lambda kv: len(kv[0]), reverse=True)


def glossary() -> list[tuple[str, str, str]]:
    """(key, word, the Camp word it replaced or "") for every concept, in the glossary's order."""
    return [(t.key, t.word, t.was or t.was_many) for t in TERMS]
