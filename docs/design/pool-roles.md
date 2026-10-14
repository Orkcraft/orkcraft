# Design — the Agent pool's lanes as roles (A6)

Status: built 2026-10-14 (backlog A6, [ork-console.md](ork-console.md) §14, §11 row 6: P0, the lanes only; the data
model behind them is P1).

## What changes

Before, the pool's card drew **a lane per ork it hired** (Grub, Mogka…): its head, its name, its AI tool and tier, its
topic, what of the topic waits ([warchief-line-and-cards.md](warchief-line-and-cards.md) §4). The decided model
([ork-console.md](ork-console.md) §2, decision 5): **an ork is a role, its runs are sessions**. So a lane is now a
**role**, and the orks hired as it are its **sessions**, drawn as chips:

```
Grunt · tests       ⚙ ⚙ ❓      3 at work · 4 waiting
Grunt · frontend    💭           1 at work
Grunt · any work    Zz           —
```

## The choices the docs left open, and the defaults taken

1. **What a role is, today.** The persona a pool ork is hired as (`PoolOrc.persona`, `realm/personas.py`); no persona
   is the role "any work". Two orks hired as `tests` are one role with two sessions. No new data: a role is grouped
   from the orks the pool keeps, so a saved pool loads as it is and needs no migration (a test loads an old one).
   A role of its own in the data, with its prompt, tier and Autonomy, is P1 (§11 row 10).
2. **Its name.** The building's ork by its orkish name (`orc.barracks` in `lexicon.TERMS`: the Grunt) and its topic:
   "Grunt · tests". A session keeps the name it was hired with (Grub) — it is what its terminal and its log say —
   and shows it in the chip's tooltip.
3. **Its status.** Every session's is the one status (`realm/status.py`, the worker's `ork_status`); the role's is
   its most urgent session's: ❓ when one asks, else at work when one works, else resting. Office says the word, and
   draws no chip for a resting session: the role's own word says it.
4. **Order.** Roles in the order they were first hired (a lane does not jump); in a role the asking session first,
   then the ones at work, then the resting ones (§14: "the asking one first").
5. **What a click does.** A chip of a session at work or asking opens its console (A4's, folded, `js/slots.js`); a
   resting one opens the pool on that session's tab (its terminal, its recent work), as the console has no row for
   a resting ork yet. The role's name opens its first session the same way. The rest of the lane stays the hut's,
   to select or drag it. The window's ork tabs say the role each is a session of. `openSession` in
   `js/buildings/barracks.js` is the one place to change when the console opens on a role (§14).
6. **How many.** Six roles at most, `+N` for the rest; a role draws six chips at most, `+N` for the rest.
7. **The tier on a role** is its sessions' when they share one; mixed, the lane shows none (each chip's tooltip
   has its own). The AI tool is a session's, never the role's (§2), so it moved from the lane to the chip's tooltip.
