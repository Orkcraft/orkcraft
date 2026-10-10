"""Why a building has an ork (docs/design/yards.md §9): one plain line per type, what its model does that code
cannot — Info shows it beside the ork's face, apart from what the building does. A yard's (script-first) says when
its steward comes: its work is code, an ork comes only to fix it or to change it from your words."""
from __future__ import annotations

WHY: dict[str, str] = {
    "barracks": "Takes a task, plans it, writes the code or the text on its own branch, runs the checks and hands it "
                "back for review — work a script cannot plan for itself.",
    "council": "Plays each reviewer — product, architecture, security, marketing — argues the document over and "
               "writes one verdict with what to change.",
    "mine": "Searches the open web, reads the sources, cross-checks them with more than one model and writes what it "
            "found and where.",
    "scrolls": "Reads what comes in, files it into the wiki's pages, links them and keeps the pages true to each other.",
    "watchtower": "Reads each message against what you are after and lets through only what matters.",
    "fields": "Turns a card into a plan, hands it to an ork, and moves the card as the work moves.",
    "war_drum": "Prepares a meeting's brief from your notes, tasks and the wiki.",
    "forge": "Resolves a merge conflict and writes a pull request's description.",
    "town_hall": "The Warchief: answers you, plans buildings and roads for what you need, and audits the town.",
    "workshop": "Writes the building's script from your words and fixes it when it fails.",
    "custom": "Lays out the panes from your words.",
    "gramophone": "Turns a report, a summary or a wiki page into a spoken briefing.",
}

YARD = "No ork lives here: the work is code. Its steward comes only when it breaks, to fix it, or when you ask in " \
       "plain words to change what it does."


def why(type_id: str, yard: bool) -> str:
    """What the ork of a `type_id` building is for; a yard's says when one comes."""
    own = WHY.get(type_id, "")
    if yard:
        return YARD
    return own or "Does this building's work with a model: tell it in plain words what you want."
