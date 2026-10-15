# Design — the Town Hall's roles: one expertise, one ork

Status: decided 2026-10-12 with the owner, nothing built. Priority **P1** ([ork-console.md](ork-console.md) §11): before
the ork's Info ships, or it ships eleven role cards. Builds on [ork-console.md](ork-console.md) §2 (an ork is a role,
its runs are sessions), [improve-buildings.md](improve-buildings.md) §8 (the Mechanic and the Alchemist on the
Council), `realm/builders.py`, `realm/audit.py`, `realm/fastpath.py`, `realm/elders.py`.

## 1. Why

The Town Hall has four mechanisms, each with its own names:

| mechanism | who | how it works |
|---|---|---|
| the building designer (`realm/builders.py`) | Mason → Artisan | two model sessions: the Mason picks the data, the Artisan lays out the panes |
| the audit (`realm/audit.py`) | Warder, Pathfinder, Treasurer, Peon | rules in code, no model |
| the Council's Fast Path (`realm/fastpath.py`) | Chief, Mason, Alchemist, Mechanic, Farseer, Warder, Peon | rules first, then **one** light-model call in which the seven are lines of one checklist |
| the night (`realm/elders.py`, `gui/improve_night.py`, `gui/day_review.py`) | the Elders (permission questions), Mechanic, Alchemist, Farseer | model sessions of their own |

Eleven names, several of them one expertise in different hats. A person meets a name and cannot tell what it means.

## 2. The rule

> **One expertise, one ork, wherever it works.**

An ork is a role (its prompt and tier); the designer, the audit, the Council and the night are **flows of the Town
Hall** it works in, each run a session there ([ork-console.md](ork-console.md) §2). The Mason and the Warder already
work this way: one expertise in several places. The rest follow them.

**The Elders are a flow, not a group of orks** (decided 2026-10-12): the Town Hall's night council, a debate the
roles come to. The word stays; the console and the ork slots list show the role and its session, e.g.
"Treasurer · the night's council".

**A role is not owned by a building.** The Test bench is the Mechanic's place of work, the UX bench the Alchemist's;
both are town roles that go where their expertise is needed.

**A role is an ork only while it calls a model.** The audit's findings are rules in code, the Town Hall's own work;
no session shows for them in the console or the ork slots list. A Council review shows one session, the light
model's.

## 3. What is folded

1. **The Artisan into the Alchemist.** Both are UI designers; on the Council the Alchemist already holds the Artisan's
   seat (its id stays `artisan`). New buildings are laid out by the Alchemist; the building designer is "Mason &
   Alchemist".
2. **The Chief into the Treasurer: money.** The Chief guards where a model is called where a script would do, how
   often it wakes, how many run at once; the Treasurer, spend against the budget. One expertise, before and after.
   The cart's price ([ork-console.md](ork-console.md) §17) is the Treasurer's too.
3. **The Peon's seat is shared out.** Shared working trees, merges without tests and skipped permission prompts go to
   the **Warder** (the repository's safety); the cache and work done twice to the **Treasurer**. The Peon stays only
   what `orc.custom` says: the ork of a custom building.
4. **The Mechanic keeps quality, gives up spend.** The **Treasurer** guards what spend shows without a run (what is
   called, how often, on which tier); the **Mechanic** guards quality per token measured on the Test bench's cases.
   Its Council duty becomes "quality", the "heavier tier with no measured reason" line goes to the Treasurer.
5. **The Pathfinder stays: the town's layout and its roads** (decided 2026-10-12): buildings no road reaches or
   leaves, buildings that send nothing, a canvas with too many buildings. The name fits the roads.

## 4. The roles after

| role | expertise | takes over |
|---|---|---|
| **Workchief** | the lead: talks, sorts things out, hands work on | — |
| **Mason** | data, schemas, scripts: builds them, checks them, repairs a yard ([ork-console.md](ork-console.md) §16) | — |
| **Alchemist** | UI/UX: lays out views, checks how a building reads | the Artisan |
| **Mechanic** | quality measured on cases | — (gives up spend) |
| **Treasurer** | money: the budget, how spend is shaped, a cart's price | the Chief; the cache from the Peon |
| **Farseer** | what the person needs | — |
| **Warder** | the safety of the machine and the repository | working trees and permissions from the Peon |
| **Pathfinder** | the town's layout and its roads | — |

Eleven names to eight, each with one meaning wherever the person meets it.

## 5. What the code keeps

- **Ids stay** (CLAUDE.md, Wording): `artisan`, `chief`, `peon` in older verdicts, logs and settings keep loading. A
  folded role's old spelling goes into its term's `was` in `realm/lexicon.py` `TERMS`, and the interface says today's
  name through `say()`.
- **The rules stay as they are;** only whose name signs a finding changes.
- **Prompts:** the Council's `ROLES` lose the Chief's and the Peon's lines into the Treasurer's and the Warder's; the
  Artisan's prompt in `builders.py` becomes the Alchemist's brief (`design/agents/alchemist.md`) with the builder's
  task.

## 6. Decided

1. **A building's quick actions are the Alchemist's** (2026-10-12): whether they are there, whether they work and
   whether they are easy to use, not only the audit's "huts without quick actions". A building it changes is checked
   again after the change. The Pathfinder keeps the town's layout and its roads.
