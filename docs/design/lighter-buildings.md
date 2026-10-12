# Design — lighter buildings: the Work panel for emergencies, a setup of one question

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

## 2. Work: the panel opens only when something is wrong

Decided with the owner 2026-10-12: **the Work panel is not where work is done; it opens only in an emergency**, never
as the everyday way into a building. Once the orks' chatter leaves Work ([ork-console.md](ork-console.md) §15), the
everyday is covered on the town:

| the person wants to | done in |
|---|---|
| see what it is doing | its card, medium size (the flow strip on top) |
| work through its data (a task, a short diff, a list) | **its card, large size, in place on the town** |
| run it, add, check | its command card: Q, W, E |
| answer or stop an ork | the console |
| change how it works | its Info |
| **deal with what went wrong** (a failure to read through, a long diff, an edit the card cannot hold) | **the panel** |

- **A double click grows the card to its large size in place**, no longer opens the panel. The town stays whole
  around it.
- **The panel opens from an emergency:** the hint of a burning building ("see what failed"), a result too long for
  the card, or **Open in panel** in the command card's ⋯. Nothing opens it by habit.
- **Narrow: a third of the screen** (at least 360 px), so the town and its 🔥 and ❓ stay in sight; the Inspector on a
  long diff may open wide. Escape closes it.
- **The large card holds one job per type.** If a type's large card cannot hold its everyday job, the card is
  redesigned, not the panel opened by default.

A first guess at each core type's everyday job on its large card ([catalog-shelves.md](catalog-shelves.md)), to
check against the owner's use (§6):

| type | its large card's one job | when its panel opens |
|---|---|---|
| Task board | open and edit a task | a task too long to edit on the card |
| Agent pool | the lanes: tasks by topic, what is at work ([ork-console.md](ork-console.md) §14) | a task failed: its run to read through |
| Review gate | pass or send back a cart, its short diff | a long diff |
| Inspector | read a short diff or document | a long one (wide) |
| External listeners | what came in | a source failing |

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
one) is done **without opening a Work panel**: cards (medium and large), the command card and the console only. Not a separate piece of
work: the acceptance test of the console ([ork-console.md](ork-console.md) §11).

## 5. How we know

- From the usage stats ([usage-stats.md](../usage-stats.md)): the share of buildings left with **needs setup**, as
  [warchief-line-and-cards.md](warchief-line-and-cards.md) §3 already waits on.
- In the testers' recordings: how often a panel is opened, and whether each time was an emergency. A panel opened
  for everyday work means a card that cannot hold its job.

## 6. Open

1. **The owner's use:** which buildings' Work panels are opened daily today, and the one thing done in each. Each is
   a large card to redesign; it replaces the first guesses of §2 and §3.
