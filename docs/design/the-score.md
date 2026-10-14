# Design — the game's score: less wood and limit per result

Status: proposal 2026-10-13, the owner's idea; nothing built. Priority **P1**: it needs the sessions' numbers
([ork-console.md](ork-console.md), [dogfood-logs.md](dogfood-logs.md)), and a person cares about it from about the
third day, when the limits are met; the first session is about a first win ([first-mission.md](first-mission.md)).
Builds on [script-first.md](script-first.md) (the cheapest thing that works), [town-hall-roles.md](town-hall-roles.md)
(the Treasurer), [connections.md](connections.md) §3 and [cut-list.md](cut-list.md) (the offers), [growth.md](growth.md).

## 1. The idea

Say plainly, and show, that the game's task is to **spend less 🪵 wood (tokens) and less limit or money**. The rule
"the cheapest thing that works wins" becomes what the person plays.

## 2. The score: per result, never in total

Spending less in total is won by doing nothing. As in a strategy game's economy, what counts is what the gold built.

- **The score:** the wood and the limit spent **per accepted result**: a task moved to Done, a cart passed at the
  Review gate. On a subscription the limit is a **% of the window**; on an API key it is **$**; the wood (tokens) is
  the same for both.
- **Quality guards it:** a cheaper week does not count if the 👎 or the reworks per result went up.
- **A trend, not a number:** "per result, 12 % less than last week", by town and by building.
- **Shown quietly:** a small arrow beside 🪵 in the HUD, in a calm colour; never louder than 🔥 or ❓
  ([ork-console.md](ork-console.md) §5).
- **Growth:** a deed for a lean week ([growth.md](growth.md)), a building's level by its cost per result.

## 3. The audit, more often, and cheap

- **The rules** of the audit (`realm/audit.py`, code, free) run as the town changes: a road laid, a building's week
  closed, a cost per result that rose. Free, so they may run often.
- **Ideas a model has to think up** cost wood themselves; run often, they would eat the score they are meant to
  improve. They stay in the night council ([cut-list.md](cut-list.md) §3), once a night at most, off by default in a
  new town.

## 4. 💡 Improvements: one list in the HUD

A small count beside 🪙, top right: `💡 2`. No toast, no sound, never in the way of 🔥 or ❓. A click opens the list:

- each item says **what to change, where, and what it saves**: "Mail triage: a Router before the agent, about −30 %
  wood per cart", with **Apply** and **Dismiss**, signed by its role (the Treasurer for money and limits, the Mason for
  a script, the Pathfinder for a road);
- a dismissed item does not come back unless its saving doubles;
- **one list for every offer** the docs put in separate places so far: the night's work turned on (the Treasurer,
  [cut-list.md](cut-list.md) §2), a connection moved from MCP to a token ([connections.md](connections.md) §3), the
  audit's findings (§3), the night council's proposals for buildings and for the way of working.

### 4a. Beside the result it is about (the owner, 2026-10-13)

The same item also shows **where the person judges the result**: at the Review gate, beside the cart it is about.
"This cart cost $0.31 (or 2 % of the window), three times its road's usual; a Router before the agent would save
about 30 %", with **Apply** and **Dismiss**. The rule of [ork-console.md](ork-console.md) §21 again: shown on what it
is about.

- **One item, two places:** the 💡 list holds every item; a result shows only its own. Applied or dismissed in one
  place, it is gone from both.
- **At most one per result**, and only when the result cost clearly more than its road's usual, or a known saving
  fits it. Never on every result.
- **Needs each cart's cost**, so the id a cart keeps across its stops ([dogfood-logs.md](dogfood-logs.md) §3, P1)
  comes first; this follows it, P1.

## 5. How we know

- From the local event log ([dogfood-logs.md](dogfood-logs.md)): items shown, applied, dismissed; the cost per result
  before and after an applied item.
- The owner's own game: does the cost per result fall over four weeks, and was it the 💡 list that made it fall?

## 6. Built (I1, 2026-10-14) and what waits

**Built:** `realm/score.py` — the wood (tokens) and $ per accepted result (a Review gate's pass, a task done; a launch is
not a judgement) this week against the last, from the local event log's `result_built` lines, which now keep the
tokens and spend of the cart's trail when the result lands (`core/last_look.py`); the guard from the feedback log
(👎 and send-backs per result). The HUD shows it beside the context (js/score.js); a launched cart flies over the wall
with its tokens, and its $ where its tool bills by key (js/camp/carts.js). **Only what is recorded is shown:** a part
never recorded is left out, and the hint says what is not measured yet (the PM, overnight).

**Later: a cart's share of the window.** No recorder exists: the limits give only the remaining fraction of each
provider's window. The recorder to build: that fraction read before and after a run, per provider, kept on the run's
hop like its tokens; then the flying cart and the HUD show it.
