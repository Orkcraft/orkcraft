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

## 5. Open for engineering

1. Which buildings already give a cart an id it keeps across stops, and which start a new one (the question of
   [dogfood-logs.md](dogfood-logs.md) §3).
2. Reading "files read, tools run" out of each AI tool's trail: Claude Code's transcript has them; Codex's and agy's to
   be checked.
