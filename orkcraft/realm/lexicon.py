"""The product's words in each mode: Camp says them as a game, Office as a work tool.

    term("watchtower")             == "Watchtower"            # the current mode's word
    term("watchtower", OFFICE)     == "External listeners"
    office_words("Spawn Ork in the Barracks") == "Add agent in the Agent pool"

One concept, two words: the Watchtower of the camp is the External listeners of the office, an ork
is an agent, a road a link. `TERMS` is the glossary (docs/reference.md shows it as a table);
`office_words` says a label of the interface in the office's words. It is meant for the interface
(titles, labels, hints, toasts), not for what people or agents wrote.

Pure module, no Textual. The mode itself lives in `realm/modes.py`.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

CAMP, OFFICE = "camp", "office"


@dataclass(frozen=True)
class Term:
    key: str        # the concept: a building type id, a resource, a screen
    camp: str       # its word in the camp (singular)
    office: str     # its word in the office (singular)
    camp_many: str = ""     # plurals, when the word has one ("" when it has none)
    office_many: str = ""


def _t(key: str, camp: str, office: str, camp_many: str = "", office_many: str = "") -> Term:
    return Term(key, camp, office, camp_many, office_many)


# The glossary. Building types are keyed by their catalog id (realm/catalog.py), their resident
# orks by `orc.<type id>`; the rest by what they are.
TERMS: tuple[Term, ...] = (
    # -- the world ----------------------------------------------------------------------------------
    _t("ork", "ork", "agent", "orks", "agents"),
    _t("orkspace", "orkspace", "workspace", "orkspaces", "workspaces"),
    _t("orkestration", "orkestration", "coordination"),
    _t("orkestrate", "orkestrate", "coordinate"),
    _t("town", "town", "project", "towns", "projects"),
    _t("building", "building", "module", "buildings", "modules"),
    _t("hut", "hut", "tile", "huts", "tiles"),
    _t("road", "road", "link", "roads", "links"),
    _t("cart", "cart", "message", "carts", "messages"),
    _t("ghost", "ghost", "preview"),
    _t("loot", "loot", "output"),
    _t("biome", "biome", "background"),
    _t("terrain", "terrain", "background"),
    # -- resources (HUD) ----------------------------------------------------------------------------
    _t("gold", "gold", "spend"),
    _t("lumber", "lumber", "context"),
    _t("meat", "meat", "agent slots"),
    _t("food", "food", "agent slots"),
    _t("treasury", "Treasury", "Budget"),
    # -- screens and actions ------------------------------------------------------------------------
    _t("war_map", "War Map", "Workspaces"),
    _t("war_horn", "War Horn", "Stop all"),
    _t("war_tent", "War Tent", "Terminals"),
    _t("orders", "Orders", "Answers"),
    _t("awaiting_orders", "Awaiting Orders", "Awaiting an answer"),
    _t("garrison", "Garrison", "Agents"),
    _t("spawn_ork", "Spawn Ork", "Add agent"),
    _t("recruit", "Recruit", "Add agent"),
    _t("recruiter", "Recruiter", "Agent setup"),
    _t("raise", "Raise", "Set up"),
    _t("raising", "Raising the town", "Setting up the project"),
    _t("town_scroll", "Town Scroll", "Project file", "Town Scrolls", "Project files"),
    _t("town_builder", "Town Builder", "Project planner"),
    _t("town_retro", "Town retro", "Weekly review"),
    _t("building_retro", "Building retro", "Module review"),
    _t("chronicles", "Chronicles", "History"),
    _t("elders", "Elder", "Advisor", "Elders", "Advisors"),
    _t("steward", "steward", "coordinator", "stewards", "coordinators"),
    _t("builders", "Mason & Artisan", "Module designer"),
    # -- the Town Hall's own orks -------------------------------------------------------------------
    _t("orc.mason", "Mason", "Data planner"),
    _t("orc.artisan", "Artisan", "Layout designer"),
    _t("orc.warder", "Warder", "Security reviewer"),
    _t("orc.pathfinder", "Pathfinder", "Usability reviewer"),
    _t("orc.treasurer", "Treasurer", "Cost reviewer"),
    _t("council_word", "Council", "Review board"),
    _t("clan", "clan", "team"),
    # -- building types (catalog ids) ---------------------------------------------------------------
    _t("pit", "The Pit", "Inbox"),
    _t("watchtower", "Watchtower", "External listeners", "Watchtowers", "External listeners"),
    _t("signpost", "Signpost", "Router", "Signposts", "Routers"),
    _t("mill", "The Mill", "Transformer"),
    _t("horn", "The Horn", "Sound alerts"),
    _t("fields", "Task Fields", "Task board"),
    _t("barracks", "Barracks", "Agent pool"),
    _t("council", "Clan Fire", "Review board"),
    _t("war_drum", "War Drum", "Calendar"),
    _t("forest", "File Forest", "File tree"),
    _t("scrolls", "Scroll Dump", "Wiki"),
    _t("lake", "Lake of Insight", "Inspector"),
    _t("forge", "The Forge", "Branches & PRs"),
    _t("loot_vault", "Loot Vault", "Review gate"),
    _t("crag", "Tally Crag", "Metrics"),
    _t("catapult", "The Catapult", "Publisher"),
    _t("town_hall", "Town Hall", "Control panel"),
    _t("workshop", "Workshop", "Script", "Workshops", "Scripts"),
    # -- the orks who live in them ------------------------------------------------------------------
    _t("orc.pit", "Scavenger", "Sorter"),
    _t("orc.watchtower", "Lookout", "Listener"),
    _t("orc.signpost", "Grot Pointa", "Router"),
    _t("orc.mill", "Miller", "Transformer"),
    _t("orc.horn", "Hornblower", "Notifier"),
    _t("orc.fields", "Taskmaster", "Task manager"),
    _t("orc.barracks", "Grunt", "Worker", "Grunts", "Workers"),
    _t("orc.council", "Chieftain", "Reviewer", "Chieftains", "Reviewers"),
    _t("orc.war_drum", "Drummer", "Scheduler"),
    _t("orc.forest", "Woodcutter", "File picker"),
    _t("orc.scrolls", "Scroll Scrapper", "Wiki writer"),
    _t("orc.lake", "Seer", "Inspector"),
    _t("orc.forge", "Smith", "Merger", "Smiths", "Mergers"),
    _t("orc.loot", "Quartermaster", "Gatekeeper"),
    _t("orc.crag", "Crag Carver", "Metrics agent"),
    _t("orc.catapult", "Loader", "Publisher"),
    _t("orc.workshop", "Tinker", "Script runner"),
    _t("orc.custom", "Peon", "Worker", "Peons", "Workers"),
)

# Short names the interface uses for a building as well as its full title.
_ALSO = {"lake": ("Lake",), "pit": ("Pit",), "mill": ("Mill",), "horn": ("Horn",), "forge": ("Forge",),
         "catapult": ("Catapult",), "town_hall": ("Town hall",)}

# Whole phrases first: where a word for word would read wrong ("an orkspace" → "a workspace"). The
# camp is the town, but Camp alone is the mode's name and stays; so does the F10 line that tells what
# the Camp looks like (it is about the camp, in any mode).
_PHRASES = {"the camp": "the project", "an orkspace": "a workspace", "Punk ork": "Expert", "an ork": "an agent",
            "Into the pit": "To the inbox", "the Elders' advice": "the advisors' advice",
            "Not enough food": "No agent slots left", "Treasury empty": "Budget spent",
            "Halt All Operations": "Stop all", "Halt All": "Stop all", "Awaiting Orders": "Awaiting an answer",
            "WAR MAP (Orkspaces)": "WORKSPACES", "War Map (Orkspaces)": "Workspaces",
            "the town of orks: ASCII, fire, gold and lumber": "the town of orks: ASCII, fire, gold and lumber"}

_BY_KEY = {t.key: t for t in TERMS}


def term(key: str, mode: str | None = None, many: bool = False) -> str:
    """The word for `key` in `mode` (the current one when None): `term("road", OFFICE, many=True)` → links."""
    if mode is None:
        from orkcraft.realm import modes          # the mode lives there; it imports us
        mode = modes.current()
    t = _BY_KEY[key]
    if mode == OFFICE:
        return (t.office_many or t.office) if many else t.office
    return (t.camp_many or t.camp) if many else t.camp


def _pairs() -> list[tuple[str, str]]:
    out: dict[str, str] = dict(_PHRASES)
    for t in TERMS:
        out.setdefault(t.camp, t.office)
        if t.camp_many:
            out.setdefault(t.camp_many, t.office_many or t.office)
        if t.camp.startswith("The "):                       # "The Mill" is also "the Mill" mid-sentence
            out.setdefault("the " + t.camp[4:], t.office)
        for short in _ALSO.get(t.key, ()):
            out.setdefault(short, t.office)
    return sorted(out.items(), key=lambda kv: len(kv[0]), reverse=True)


_PAIRS = _pairs()
_OFFICE = dict(_PAIRS)
_LOWER = {camp.lower(): office for camp, office in _PAIRS if camp[:1].islower()}
_UPPER = {camp.upper(): office for camp, office in _PAIRS}


def _alternation() -> str:
    names: list[str] = []
    for camp, _ in _PAIRS:
        names += [camp, camp.upper()]                       # a heading may shout: 🧌 GARRISON
        if camp[:1].islower():                              # a common noun also opens a sentence
            names.append(camp[:1].upper() + camp[1:])
    return "|".join(re.escape(n) for n in sorted(set(names), key=len, reverse=True))


# A name stands alone: not inside another word (`ork` in `work` or in `Orkcraft`, `town` in `downtown`)
# nor in a path (`./loot/`, `loot/screenshots`, `src/roads.py`): those name files, not concepts.
_WORD = re.compile(rf"(?<![\w\-/\\.])(?:{_alternation()})(?![\w\-/\\]|\.\w)")


def _swap(m: re.Match) -> str:
    found = m.group(0)
    if found in _OFFICE:
        return _OFFICE[found]
    if found.isupper() and found in _UPPER:
        return _UPPER[found].upper()
    office = _LOWER[found.lower()]                          # `Orks` opening a sentence → `Agents`
    return office[:1].upper() + office[1:]


def office_words(text: str) -> str:
    """`text` in the office's words: `🗼 Watchtower` → `🗼 External listeners`, `3 orks` → `3 agents`.

    Proper names (Watchtower, War Map) match as written; common nouns (ork, road) in any case,
    keeping it (`Orks` → `Agents`, `ORKS` → `AGENTS`). Emoji stay — `modes.text` takes them off."""
    if not text:
        return text
    return _WORD.sub(_swap, str(text))


def spans(text: str) -> list[tuple[int, int, str]]:
    """Where `office_words` changes `text`: (start, end, office word), left to right (for styled text)."""
    return [(m.start(), m.end(), _swap(m)) for m in _WORD.finditer(text or "")]


def table() -> list[tuple[str, str]]:
    """Every way a camp word is written, with its office word, longest first: what a face that cannot
    import this module (the GUI's page) needs to do `office_words` itself."""
    out = {}
    for camp, _ in _PAIRS:
        for found in (camp, camp.upper(), camp[:1].upper() + camp[1:]):
            m = _WORD.fullmatch(found)
            if m:
                out.setdefault(found, _swap(m))
    return sorted(out.items(), key=lambda kv: len(kv[0]), reverse=True)


def glossary() -> list[tuple[str, str, str]]:
    """(key, camp, office) for every concept, in the glossary's order (for docs and the GUI)."""
    return [(t.key, t.camp, t.office) for t in TERMS]
