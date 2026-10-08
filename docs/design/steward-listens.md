# Design — the steward listens: a road's rule is carried out by its building's steward

Status: written 2026-10-07; stages 1–4 (§6) are built. The road planner (*Listen in words*) and the
Recruiter think on the receiver's steward's tool, at its tier for **roads**; a road rule is a `steward`
handler the steward carries out at its tier for **listen** (`realm/roads.py`, `realm/steward.py`); the
Recruiter offers it, the Council reviews it, the GUI lists it under the steward, and the steward's Watch
turns its rules into code. Not built: a rule's own tier (§7), a cap on parallel rules (§7), migrating
old `agent` handlers by itself (never: *Hand to the steward* is the person's or a proposal), and a
rule looked at for code at once when written (§2a "When": it needs recorded runs to replay on). What
was decided while building is under each section as **Built:**.
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
- **listen is the steward's work**, so the building's goal names its tier when none is picked, and a
  tight quota runs it as 🪙 (`steward.WORK` and `steward.pick`, docs/design/steward-at-work.md §2–3).
- The steward runs a rule with the building's purpose in its prompt (its role and orders), so every
  rule works toward the same goal.
- **Code stays code.** `chain` and `script` handlers keep their place: they have no head, they cost
  nothing, and the Recruiter still tries them first. A `hybrid`'s script escalates (exit 3) to the
  steward instead of to an agent of its own.
- **The agent handler goes away for new roads.** The Recruiter's order becomes chain → script →
  **steward** → hybrid.

## 2a. Code over thinking

The steward does not spend its tokens on what code can do. A rule is where a road starts, not where it
has to stay: when the steward sees that a rule only *processes* its carts (picks fields, filters,
reformats, counts, sorts by a keyword, fills a template), it writes the code for it and steps aside.

- **When.** After `MIN_EXAMPLES` recorded runs of a rule, its Watch compares inputs and outputs
  (today's repeat finding, `REPEAT_SIMILARITY`): the same shape of answer for the same shape of cart, no
  judgment in between. Also at once, when a rule is written: the Recruiter's chain → script → steward
  order already stands, and a rule it could only make a `steward` handler is looked at again here.
- **What it writes.** A **chain** when the whitelisted ops can do it (data, runs at once); a **script**
  when they cannot (today's demotion knows only chains, so this adds scripts to it). Where only part of
  the work is mechanical, a **hybrid**: the script does the routine and exits 3 for the carts it cannot
  decide, and only those reach the steward.
- **Proved before it replaces.** The new code is replayed on the rule's recorded runs (`READY_SCORE`); a
  script also passes the Council and the person's review before it ever runs, as every script does
  (`script_problem`). Until then the rule keeps running on the steward.
- **Who decides.** A chain that replays clean replaces the rule by itself when the building's Autonomy
  lets the steward change its own handlers; otherwise it is a proposal with the replay and the spend it
  saves per week ("≈ $1.80/week → $0"). A script always waits for review.
- **The rule stays as the way back.** The handler keeps its words (`orders`) next to its code: when the
  code starts failing or the carts change shape, the steward goes back to the rule and tries again later.
- **Spend is the signal.** The steward's report shows, per rule, its runs and spend on the *listen* tier;
  a rule that costs much and keeps answering alike is the first one it tries to turn into code.

**Built:** `steward.watch` finds a repeating rule (or agent) with its spend per week, costliest first,
and the model may answer `demote` with a `chain` (replayed at once) or a `script` (+ `hybrid`). A script
is never run before review: in the report *Apply* is the person's review, then the Council's Fast Path
reads it, then `replay_script` replays it on the recorded runs (a hybrid's exit 3 is left out of the
score) and it replaces the rule only when the replay is ready (`gui/steward.py` `_review_script`).
"Lets the steward change its own handlers" is the existing self-apply of the night (`core/night.py`,
`realm/evolution.py`: a `demote` is a *cheaper* change — 🕰 after its wait, ⛓️‍💥 in the next quiet hours,
with the Council and 24 h probation); a saved report now keeps its replay's `ready`, which the night
reads, and a script demotion is never self-applied. Code that came from a rule (a chain / script /
hybrid that still has `orders`) and fails ≥ 3 times, at least half its runs, gets a free `rule`
proposal: back to its words. A demotion shows `saves` (≈ $X/week → $0).

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

**Built** as written; also `OrcSpec.on_steward` (a `steward` handler, or a `hybrid` with an empty
`harness`, which escalates to the steward) and `roads.steward_steps(b, goal)`: one step on the steward's
tool with the tier `steward.pick(b, "listen", …)` names. The engine learns the goal in force from the
town (`Engine(aim=…)`, `core/delivery.py` `aim_now`: the building's worker's `aim_now`, else its own goal).
The rule's prompt names the steward, the building's purpose (the steward's role and orders) and the rule.

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

**Built:** the snapshot's `garrison` leaves rules out and lists them as `rules` (`gui/state.py`); Info's
steward part has a *Road rules* group (`js/steward.js`), a rule opens `RuleView` (`js/console.js`: words
with *Edit*, roads, tier, spend, latest runs, *Remove*); the steward's models show what the rules spent
next to *Listen*; `ork.hand` (`gui/console.py`) previews and hands over, with a checkpoint before and
after so *Revert* takes it back. The estimate per run on the steward's tier scales the agent's recorded
cost per run by a rough tier ratio (`gui/info.py` `TIER_COST`, laborer : warrior : elder ≈ 1 : 3 : 5),
said as "≈". The planner's option reads *Set up the rule*.

## 5. What else changes

- **Recruiter** (`realm/recruiter.py`): offers `steward` where it offered `agent`; its contract drops
  `harness` for that kind. `agent` is still accepted when the person asks for a pipeline of tools the
  steward does not have (`[write: agy, review: claude]`) — see §7.
- **Council's Fast Path** reviews a steward rule like an agent's orders today (its text and its roads).
- **The steward's Watch** (`realm/steward.py`): demotion becomes the steward's own move (§2a) and learns
  to write scripts and hybrids, not only chains. A new finding: an `agent` handler whose tools are the
  steward's own is proposed for *Hand to the steward*.
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
4. **Watch.** The steward turns its own rules into code (§2a: chain, script, hybrid; replayed, a chain
   applied by itself under Autonomy) and proposes *Hand to the steward*. This document's
   status and [roads-and-orcs.md](roads-and-orcs.md) §1, §3 updated to the new model.

**Built (stage 2):** the Recruiter's prompt lists chain → script → steward → hybrid → agent, describes the
steward (its name, tool and purpose) and refuses: a harness on a `steward` or a new `hybrid`, and an
`agent` of one step on the steward's own tool (`steward.stewards_own`) — "make it a steward rule". A rule
that needs no judgement still has to be a chain or a script. The Fast Path's Chief warns on a rule as on
an agent (no *why*, no quiet time, every selection wakes a model).

**Built (stage 4):** the Watch's free findings `hand` (an agent on the steward's own tool) and
`code_failing` come with their proposals without a model (`steward.free_moves`); the retros read a
rule's words as an agent's orders (`optimize.parts`).

## 7. Open questions

- **Pipelines of tools.** An agent handler today can be `[plan: claude, write: agy, review: claude]`.
  Keep `agent` for that case only, or let the steward's own harness steps be a pipeline too?
  Proposed: keep `agent` as the explicit exception; the Recruiter says why it picked it.
- **A rule that needs a heavier tier** than the steward's *listen*. *Built 2026-10-08 as proposed:*
  `OrcSpec.tier` (the scroll schema's `tier`), `roads.steward_steps(own=)`, *Model tier* in the rule's Edit
  dialog (empty: *Follow the steward*). Proposed: one optional `tier` on the
  rule, shown in its panel; empty follows the steward. It is `own` in `steward.pick`'s order, above the
  tier picked for *listen* and above the goal's.
- **Self-applied chains.** Built on the night's existing rules (🕰 after its wait, ⛓️‍💥 in quiet hours).
  Should ⛓️‍💥 apply a ready chain at once, on the watch, instead of waiting for the quiet hours?
- **Council notes on a reviewed script.** A script whose Fast Path notes are warnings (not a block) is
  still replayed and applied, since *Apply* was the person's review. Should warnings stop it and show the
  verdict first, as the Recruiter does?
- **Parallel runs.** Several rules of one steward may run at once (each its own session, as handlers
  do today). Should a building cap how many of its rules think at the same time? Proposed: no cap at
  first; the jam at the entry gate already shows when it matters.
