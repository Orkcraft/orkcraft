# Design — lighter buildings: no Work panel, a setup of one question

Status: proposal 2026-10-12, the owner's ask; **being built (A5, 2026-10-14), type by type — see §7.** Priority **P1**, with the Work and Info split of
[ork-console.md](ork-console.md) §15, and one check at **P0** (§4). Builds on
[select-a-building.md](select-a-building.md) §7 (a building raised is set up in the Workchief's line, built for
External listeners), [warchief-line-and-cards.md](warchief-line-and-cards.md) §3 (place first, then set up) and §4
(a card in three sizes, and its window).

## 1. Why

- **The Work panel takes half the screen** (`layout.css` `.gui-panel`: `width: 50%`, at least 380 px) and gives
  little for it. An open building hides half the town, and the town at a glance is what Orkline promises.
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
> the Workchief's line. Everything else is a default, changed later in its Info.**

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

## 7. Built (A5): Work taken away, type by type

How a type loses its Work: its page module says `export const work = false` (js/types.js). Opening it then grows its
card to its large size **in place**, at any zoom, while it stays selected (a view of the page, never a size kept in the
Town Scroll; js/windows.js `showOnCard`, js/hut.js); opened again, its Info. On the phone, with no town, the panel shows
that large card as its sheet. Its settings are drawn in its Info by the type's `settings(id, data)`. Saved towns keep
loading: every setting stays in the building's config as before, and its old UI document stays valid, unused.

| type | its Work held | where it went |
|---|---|---|
| **Agent pool** | counters and Pause; the question strip; New task; the flow of tasks and a task opened over it (brief, diff, report, answer, files, assumptions); a tab per ork with its terminal, Take over / Hand back, its recent work; rules, the steward's ask, folder, settings, kinds of work, areas in work, decisions | counters on the large card's first line, Pause / Resume the command card's (and the card's when paused); questions on the ❓ and in the console (§7 of ork-console.md); New task and the flow with the task opened over it on the **large card**; each ork's session, terminal, Take over / Hand back, history with cost in its **console** (js/orkconsole.js); rules, folder, settings, kinds of work, areas, decisions in its **Info** |
| **External listeners** | its chips and the feed, a message read over it, Check now, Read all, Open new, a failing source with its fix; Add source over the feed; Sources & intent (the intent, each source with Edit, Log in again, Remove, its places, the steward's ask) | the chips, the feed, the message read over it, Check now, Read all, Open new and a failing source on the **large card** (a bare building's card is drawn while grown); Add source a page of its **Info** (its ← Back), also from the card with no source and from the Workchief's setup; the intent and the sources in its **Info** |
| **Review gate** | counters with Accept all / Accept files; Rules (the keeper's dialog); the strip of a cart that needs you; the carts and the changed files, a cart or file opened over them with its acts, edit, branch files, why it waits, its chain | everything but the rules on the **large card** (the opened cart replaces the list there; Rework, Drop and Accept all ask over the town, never inside the card); a long cart or file to the **Inspector**; the rules, read out and changed through its steward, in its **Info** |
| **Task board** | the whole board (counters, the three parts, lanes of cards, drag between lanes, the selected card's strip, every card's window: open and edit, context, plan, join, news, delete), the note writer; When new tasks go; New note folder | the whole board on the **large card** (grown to 760 × 520, a type's `grown`), its windows asking over the town; the note writer on the card too (+ Note, the New note quick action); When new tasks go and New note folder in its **Info** |

**Not taken away (yet):** the **Inspector** keeps its window, its job being reading at length (§2). Every other type
keeps its Work as it is until its large card can hold its everyday job (§2: never all at once). With A5 the five core
types of the demo and the testers' first fifteen minutes (§4) are done: the Agent pool, External listeners, the Review
gate and the Task board without Work, the Inspector reading in its window.

## 8. The inside of a building (I2, built for the Task board)

[decisions-2026-10.md](decisions-2026-10.md) §13.2 replaces §7's large card **for the view** with the building's
inside, the Task board first; the removals of §7 stand.

- **Entered** by the second click on a building in Camp (I1's steward and its Enter call the same
  `openBuilding`, `js/windows.js`): a type whose module draws a room (`inside(b)`, `js/types.js`) is entered as **a
  screen of its own** (`js/inside.js`) in the town's place; every other type keeps its large card. **Exit** stands
  at the top right; **Esc** goes back too, the building still selected.
- **Left (~60 %), the room** (`js/buildings/fields_inside.js`): the dispatcher's booth from inside, scrolled when large.
  Three boards on its back wall — **To do, Doing, Done** (a lane the person named keeps its name) — the orks' tasks
  pinned as **parchment sheets**, the person's own to-dos as **light stone slabs** standing on To do while open, on
  Done once ticked off. A card's flag is a small cloth flag: lowered on To do, half up on Doing, raised on Done; a
  to-do's flag is its checkbox (a press ticks it off or puts it back). The notes' lanes stand on a shelf under the
  boards. A card dragged to another board does what moving it does on the card (`move`); a to-do dragged onto Done
  is ticked off, back onto To do put back. A click selects a card (its acts over the boards, as on the card), a
  double click opens it. The **Taskmaster** and the orks at work walk between the boards in the inside poses (carry
  between boards; pin, lens, quill at one), a bubble over each: the Taskmaster's what it asks or how many orders wait,
  an ork's its Doing card in two or three words.
- **Right (~40 %), its settings**: the building's Info as it is today (`InfoTab`, js/console.js), the same settings,
  on a merchant's window — cream parchment in a walnut frame with teal accents (`inside.css`), in plain words.
- **Art:** the orks are v3's sprites; the booth's wall, the boards, the cards, the pins and the flags are CSS stand-ins
  in v3's tokens until u6-inside, u6-cards and u2-panels are cut. Each piece is one element with its own class
  (`.fields-in__wall`, `__board`, `__plaque`, `__card.is-sheet` / `.is-slab`, `__pin`, `__flag`, `__floor`), so a
  sprite drops in by CSS alone. Yellow and red stay for signals.
- **Office keeps the large card** (it draws no rooms, and a look changes only how things are drawn), and so does the
  phone's sheet. Tested in `tests/test_gui_camp_browser.py` (enter, the boards and a card, a card moved, a to-do
  ticked, Exit, Esc); screenshots in [img/i2/](img/i2/).
