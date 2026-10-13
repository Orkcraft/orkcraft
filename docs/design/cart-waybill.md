# Design — the cart's waybill: one way to see a unit of work, anywhere

Status: proposal 2026-10-13, the owner's idea; nothing built. Priority: **P0** for an ork's status naming the cart it
works on (§4), **P1** for the waybill (§2), right after a cart's id across its stops
([dogfood-logs.md](dogfood-logs.md) §3). Builds on [ork-console.md](ork-console.md) (§5 the one status, §7 the
console, §17 a cart's price and load, which this takes in), [the-score.md](the-score.md) §4a,
[lighter-buildings.md](lighter-buildings.md) §2 (long reading goes to the Inspector), `realm/call_log.py` (every
model call kept with the tool's own trail).

## 1. Why

The status and the work of orks were made one ([ork-console.md](ork-console.md)). A cart, the unit of work that
travels the roads, has no such place: what happened to it is spread over each building's own files. The owner: open a
cart at any stage, see its whole way at any time, and at each stop what context or tools were added or run for it;
and show an ork's status together with the cart it works on.

Three things, each with one way to see it:

| | what it is | where it is seen |
|---|---|---|
| an **ork** | who works (a role) | its console ([ork-console.md](ork-console.md) §7) |
| a **building** | how work flows | its card and its Info ([lighter-buildings.md](lighter-buildings.md) §2) |
| a **cart** | what is worked on | **its waybill**, in the Inspector |

## 2. The waybill (P1)

A cart's whole way, as a list of its stops, newest at the bottom; the stop it is at now open.

At each stop:

- the **building**, and the **session** of the ork that worked on it (a link to the console);
- **what was added to its context:** files read, data brought in through an MCP server or a connector;
- **what tools were run:** commands, edits, searches, as the AI tool's own trail kept by `realm/call_log.py` records
  them;
- **what went out:** the result (a diff, a text, a picture), its assumptions ([ork-console.md](ork-console.md) §4);
- **the waits** and why ([ork-console.md](ork-console.md) §19);
- **the price and the load:** 🪙 or % of the window spent here, 🪵 tokens carried in and out (this takes in
  [ork-console.md](ork-console.md) §17).

**Opened from anywhere:** a cart on a road; a result at the Review gate; a task's card; an ork's line in the console or
the ork slots list. Always the same waybill.

**In the Inspector**, whose job is reading at length: its window size when wide, the result rendered as the Inspector
renders diffs and documents.

## 3. The Review gate becomes the place of judgement

The result, its price, its one improvement ([the-score.md](the-score.md) §4a) and its waybill meet at the Review
gate: the person judges a result knowing what it cost and how it was made. It is on the core shelf
([catalog-shelves.md](catalog-shelves.md)) and in Mission 1's third quest ([first-mission.md](first-mission.md)).

## 4. An ork and its cart, both ways (P0 for the first half)

- **An ork's status names what it works on** (P0, part of the one status): "Grunt · Agent pool · running pytest · on
  «Fix the login»". The task's title is known today; the link to the waybill comes with §2.
- **A cart shows who carries it** (P1): a small head of its ork on the cart while one works on it; the cart's hint
  says the ork and its state.

## 5. A cart's id: one for life, sub-ids when it splits (decided 2026-10-13)

**What is there** (`realm/pipes.py`): every cart carries `ref`, "the thing worked on, stable across hops and rework
rounds", and `trail`, its stops (`Hop`: building, ork, kind, tokens, cost, branch, outcome, time, model, decision,
round). The Review gate already shows the trail with its total (`gui/views/loot.py` `_chain`). So `ref` is the cart's
id, and half of the waybill exists.

**The owner's rule:** a cart keeps **one id for its whole life**; where its work is split to run side by side (the
Agent pool's subtasks, the Review board's members), the parts get **sub-ids** under it.

| case | the id | today |
|---|---|---|
| **born** at an entry: a listener's signal, a dropped file, a task made by hand, a talk made a card | a new id, minted there | minted only when a building finds none (the Agent pool: `<building>:<task>`); not every entry mints one: **to check** |
| **passes on** to the next building | the same id | ✓ carried |
| **comes back** for rework | the same id, round n | ✓ `Hop.round` |
| **splits and joins**: the pool's subtasks, the board's members | sub-ids `42.1`, `42.2`…; the parent waits; the join carries `42` on, its waybill shows the parts | no sub-ids; a join keeps the **first** cart's `ref` and **drops the others'** (`realm/roads.py`): **a gap** |
| **splits for good**: a Router sending copies down two roads | sub-ids `42.1`, `42.2`, each on its own way, each knowing its parent | no sub-ids: **a gap** |
| **many become one**: a steward handling ten carts in one session, a digest | a new id, "made from 42, 43, …"; the session's cost shared evenly (§2 price, [ork-console.md](ork-console.md) §17) | **a gap** |
| **new work born of a cart**: a follow-up task | a new id, "born of 42": not a part, nothing waits on it | **to check** |

So a cart's ids form a tree, with an occasional merge. The waybill shows a cart's parent, its parts and what it was
made from, each a link to its own waybill.

## 6. Open for engineering

See the research to-do in [open-questions.md](open-questions.md) §F: which entries mint an id; sub-ids at a split;
keeping every id at a join; reading files and tools out of each AI tool's trail.
