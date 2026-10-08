# Design — the steward at work

Status: written 2026-10-07. §2 (the model of the steward's work by the goal) is implemented; §3 (the
steward's road rules, docs/design/steward-listens.md) is implemented but for a rule's own tier.
Builds on the building goals (docs/design/retros-and-goals.md §3), the Barracks' steward
(docs/design/barracks-planning.md) and the steward's tasks (`realm/steward.py`).

## 1. Why

A steward began as the building's **upkeep**: it watches how the building is used, proposes changes,
redesigns its window, keeps its rules. Its calls are rare, made when the operator asks, and they do not
make the building's results.

That is changing. The Barracks' steward already does the work: it sorts the tasks, plans them, answers
the orks, reviews what they did and looks at the whole. The Workshop's steward takes the carts its
script hands over. Next, the Task Fields' steward loads context into to-dos and notes, and later the
steward carries out the road rules in place of agent handlers (docs/design/steward-listens.md). Then most model calls of a
building are its steward's, and the model it runs on is the building's model.

So the building's goal (🪙 thrift · ⚖️ balance · 💎 quality) has to pick the model of the steward's work,
the same way for every building, while its upkeep stays on what the operator picks.

## 2. Work and upkeep (implemented)

Every task a steward calls a model for is one of two kinds (`realm/steward.py`):

- **upkeep** — `USES`: watch, redesign, rules, roads (finding a road, writing a rule). Runs on the tier picked for it in the steward's window,
  else the default model. The goal never moves it.
- **work** — `WORK[type][use]`: what becomes the building's results. Each declares its tier under each
  goal. Today:

| Type | Work | 🪙 Thrift | ⚖️ Balance | 💎 Quality |
|---|---|---|---|---|
| Agent pool | Sort the tasks (`triage`) | light | light | light |
| | Plan the tasks (`plan`) | middle | middle | heavy |
| | Answer the orks (`answer`) | middle | middle | middle |
| | Review their work (`review`) | middle | middle | middle |
| | Look at the whole (`final`) | middle | heavy | heavy |
| Script | Take what the script hands over (`escalate`) | middle | default | heavy |
| Task board | Name the cards (`title`) | light | light | light |
| | Plan the to-dos (`plan`; its `plan_model` first) | light | light | middle |
| External listeners | Judge what it caught (`judge`) | light | light | middle |
| Transformer | The agent steps (`agent`; its `model` first) | light | default | heavy |
| Review board | Let the document go (`decide`; its `moderator` model first) | middle | default | heavy |
| Town Hall | Answer as the Warchief (`answer`) | middle | default | heavy |
| | Plan the town — the Town planner (`build`) | middle | default | heavy |

(light: laborer · middle: warrior · heavy: elder, `realm/tiers.py`.) Under ⚖️ each keeps the model it had
before; the calls that run by themselves on every card or signal (naming a card, the judge) still stop
when the Council's light model is switched off (`fast_llm`).

**Every building, checked.** A worker calls a model for its work only through `Worker.steward_runner` /
`steward_pick`; `tests/test_steward_work.py` reads every worker for a call that skips it. What is not a
building's work says why in that test (`NOT_WORK`): the Agent pool's and the Review board's orks (their
tiers are their own: realm/plans.py `GOALS`, the members' settings) and setting up a Review board's clan
(upkeep). A steward with no tool of its own (none, or `main`) runs on the main tool of the machine's
settings as the town holds them (`Worker.steward_runner`).

**One order** for every call, `steward.pick(building, use, harness, type_id=, goal=, setting=, own=)`:

1. **own** — a tier set closer to the work than the steward: a road rule's (§3); empty for now;
2. **picked** — the tier picked for this task in the steward's window;
3. **setting** — the building's own steward setting (the Agent pool's `steward`, e.g. `claude:opus`);
4. **goal** — for work only, the tier the goal in force names;
5. **default** — the CLI's own model.

**The goal in force** is `Worker.aim_now`: the building's goal, or 🪙 thrift while the camp's quota is
tight (`Worker.quota`, realm/pressure.py, measured once a minute). The Agent pool used to keep this to
itself; every worker has it now.

**What the operator sees**: the goal's hint and its toast say which models the work runs on under each
goal (`core/buildings.py` `goal_words`), and that a tight quota runs it as Thrift; in the steward's model
picker a work task's default reads `Default — Quality: Warrior`.

**Not on the steward yet** (`steward.NOT_YET`): the **Wiki** (its librarian and its review), the
**Review gate** and the **Publisher** (its overseer's scouting, mapping and repairs). They are being
reworked; until their model calls go through their steward, the goal does not reach them and **the
building is not done**. The test marks each as expected to fail, and the mark comes off with that change.

**A new work task** (the Task Fields' context loading, the steward's `listen` of §3) is one line in
`TYPE_USES` (its label) and one in `WORK` (its three tiers), and its calls go through `steward.pick` or
`steward.runner_for(..., type_id=, goal=worker.aim_now)`. Nothing else: the goal, the quota, the picker
and the hint follow.

## 3. The road rules on the goal (with docs/design/steward-listens.md)

docs/design/steward-listens.md proposes that the steward carries out a road's rule itself (a `steward`
handler kind, its new task **listen**), code first. In this model:

- **`listen` is work**, not upkeep: it runs on every cart and is where the money goes, so it goes into
  `WORK_ALL` (work every type's steward has) with its three tiers (🪙 light · ⚖️ middle · 💎 heavy) and
  through `steward.pick`; it is listed in `USES` so every steward's model picker shows it.
  `roads` (a rare setup call) stays upkeep.
- **A rule's own tier** (steward-listens.md §7, "a rule that needs a heavier tier") is `own` in §2's
  order: above the tier picked for `listen` and above the goal's.
- **Thrift pushes towards code.** The steward's "code over thinking" (steward-listens.md §2a) is what
  🪙 asks for; the retros' `chain` and `script` actions aim at a steward rule as they aim at an agent
  handler today (`optimize._parts`).
- **A tight quota** runs `listen` as 🪙 like every other work task (`Worker.aim_now`).
- **A session** that a rule keeps between carts starts afresh when its model changes — a new goal, or the
  quota turning tight — never switches the model in the middle.

## 4. Stages

1. **Done.** Work and upkeep, `steward.pick` in one order, `Worker.aim_now` / `quota` for every worker, the
   Agent pool and the Script building on it, the goal's hint and the picker's default.
2. **Done.** The Task board's naming and plan, the External listeners' judge, the Transformer's agent steps
   and the Review board's moderator, the Town Hall's Warchief and Town planner; the check over every
   worker (`tests/test_steward_work.py`).
3. The Wiki, the Review gate and the Publisher (`NOT_YET`), with their rework.
4. **Done**: `listen` as a work task (`WORK_ALL`). Not yet: a rule's own tier as `own` (steward-listens.md §7).
