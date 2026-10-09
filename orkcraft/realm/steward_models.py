"""Which model each of a steward's tasks runs on: its tasks (`USES`, `TYPE_USES`), what they are for
in the Spend window (`PURPOSE`), the tier its own tier names for its work (`WORK`, `level_of`) and `pick`,
the one order every building follows. Split out of `realm/steward.py`, which re-exports it.
"""
from __future__ import annotations

from dataclasses import dataclass

from orkcraft import scroll as ts
from orkcraft.realm import builders, tiers

# -- which model for which of its tasks ----------------------------------------------------------------

# What every steward calls a model for, and what a type's steward does besides (the Barracks' answers to
# its orks and its review of their work). Its spec keeps a tier per task (`OrcSpec.models`); a task with
# none runs on the default (the CLI's own model, or the type's setting).
#
# Two kinds (docs/design/steward-at-work.md §2): the upkeep of the building (`USES`: watch, redesign, rules,
# roads) runs on what is picked for it, else the default; the steward's WORK — what becomes the building's
# results (`WORK`) — runs, when nothing is picked, on the tier the steward's own tier names for the task (its
# column of `WORK`), and on the light column while the quota is tight (the caller says which goal is in force:
# `Worker.aim_now`). The building's goal no longer moves it (docs/design/warchief-line-and-cards.md §7).
USES = {"watch": "Watch: findings and proposals", "redesign": "Redesign the window", "keeper": "Rules and settings",
        "roads": "Roads: what it listens to", "listen": "Listen: carry out the road rules"}
TYPE_USES = {"barracks": {"triage": "Sort the tasks", "plan": "Plan the tasks", "answer": "Answer the orks' questions",
                         "review": "Review their work", "final": "Look at the whole"},
             "workshop": {"escalate": "Take what the script hands over"},
             "fields": {"title": "Name the cards", "plan": "Plan the to-dos",
                        "news": "Night round: what is new for a card", "ideas": "Night round: cleanup ideas"},
             "watchtower": {"judge": "Judge what it caught"},
             "mill": {"agent": "The agent steps"},
             "council": {"decide": "Let the document go"},
             "gramophone": {"script": "Write the script"},
             "mine": {"plan": "Plan the research", "search": "Search the web", "check": "Group the findings"},
             "town_hall": {"answer": "Answer as the Warchief", "build": "Plan the town (Town planner)"}}

# What each task's model calls are for, in the Spend window's *By purpose* (docs/design/simplify.md §2;
# `telemetry.PURPOSES`); a task not named here is `work`.
PURPOSE = {"watch": "retro", "redesign": "build", "keeper": "build", "roads": "build", "listen": "work",
           "triage": "sort", "plan": "plan", "answer": "answer", "review": "review", "final": "review",
           "title": "sort", "news": "look", "ideas": "retro", "judge": "sort", "decide": "review",
           "search": "work", "check": "work", "build": "build"}


def purpose_of(use: str, type_id: str = "") -> str:
    """The purpose of one of the steward's tasks; the Town Hall's `answer` is the Warchief's `chat`."""
    return "chat" if (type_id, use) == ("town_hall", "answer") else PURPOSE.get(use, "work")


def _g(thrift: str, balance: str, quality: str) -> dict[str, str]:
    return {"thrift": thrift, "balance": balance, "quality": quality}


# The tier of each of the steward's work tasks under each goal ("": the default model).
WORK = {"barracks": {"triage": _g("laborer", "laborer", "laborer"), "plan": _g("warrior", "warrior", "elder"),
                     "answer": _g("warrior", "warrior", "warrior"), "review": _g("warrior", "warrior", "warrior"),
                     "final": _g("warrior", "elder", "elder")},
        "workshop": {"escalate": _g("warrior", "", "elder")},
        "fields": {"title": _g("laborer", "laborer", "laborer"), "plan": _g("laborer", "laborer", "warrior"),
                   "news": _g("laborer", "laborer", "warrior"), "ideas": _g("laborer", "warrior", "elder")},
        "watchtower": {"judge": _g("laborer", "warrior", "warrior")},   # the sort reads risk and tone: warrior at most
        "mill": {"agent": _g("laborer", "", "elder")},
        "council": {"decide": _g("warrior", "", "elder")},
        "gramophone": {"script": _g("laborer", "warrior", "warrior")},
        "mine": {"plan": _g("warrior", "warrior", "elder"), "search": _g("warrior", "elder", "elder"),
                 "check": _g("laborer", "warrior", "warrior")},
        "town_hall": {"answer": _g("warrior", "", "elder"), "build": _g("warrior", "", "elder")}}
# Work every steward has, whatever its type: `listen` runs its road rules on every cart (a `steward` handler,
# docs/design/steward-listens.md) — where the money goes, so the goal picks its tier; `roads` stays upkeep.
WORK_ALL = {"listen": _g("laborer", "warrior", "elder")}
# Not on the steward yet — they call their models on their own, so the goal does not reach them, and they
# break the rule the test holds (tests/test_steward_work.py): the Wiki (scrolls: its librarian, its review),
# the Review gate (loot) and the Publisher (catapult: its overseer). Being reworked; until then not done.
NOT_YET = {"scrolls": "Wiki", "loot": "Review gate", "catapult": "Publisher"}


def uses(type_id: str) -> dict[str, str]:
    """Its tasks, the type's own last: id → what it is."""
    return {**USES, **TYPE_USES.get(type_id, {})}


