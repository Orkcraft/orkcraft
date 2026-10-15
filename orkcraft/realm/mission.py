"""Mission 1, Raise the camp (docs/design/first-mission.md §3): the person builds the first town, one building a quest.

The quests, their words and where the mission stands; no face, no town. core/mission.py raises the buildings, lays
the roads and watches each quest's goal; the GUI draws the quest log in the Workchief's line.

    mission.QUESTS                  the quests in their order: id, the Workchief's line, the goal, what is raised
    mission.load(root)              where the mission stands: {"on", "quest", "started", "done", "skipped", …}
    mission.save(root, state)

Quests 1 to 3½ run no model and spend nothing: the drill is a practice task, called a drill on its card and in the
Workchief's words (§2 rule 5). Quests 4 and 5 are real work (core/mission.py). A deed for each quest and Mission 1's
stage and first item: realm/growth.py.
"""
from __future__ import annotations

import json
import os
import threading
from dataclasses import dataclass
from pathlib import Path

PATH = Path(".orkcraft") / "mission.json"


@dataclass(frozen=True)
class Quest:
    id: str
    says: str            # the Workchief's line (the camp's voice may joke)
    goal: str            # what the person does, plainly
    raises: str = ""     # the building type it raises ("" none)
    press: str = ""      # the button that raises it ("" when the goal is done elsewhere)
    cost: str = "free, no model"


QUESTS = (
    Quest("board", "Boss, the work needs somewhere to lie.", "Set up the Task board: a drill cart waits on its "
          "siding.", "fields", "Set up the Task board"),
    Quest("pool", "We need hands.", "Set up the Agent pool. An ork takes the drill and asks you one question: "
          "answer it in the console.", "barracks", "Set up the Agent pool"),
    Quest("gate", "Nothing leaves without a check.", "Set up the Review gate. The drill's cart stops at its barrier: "
          "lift it to pass the cart.", "loot", "Set up the Review gate"),
    Quest("office", "Boss, in working hours the camp can look like an office.",
          "Switch to the Office look and back to Camp: the same town, the same carts and orks."),
    Quest("listen", "Listen to what goes on outside.", "Set up External listeners on GitHub: your notifications "
          "and open issues of this project become cards on the Task board (without gh: its TODO and FIXME lines). "
          "Read only.", "watchtower", "Set up External listeners", "free, read only, no model"),
    Quest("two", "Two at once.", "Two cards go to two orks at once, each on a branch of its own; both results wait "
          "at the Review gate. Nothing is merged without you.", "", "Send two cards", ""),
)
IDS = tuple(q.id for q in QUESTS)
DONE_SAYS = "The camp stands and works. The rest is yours: send cards, answer the orks, pass what is good."
LIFT = "Lift the barrier"          # quest 3's press once the drill waits at the gate: the person's pass
# The finale after quest 3 (first-mission.md §9.2): the passed drill cart rolls on and is launched, or leaves along the
# line; a drill, so nothing leaves the town and it costs nothing.
FINALE_S = 14.0
FINALE_SAYS = "The barrier is up: the drill cart rolls on. A drill, so nothing left the town."
FINALE_CHIP = "Drill · free"
# Mission 1 done (the quests up to 4; quest 5 may be put off, §3): the portrait's stage 2 opens by it (v3-prompts.md
# §14), and the first item is earned, for the inventory to read (realm/growth.py `ITEMS`).
# Quest 5 is real work: its price is said before the press (core/mission.py `two_cost`).
TWO_BUDGET_USD = 2.0
TWO_COST = ("Real work on {tool}: two runs, each on its own branch, with the Security reviewer on. No new run "
            "starts once the Agent pool has spent ${budget:.2f}; a run under way finishes. On a subscription it "
            "counts against your plan's limits.")
# Asked once, before quest 4 (open-questions.md Q16): the hooks the Security reviewer and the session log stand on.
HOOKS_SAYS = "Before real work: may the Security reviewer guard this project?"

# The drill: a practice task the Grunt "works" by a script (core/workers/barracks.py DRILL), never a model.
DRILL_TITLE = "Drill: pick the camp's banner"
DRILL_BODY = ("A drill, for practice: nothing in your project changes and no model is called. "
              "An ork takes it, asks you one question, and brings the result to the Review gate.")
DRILL_QUESTION = "Drill: which colour should the camp's banner be?"
DRILL_OPTIONS = ("Red", "Green")
DRILL_ASK = (f"Drill: I read the task; one thing is yours to choose.\n\n```asks\nQUESTION: {DRILL_QUESTION}\n"
             + "".join(f"- {o}\n" for o in DRILL_OPTIONS) + "```")
DRILL_DONE = ("Drill: the banner is painted in the colour you chose. Nothing in your project changed; "
              "this was practice.")

_LOCK = threading.Lock()


def quest(quest_id: str) -> Quest | None:
    return next((q for q in QUESTS if q.id == quest_id), None)


def after(quest_id: str) -> str:
    """The quest after this one, "" after the last."""
    i = IDS.index(quest_id) if quest_id in IDS else len(IDS)
    return IDS[i + 1] if i + 1 < len(IDS) else ""


def drill_script() -> dict:
    """The Agent pool's script for the drill (`simulated.json`'s shape): the question first; once answered (its
    prompt carries the decisions), the result."""
    return {"work": [{"match": "Decisions so far", "say": DRILL_DONE, "seconds": 1.5},
                     {"match": "Drill", "say": DRILL_ASK, "seconds": 1.5}]}


def load(root: Path) -> dict:
    try:
        data = json.loads((Path(root) / PATH).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def save(root: Path, state: dict) -> None:
    """Whole or not at all: the town's thread and a tick may both write."""
    path = Path(root) / PATH
    with _LOCK:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(path.name + ".tmp")
        tmp.write_text(json.dumps(state, indent=1), encoding="utf-8")
        os.replace(tmp, path)
