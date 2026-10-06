# Design — 🌾 Task Fields: a board of tasks and sticky notes

Task Fields began as a three-column kanban of tasks. People keep more than tasks next to their
work: ideas, questions for the next sync, notes from a call — things with no status that sometimes
turn into work. This note makes the building one board for both, without a second building and
without a heavier screen.

Implemented: `realm/tasklist.py` (the board in a file or a folder), `screens/typed/tasks_view.py`
(the board), `realm/catalog.py` (what the Town Builder knows of it). Tests: `tests/test_typed_tasks.py`.

## 1. One board, two kinds of card

- A **card** has a title, a text and a colour.
- A **lane** is a column of cards. The three **status lanes** — To Do, In Progress, Done — hold
  **tasks**. Every other lane — Ideas, Notes, Questions, For the sync — holds **notes**.
- **A card's kind follows its lane.** There is no "type" field to keep in step: moving a note into
  To Do makes it a task (`tasks.created`), moving a task into Ideas makes it a note. `t` does that
  move in one key.

Why not two buildings, or a type switch on every card: the step from "an idea" to "a task" is the
point of keeping both in one place, and a lane already says what a card is.

## 1a. The person's own to-dos — three parts on one board

The orks' tasks are not all the work: the person has their own. A third kind of lane holds them,
**My to-dos** (`## My to-dos` in the file, `mine/` in a folder; Camp says *My chores*, the Office
*My to-dos*): a checklist whose cards are ticked off (`- [x]`, `done: true` in a card file) rather than
moved. They send nothing down the roads — they are no work for the orks — until one is given to them
(moved into To Do, `tasks.created`). An idea (a note) becomes a task (`t`, *Give it to the orks*) or a
chore (`m`, *Make it my chore*); `x` ticks a chore off.

In `board` mode the screen has three parts: **Ork work** (the status lanes) on top, **My chores** and
**Scribbles** (the lanes of notes) under it. The closed card shows all three at a glance and stands
larger than other huts (about a fifth of the screen high; 26 × 11 cells in the terminal).

## 2. Modes instead of more screens

`mode` decides which lanes the board shows; the cards stay the same:

| mode | shows | a cart that arrives becomes |
|---|---|---|
| `board` (default) | every lane: the kanban, then the lanes of notes | a task in To Do |
| `tasks` | To Do, In Progress, Done | a task in To Do |
| `notes` | the lanes of notes (a wall of stickers; "Notes" when there is none yet) | a note |

A board with no lanes of notes looks exactly as Task Fields always did, so towns raised before keep
their screen. Two buildings can share one file: a `tasks` kanban in one orkspace and a `notes` wall
in another.

`lanes` (`["Ideas", "Questions"]`) puts lanes of notes on the board before any note is in them.

## 3. Not overloading the screen

- No new panes: a lane is a column like the three before; a note shows its title in bold and the
  first two lines of its text, dimmed; a task with a text shows ✎.
- The footer shows the keys used most — `n` new, `<` `>` move, `e` open, `c` colour, `t` note ⇄
  task; `s` send, `d` delete and `N` a new lane work without taking space there.
- Opening a card is one text box: the first line is the title, the rest its text.
- Colour is a coloured square at the start of the title (🟨 🟩 🟦 🟥 🟪). It needs no extra field,
  reads the same in the file, on GitHub and on the board, and `c` cycles it.

## 4. The file

Plain Markdown in git, one `##` section per lane; a card is a `- [ ] title` line (`- title` in a
lane of notes), its text the indented lines under it:

```markdown
# My tasks

## To Do
- [ ] Plan the v0.2 release
  freeze on Monday, tag on Thursday

## Done
- [x] Town Hall audit

## Ideas
- 🟨 A calendar roof
  the War Drum's hut shows the next meeting
```

- What comes before the first `##` is kept; every lane is kept. (Before this, writing the file
  dropped every section but the three status ones — a `## Notes` section was lost on the first move.)
- A heading is a status lane when it reads like one (`To Do`, `Backlog`, `Doing`, `WIP`, `Done`…),
  else a lane of notes whose id is a slug of the heading.
- A card's id is a slug of its title, the colour aside, so recolouring keeps it.
- **A folder** (`path: tasks`): `todo/`, `in-progress/`, `done/` hold the tasks (their `status:`
  follows the folder, as before); any other subfolder is a lane of notes; a card is a file whose
  text follows its `# title`.

## 5. Roads

| event | when | carries |
|---|---|---|
| `tasks.created` | a task is added, or a note becomes one | its id (node) |
| `tasks.status_changed` | a task moves between statuses | its id, `from → to` in the title |
| `notes.created` | a note is added | its title and text; `ref` = `<building>:<card id>` |
| `tasks.sent` | the operator presses `s` on a card | its title and text; the same `ref` |

The events every building and ready town already use (`tasks.*`) mean what they meant: they never
fire for notes. A cart that arrives becomes a card — its title (else its first line) and the rest
of what it carries as the text.

## 6. Next

- **The result comes back to the card.** A card sent to a Barracks or a Clan Fire could get the
  pull request, the report or the verdict attached and move itself (to Done, or "Needs rework").
  It cannot come by road — Fields → Barracks → Fields closes a loop — so it needs the direct
  delivery a Loot rework uses (`app.return_for_rework`), matched by the card's `ref`.
- **Group by another field** (assignee, priority) for boards that are not about status.
- **Links between cards** (`→ dark-mode`) and a due date, shown on the hut when one is near.
- **A "wall" layout** for `notes` mode: cards of one size in a grid instead of lanes. Free 2D
  placement, as on a whiteboard, is out on purpose — in a terminal it is cramped and slow to move.
