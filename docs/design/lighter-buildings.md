# Design — lighter buildings: no Work panel, a setup of one question

Status: proposal 2026-10-12, the owner's ask; nothing built. Priority **P1**, with the Work and Info split of
[ork-console.md](ork-console.md) §15, and one check at **P0** (§4). Builds on
[select-a-building.md](select-a-building.md) §7 (a building raised is set up in the Warchief's line, built for
External listeners), [warchief-line-and-cards.md](warchief-line-and-cards.md) §3 (place first, then set up) and §4
(a card in three sizes, and its window).

## 1. Why

- **The Work panel takes half the screen** (`layout.css` `.gui-panel`: `width: 50%`, at least 380 px) and gives
  little for it. An open building hides half the town, and the town at a glance is what Orkcraft promises.
- **Setting a building up is heavy.** Only External listeners asks its first question in the line; every other type
  opens its whole window when it is raised.

## 2. No Work: a card, a command card and one Info

Decided with the owner 2026-10-12: **the Work panel is a crutch for what the cards do not do yet, and it goes.** An
earlier step of the same day kept it for emergencies; every emergency already has its own place:

| what went wrong | where it is dealt with |
|---|---|
| a run failed, an ork stuck or asking | its session in the console ([ork-console.md](ork-console.md) §7) |
| a long diff or document to read | the Inspector, whose job is reading ("Read in the Inspector" on the result) |
| a building burns | its hint opens the failed session in the console, or its record in its Info |

**What is left, for every building:** its **card** in three sizes (its data and flow; the large size in place for
the everyday job), its **command card** (Q, W, E) and **one Info** (how it works and how it shows its data).
**For every ork:** its **console** and **one Info** ([ork-console.md](ork-console.md) §15).

- **A double click grows the card to its large size in place.** The town stays whole around it.
- **The large card holds one everyday job per type.** If it cannot, the card is redesigned; no panel comes back.
- **The Inspector's own reading size** is its card's window size (half the screen, by the person's choice,
  [warchief-line-and-cards.md](warchief-line-and-cards.md) §4): it is the one type whose job is reading at length.

**Taken away type by type, never all at once.** A type's Work goes when its large card does its everyday job; until
then it stays as it is. The load moves to the cards: editing a task on the Task board's large card is real design
work, not a removal.

A first guess at each core type's everyday job on its large card ([catalog-shelves.md](catalog-shelves.md)):

| type | its large card's one job |
|---|---|
| Task board | open and edit a task; see where it goes next and why it waits ([ork-console.md](ork-console.md) §19) |
| Agent pool | the lanes: tasks by topic, what is at work ([ork-console.md](ork-console.md) §14) |
| Review gate | pass or send back a cart, its short diff; a long one to the Inspector |
| Inspector | read a diff or a document (its window size for long ones) |
| External listeners | what came in |

## 3. Setup: it works on defaults, and asks at most one question

> **A building raised works at once on its defaults. It asks at most one question, the one with no good default, in
> the Warchief's line. Everything else is a default, changed later in its Info.**

- Every core type gets the line's setup that External listeners has
  ([select-a-building.md](select-a-building.md) §7): its one question with answers as buttons ("What should it
  listen to?"), or no question at all when its defaults are enough.
- No type opens its whole window when raised. *All its settings* stays one press away.
- *Later* leaves the **needs setup** plate, as today: a building half set up is never lost.
- **The aim:** from Build to its first useful result in **60 seconds or less**, with **one answer at most**.

A first guess at the one question of each core type:

| type | its one question |
|---|---|
| Task board | none: it starts empty |
| Agent pool | none: it takes tasks from the board on its road |
| Review gate | none: everything waits for the person until rules are added |
| Inspector | none |
| External listeners | what should it listen to (built) |

## 4. The P0 check

The main scenario of the demo GIF and of the testers' first fifteen minutes (see who works and who waits, step in to
one) is done **without Work**: cards (medium and large), the command card and the console only. Not a separate piece of
work: the acceptance test of the console ([ork-console.md](ork-console.md) §11).

## 5. How we know

- From the usage stats ([usage-stats.md](../usage-stats.md)): the share of buildings left with **needs setup**, as
  [warchief-line-and-cards.md](warchief-line-and-cards.md) §3 already waits on.
- In the testers' recordings: where they look for what Work held. Looking for it means a card that cannot hold its
  job yet, so that type keeps its Work longer.

## 6. The owner's use (answered 2026-10-12)

The panels opened daily are the **Task board's** (when a task will be made or start, there is a delay; how to hand it
on) and the **Agent pool's** (why an ork does not start, what it is doing). Neither is for the data: both answer "why
is it not moving". That is the status's job, P0: every wait says why, until when and how to skip it, and a task says
where it goes next ([ork-console.md](ork-console.md) §19, §5). Their large cards then keep the everyday jobs of §2,
and their Work can go.
