# Design — the steward listens: a road's rule is carried out by its building's steward

Status: proposal, written 2026-10-07. Nothing below is built yet. The first step is done: the road
planner (*Listen in words*) and the Recruiter already think on the receiver's steward's tool, at its
tier for **roads** (`realm/steward.py` `USES`, `gui/road_planner.py`, `gui/recruiter.py`).
Builds on [roads-and-orcs.md](roads-and-orcs.md) §1–3 and §5b.

## 1. Why

Today a road with a rule (*Listen with a prompt*, or a road the planner offers with a `rule`) goes to
the Recruiter, which hires a **new handler ork** into the receiver's garrison: chain, script, agent or
hybrid. When judgment is needed it is an `agent`, with its own orders, its own tools (`harness`), its
own tier and its own chronicle. So a building that listens to three things in words has a steward
plus three agents that think about the same building, each set up and paid for on its own:

- **Two heads per building.** The steward knows the building's purpose, its spend and how it is used;
  the agent handlers know their roads. Neither sees what the other knows: a rule never learns the
  building's goal, and the steward learns about an agent only from its runs.
- **Setup per ork.** Each agent handler picks its own tool and tier; the person tunes the steward in
  Info, then has to tune every handler again.
- **The roster fills with orks** that are, in the person's words, "what this building does with mail".

## 2. The model

**A building has one head: its steward.** A rule on a road is something the steward does, not an ork
of its own.

- A road with a rule is handled by the steward, on the steward's tool (its first harness step, else
  the machine's main tool) and at its tier for a new task, **listen** — "Carry out the road rules".
  `roads` (finding a road, writing a rule) and `listen` (running a rule on every cart) stay separate
  tiers: one is a rare setup call, the other runs on every cart and is where the money goes.
- The steward runs a rule with the building's purpose in its prompt (its role and orders), so every
  rule works toward the same goal.
- **Code stays code.** `chain` and `script` handlers keep their place: they have no head, they cost
  nothing, and the Recruiter still tries them first. A `hybrid`'s script escalates (exit 3) to the
  steward instead of to an agent of its own.
- **The agent handler goes away for new roads.** The Recruiter's order becomes chain → script →
  **steward** → hybrid.

## 3. Schema

The smallest change that keeps the road engine as it is: a handler of a new kind, **`steward`**.

```jsonc
"handlers": [{
  "id": "boss-mail", "name": "Boss's mail", "kind": "steward",
  "orders": "Only my boss's mail; make one to-do per letter, with the deadline if it names one.",
  "harness": [],                       // empty: the steward's tool is used
  "run": {"quiet_s": 30, "restart_on_new": true}
}]
```

- The rule is the handler's `orders`; its roads point at it as today (`road.handler`), so several roads
  under one rule, the snapshot of the latest cart of every road, the quiet period and restart on a new
  event (`realm/roads.py`) all keep working unchanged.
- `uses_model` covers `steward`; `RUN_DEFAULTS["steward"]` = the agent's.
- `_agent_thread` reads its steps from the steward for this kind: `steward.harness_for(b)` and
  `steward.tier_for(b, "listen")` in place of `orc.harness`. A building with no steward falls back to
  the main tool on its default model, as `steward.runner_for` already does.
- Old scrolls load as they are: an `agent` handler keeps running on its own tools. Nothing is migrated
  behind the person's back (§5).

Rejected: a `rule` field on each road. It loses "several roads, one rule, one snapshot", moves the run
state off the handler, and needs a second engine path.

## 4. Interface (GUI only — the TUI is deprecated)

- **Garrison.** Steward handlers are not drawn as orks. They are listed under the steward as its rules
  (`📜 Boss's mail · ⚒️ Inbox → here`), each with its roads, its last run and its spend; clicking one
  opens the rule (its words, its roads, its runs) where an ork's Info opened.
- **Info of the steward** shows the new **listen** tier next to *Watch*, *Redesign*, *Rules and
  settings* and *Roads*.
- **Hand to the steward.** An `agent` handler's Info gets one action: its orders become a steward
  rule, its own tools are dropped, its roads stay. Shown with what changes (tool, tier, the estimated
  spend per run on the steward's tier); Z takes it back like any change.
- **Wording.** "Rule" is a new concept: it gets its one word in `realm/lexicon.py` `TERMS`
  ("Road rule" / "rules"), and the GUI says it in every label.

## 5. What else changes

- **Recruiter** (`realm/recruiter.py`): offers `steward` where it offered `agent`; its contract drops
  `harness` for that kind. `agent` is still accepted when the person asks for a pipeline of tools the
  steward does not have (`[write: agy, review: claude]`) — see §7.
- **Council's Fast Path** reviews a steward rule like an agent's orders today (its text and its roads).
- **The steward's Watch** (`realm/steward.py`): demotion becomes the steward's own move — a rule it keeps
  answering the same way is replayed as a chain on its recorded runs, as now. A new finding: an `agent`
  handler whose tools are the steward's own is proposed for *Hand to the steward*.
- **Spend** is charged to the building as today and shown under the steward's *listen* tier in Info.
  The 🪙 budget check and Stop all apply unchanged (`_budget_ok`, `halt`).
- **Chronicles**: a rule's runs stay in its own chronicle (the handler id), so its history, feedback
  examples and the replay keep working.

## 6. Stages

1. **Engine.** `kind: "steward"` in `scroll.py` and the v3 schema; `realm/roads.py` runs it on the
   steward's tool and *listen* tier; `steward.USES` gets `listen`. Tests: a rule runs on the steward's
   tool and tier, a building without a steward falls back, an old `agent` handler is untouched.
2. **Recruiter and Council.** The Recruiter offers `steward`; the Fast Path reviews it. Tests on the
   contract and on a road with a rule from the planner ending as a steward rule.
3. **GUI.** Rules under the steward in the garrison, the rule's panel, *Hand to the steward*, the
   *listen* tier in Info, the lexicon term.
4. **Watch.** The steward proposes *Hand to the steward* and demotes its own rules. This document's
   status and [roads-and-orcs.md](roads-and-orcs.md) §1, §3 updated to the new model.

## 7. Open questions

- **Pipelines of tools.** An agent handler today can be `[plan: claude, write: agy, review: claude]`.
  Keep `agent` for that case only, or let the steward's own harness steps be a pipeline too?
  Proposed: keep `agent` as the explicit exception; the Recruiter says why it picked it.
- **A rule that needs a heavier tier** than the steward's *listen*. Proposed: one optional `tier` on the
  rule, shown in its panel; empty follows the steward.
- **Parallel runs.** Several rules of one steward may run at once (each its own session, as handlers
  do today). Should a building cap how many of its rules think at the same time? Proposed: no cap at
  first; the jam at the entry gate already shows when it matters.