def is_work(type_id: str, use: str) -> bool:
    """Whether `use` is part of the building's work (its goal picks the tier), not its upkeep."""
    return use in WORK.get(type_id, {}) or use in WORK_ALL


# The steward's tier is its own, not its building's goal's (docs/design/warchief-line-and-cards.md §6–7): a goal says
# what the retros aim at; the steward says how heavy a mind it is. Its tier picks a column of `WORK` — each task keeps
# its weight (a triage light, a plan heavier) — Novice the light one, Seasoned the middle, Veteran the heavy one.
GOAL_LEVEL = {"thrift": "laborer", "balance": "warrior", "quality": "elder"}    # a steward set before: its goal's
LEVEL_COLUMN = {"laborer": "thrift", "warrior": "balance", "elder": "quality"}


def level_of(b: ts.BuildingSpec | None) -> str:
    """The steward's own tier: the one set in Info, else the one its building's goal gave it (a town scroll written
    before the split keeps what it spent)."""
    stew = b.garrison.steward if b is not None else None
    own = stew.tier if stew is not None else ""
    return own if own in tiers.TIERS else GOAL_LEVEL.get(b.aim if b is not None else "balance", "warrior")


def column_of(b: ts.BuildingSpec | None, goal: str | None = None, tight: bool = False) -> str:
    """The column of `WORK` its steward works in: its tier's, the light one while the quota is tight (`tight`, or a
    goal in force of thrift where the building's own is not: the quota's)."""
    if tight or (goal == "thrift" and (b is None or b.aim != "thrift")):
        return "thrift"
    return LEVEL_COLUMN[level_of(b)]


def goal_tier(type_id: str, use: str, goal: str) -> str:
    """The tier a column of `WORK` names for one of the steward's work tasks (`goal`: thrift | balance | quality, the
    column — `column_of` picks it), "" for the default (and for upkeep)."""
    by_goal = WORK.get(type_id, {}).get(use) or WORK_ALL.get(use) or {}
    return by_goal.get(goal, by_goal.get("balance", ""))


def tier_for(b: ts.BuildingSpec | None, use: str) -> str:
    """The tier picked for its steward's `use` (its window's model picker), or "" for none."""
    stew = b.garrison.steward if b is not None else None
    tier = str(((stew.models if stew is not None else None) or {}).get(use) or "")
    return tier if tier in tiers.TIERS else ""


@dataclass(frozen=True)
class Pick:
    model: str           # "" for the default model
    tier: str            # the tier it came from, "" when none
    by: str              # own | picked | setting | level | default: what decided


def pick(b: ts.BuildingSpec | None, use: str, harness: str = "", *, type_id: str = "",
         goal: str | None = None, setting: str = "", own: str = "", tight: bool = False) -> Pick:
    """The model one of its steward's calls runs on (`harness`: its tool, "" or `main` for the machine's
    main tool), in one order for every building:

        own       a tier set closer to the work than the steward (a road rule's own `tier`; "" for none)
        picked    the tier picked for this task in its steward's window
        setting   the model of the building's own steward setting (the Barracks' `steward`)
        level     for its work, the tier its steward's own tier names for the task (`column_of`: light while tight)
        default   the tool's own model
    """
    for tier, by in ((own, "own"), (tier_for(b, use), "picked")):
        if tier in tiers.TIERS:
            return Pick(tiers.resolve(harness, tier), tier, by)
    if setting:
        return Pick(tiers.resolve(harness, setting), setting if setting in tiers.TIERS else "", "setting")
    tier = goal_tier(type_id, use, column_of(b, goal, tight)) if is_work(type_id, use) else ""
    if tier:
        return Pick(tiers.resolve(harness, tier), tier, "level")
    return Pick("", "", "default")


def model_for(b: ts.BuildingSpec | None, use: str, harness: str = "", *, type_id: str = "",
              goal: str | None = None) -> str:
    """The model of that task on `harness`, or "" for the default."""
    return pick(b, use, harness, type_id=type_id, goal=goal).model


def harness_for(b: ts.BuildingSpec | None) -> str:
    """The tool its steward thinks with: the one its first step names, else "" (the machine's main tool)."""
    stew = b.garrison.steward if b is not None else None
    steps = (stew.harness if stew is not None else None) or []
    return str(steps[0].get("harness") or "") if steps and isinstance(steps[0], dict) else ""


def runner_for(b: ts.BuildingSpec | None, use: str, fake: builders.Runner | None = None, *, type_id: str = "",
               goal: str | None = None, setting: str = "") -> builders.Runner:
    """The model call for one of its tasks: the test's or demo's fake as it is, else its steward's tool
    (the main one unless it names its own) on the model `pick` names."""
    if fake is not None:
        return fake
    p = pick(b, use, harness_for(b), type_id=type_id, goal=goal, setting=setting)
    return builders.tagged(builders.runner_for(harness_for(b), p.tier or p.model or None),
                           purpose_of(use, type_id), b.id if b is not None else "")


def set_models(b: ts.BuildingSpec, models: dict[str, str]) -> dict[str, str]:
    """Its steward's tier per task (an unknown task or tier is left out; empty: the default)."""
    if b.garrison.steward is None:
        raise ValueError(f"{b.title} has no steward")
    known = set(USES) | {u for t in TYPE_USES.values() for u in t}
    kept = {u: t for u, t in models.items() if u in known and t in tiers.TIERS}
    b.garrison.steward.models = kept or None
    return kept
