# Design — 🌾 Task Fields: a task settles before it goes, related ones go together

A person thinks in bursts: *"make feature X"*, and two minutes later *"no — here is a new design for
X"*. Today a board that hands its tasks to the orks by itself (`send_new`) sends the first card at once.
By the time the second one comes, an ork has built X the first way, and the second card is a rework
(or a second branch that conflicts with the first). The Barracks' foreman already sends related work to
the same ork in its warm session (♻, docs/design/barracks-flows.md). That saves tokens but not the work:
the join comes **after** the first version is built.

This note moves the join **before** the work: a new task waits a short while on the board (it
*settles*), and a related card that comes meanwhile joins it, so both go as one task. A card the person
marks **Not urgent** waits longer and gathers more. A related card that comes after the task went is
added to the work in the Barracks instead of starting it again.

Status: **implemented** — §2 and §3 (step 1), §4 (step 2), §5 (step 3), §6 (the board). Tests:
`tests/test_fields_settle.py`, and the board in a browser in `tests/test_gui_browser.py`.

Where it lives: `realm/settle.py` (what is related, what goes together: pure), `core/workers/fields_settle.py`
(holding, joining and sending; a part of the board's worker, `core/workers/fields.py`), `realm/cardlore.py` (what is kept beside the board),
`core/workers/barracks.py` (step 3: an addition to a queued task), `gui/views/fields.py` and
`gui/static/js/buildings/fields.js` (the board). The TUI gets nothing new (CLAUDE.md: it is deprecated).

## 1. Who it is for, and the default

It applies to a board that sends its tasks by itself (`send_new: true`): that is the board whose cards
become ork work without anyone pressing a key, so that is where a hasty send costs a rework. A board
where the person presses **Send** keeps that press as it is: an explicit send goes at once.

On such a board it is **the default**: `settle` is 120 seconds unless the building says otherwise
(`settle: 0` sends at once, as before). Two minutes is the length of "wait, one more thing": short enough
that nobody waits for the orks, long enough to catch the second thought. Every waiting card says when it
goes and has **Send now**, so the wait is never a surprise and never a trap.

| setting | default | what it does |
|---|---|---|
| `settle` | `120` | seconds a new task waits on the board before it goes; `0` sends at once |
| `later_minutes` | `60` | how long a task marked **Not urgent** waits |

## 2. A task settles (step 1)

A new task in To Do on a `send_new` board — written by the person, brought by a cart, moved from a note
or added by a hand edit of the file (all of them are `tasks.created`) — does not go at once. It is
**held**: the board keeps when it goes (`hold`, kept beside the board: `cards.json`, never in the board
file). The card shows **⏳ goes at 14:32** and **Send now**.

When the time comes (the board looks once every few seconds; a restart keeps the time), the task goes as
before: `tasks.sent`, its text and its `ref`. **Send now** sends it at once. Moving a held card out of To
Do, deleting it or making it a note drops the hold: it is not going anywhere.

## 3. Related tasks join (step 1)

When a new task comes while another one is held, the board asks whether they are about the same thing —
by their words, on this machine, no model (`realm/settle.py`): the words they share, each cut to its
start so that "экспорта" meets "экспорт" and "designs" meets "design", the common short words aside.

| how close | what happens |
|---|---|
| close (two or more words in common, at least half of the shorter card) | the new card **joins** the held one |
| near (a word in common) | the new card is held on its own and asks: **Looks like “X” — Join · Keep apart** |
| not related | held on its own |

A **joined** card stays on the board as it was written — nothing of the person's text is merged in the
file — and says **↳ with “X”**; the first card says **+1 added**. Both go as **one task** when the first
card's time comes, which is pushed back to give the next thought its two minutes too (at most three times
`settle` after the first card came). The task's text is the first card's, then each joined card under a
line of its own:

```
Make the CSV export

---
Added later — where it disagrees with the above, this wins: New design for the CSV export
the button on the right, …
```

The work comes back to every card of it: `pool.assigned`, `pool.done` and `pool.failed` carry the first
card's `ref`, and the joined cards move with it (In Progress, Done, back to To Do).

**Split off** takes a joined card out: it is held on its own again (one that already went with its task
stays as it is — the orks have it). **Join with…** joins a card to a held or sent task by hand, for what the words did not catch.

Why the cards stay apart in the file: the join is a guess. A guess the person cannot see or undo would
send mixed work to an ork; two cards with a mark between them are both visible and undone by one click.

## 4. Not urgent (step 2)

**Not urgent** on a held task makes it wait `later_minutes` (an hour) instead of `settle`: **🐢 goes at
15:30**. While it waits it gathers every related task that comes, so a morning of thoughts about one
feature goes as one task. **Urgent again** puts it back on the short wait. A joined card follows its first
card; marking it Not urgent marks the whole task.

## 5. Too late to join: an addition to the work (step 3)

A related card can come after its task went. Then it does not wait: it joins the task it belongs to
(**↳ with “X”**) and goes at once as an **addition** — `tasks.sent` with the first card's `ref` and only
the new text, under the same "Added later" line. The Barracks knows the task by that `ref`:

| the task in the Barracks | the addition |
|---|---|
| still in the queue, nobody on it | is added to the task's text: no second task, one ork does it all |
| an ork is on it, or it is done | a follow-up of that task: the same ork, its warm session, the same branch (as a rework is) |
| planned into parts, or being planned | a follow-up, as above |

## 6. On the board and the hut

- A held card: **⏳ goes at 14:32** (**🐢** when Not urgent), **+N added** on a first card, **↳ with “X”**
  on a joined one; a near one asks **Looks like “X” — Join · Keep apart** on the card.
- The selected card's strip: **Send now** in place of Send while it waits; **Not urgent** / **Urgent
  again**; **Split off** on a joined card; **Join with…**.
- The closed card says how many tasks wait to go (**⏳ 2 waiting**).

## 7. Roads

Nothing new: a held task goes as `tasks.sent`, as it did; an addition is a `tasks.sent` with the `ref`
of the task it adds to. A Barracks that knows that `ref` (§5) takes it as an addition; any other building
takes it as a cart like any other.

## 8. What would tell it works

- Fewer reworks and follow-ups on the same ticket within a few minutes of each other (the Barracks'
  decisions log has both).
- Tokens per finished task.
- How often **Split off** and **Keep apart** are pressed: often means the words join badly.
- How often **Send now** is pressed: nearly always means `settle` is too long.

## 9. Next

- A light model to judge the near ones (only for cards that are not personal, after the words).
- A held task that waits for the Barracks to be free rather than for a time.
- The same wait for carts that come straight into a Barracks, not through a board.
