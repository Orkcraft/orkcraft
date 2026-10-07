# Design — the Review board: a purpose, a clan, named exits

Status: written and built 2026-10-07 — all four stages of §8. Not built: the exits drawn as signed roads on the map (§2) and Go on resuming from the very turn it stopped at (it resumes with the members not yet heard). The Review board is the catalog's
`council` (the Clan Fire of old: `core/workers/council.py`, `realm/team.py`, `gui/views/council.py`,
`js/buildings/council.js`). Screenshots of every state it has today:
https://claude.ai/artifact/HXs4DvsBndSTyyKrF5t3Uv

## 1. The model

A Review board is set up once, from what it is for:

```
 purpose (the steward's prompt, in plain words)
    └─► the clan: the members who judge, each with a brief, some with a veto
    └─► the exits: where a judged document can go, each a road out of the building
```

- **The purpose decides the clan.** "Review a PRD before it is built" → Product critic, Risks
  analyzer, Marketing analyzer. "Check a new calendar event" → Productivity analyzer. The keeper
  proposes the clan from the purpose; the person edits and confirms (§3).
- **One clan per building.** Another kind of document is another building: *PRD review* and *Event
  review* stand side by side, each with its own roads and its own spend.
- **The exits are named.** The steward picks exactly one exit for each document. The person names
  them when setting up — "To development", "To the designer", "Backlog" — each with a rule in words
  for when it is taken, and each is a road on the map (§2).

## 2. Exits

An exit is `name` + `when` (the rule, in words, the steward reads) + its road. Two exits are built in
and always there:

| Exit | What happens | On the map |
|---|---|---|
| a named exit ("To development") | the document goes down its road | a road out of the building, signed with the exit's name |
| **Back to the author** (built in) | the document goes back to the building that wrote it (a Barracks redoes it under the same title: the next review is cycle 2) | no road: it goes straight back (a road back would close a loop) |
| **Ask me** (built in) | the building burns; the person picks the exit (§5) | the fire on the building |

- **Templates.** The two modes of today become two one-click templates, then the exits can be
  renamed and added to:
  - *Decision*: **Next** + Back to the author.
  - *Who does it*: **To an agent** + **To a person** (+ Back to the author).
- **An exit with no road** cannot be taken: the steward asks instead, and the exit shows
  *not connected* in the setup and in the panel.
- **Back to the author with no author.** A document that came from a file, a Watchtower or by hand
  has no building that redoes it. The setup says so beside the exit (*nobody here reworks — it will
  ask you*); at run time the steward asks instead.
- **The veto.** A veto from a member who holds one forbids every exit but *Back to the author* and
  *Ask me*. A veto from a member without one counts as changes (as today).
- **The cycle limit.** Once a document has gone back `max_cycles − 1` times, *Back to the author*
  turns into *Ask me* (as today).
- In the spec: `exits: ["To development: ready to build, no open risk", "To the designer: the flows
  or the screens are unclear"]` — the name before the colon, the rule after; each is a route a road
  waits for (`road.filter.route`), as `routes` are today. `routes` of old keep loading as exits
  without a rule; a clan with neither has the *Decision* template.

## 3. Setting up — in the panel, never a dialog

A Review board with nothing set up opens its panel on the setup (watchtower-quick-add.md §4.2), and
its card says **Set up the review**. Three steps, the same shape as Add a source:

1. **Purpose.** One field: *What does this board review, and what matters?* — "PRDs before
   development: scope, risks, whether marketing can sell it".
2. **Clan.** The keeper proposes the members from the purpose (one model turn): role, what it
   checks (the first lines of its brief), its model tier, the veto on the guards (Risks, Security).
   The person removes, adds, renames, moves the veto, opens a brief in Lake. Briefs are files
   (`roles/<role>.md`), written by the keeper from the purpose, not empty templates.
3. **Exits.** A template (*Decision* / *Who does it*), then the named exits, each with its rule and
   its road: *+ Connect* lays the road to a building on the map (the road dialog, in one click). The
   two built-in exits are listed, not editable. The limits stand here too, in plain sight:
   *at most 3 cycles and $2.00 a review*.

**Save** writes the spec and the briefs; the card shows the clan and the exits. Every step is open
later from the panel (*Edit the clan*, *Edit the exits*); the keeper keeps taking changes in words.

## 4. The verdict travels on every exit

Whatever exit a document takes, it carries the verdict before the document:

```
## Review notes — To development · cycle 1 · 3 ✓ 0 ✗
<the steward: what to keep in mind / what to fix>

**Architect — changes:** <what it asked>
**Risks — approve:** <one line>
---
<the document>
```

- *To development* reads it as **what to keep in mind**; *Back to the author* as **what to fix**
  (today's `rework_markdown`); a person's exit as **why it is yours**.
- Members who approved without a remark are a count, not a block.
- The person's comment (§5) goes in as the steward's part, word for word.
- The full report still goes to `loot/` as `team.artifact_ready`.
- In the panel, after the decision: **Sent → To development: notes + document**, with a link to what
  went out.

## 5. Asking the person: fire and the exits as buttons

When the steward asks (or the rules hand it over: a veto it would pass, the cycle limit, an exit
with no road):

- **The building burns** (the design system's fire: frame, glow, flames after 60 s), and the
  question is in Answers — never a toast alone.
- **In the panel**, above the turns: the steward's question, then **one button per exit** —
  *To development · To the designer · Back to the author* — and a comment field. A button sends the
  document down that exit at once, with the comment as the verdict (§4): no model turn, no dialog.
- *Ask the steward again* stays for an answer in words (today's reply), for when none of the exits
  fits yet.

## 6. States and what each one offers

The states stay those of today (the screenshots), with a way on from each:

| State | Card | Panel adds |
|---|---|---|
| not set up | **Set up the review** | the setup (§3) |
| ready | the purpose in a line, the exits as small signs | *Review…* |
| members reading | `reading · 2 of 3 have spoken` | the turns as they come |
| the steward decides | `deciding` (a step of its own) | — |
| sent down an exit | `→ To development` | **Sent → …** (§4) |
| back to the author | `↩ back · cycle 2` | what went back |
| asks you | 🔥 the question | the exits as buttons (§5) |
| stopped: budget | `⚠ budget` | **Raise to $4 and go on** · the exits as buttons |
| failed | `✗ failed` + why | **Try again** |
| stopped by hand | `■ stopped` | **Go on** (from the turn it stopped at) |
| waiting in line | `N waiting` on the card and **in the panel's head** | the line, each with *Review now* / *Drop* |

## 7. What changes in the code

- `realm/team.py`: `exits_of(config)` (`exits`, else `routes`, else the *Decision* template), the
  exits and their rules in `decide_prompt`, `EXIT:` parsed as `ROUTE:` is; `verdict_markdown(d, exit)`
  in place of `rework_markdown` for every exit; a decision by the person (`decide(d, exit, comment)`)
  that ends the review without a model turn.
- `core/workers/council.py`: every exit emits its document with the verdict; *Back to the author*
  through `take_back` as today; `status()` says `WORKING` while it reviews (the hut's spinner) and
  raises the building's alert when it asks (the fire); a document that comes while the 🪙 budget is
  out waits in line instead of being dropped; setup acts (purpose, propose the clan, save) running
  the keeper's turn in a thread, as Add a source does.
- `gui/views/council.py` + `js/buildings/council.js`: the setup in the panel; the exits as buttons;
  *Sent → …*; the line in the head; Add member and Answer leave their dialogs for the panel (Review…
  stays a small dialog: one decision); the garrison badge says today's word (*Reviewers*, not
  *Chieftains*).
- `realm/catalog.py`: `exits` in the config, `purpose` beside `steward_prompt` (the same thing, the
  new name in the interface).

## 8. Stages

| # | Stage | Done when |
|---|---|---|
| 1 | Fire and spinner; nothing dropped when the budget is out; the badge's word | asking burns the building, a review spins the hut, a document never vanishes |
| 2 | The exits as buttons when it asks; ways on from budget, failed, stopped | no state is a dead end |
| 3 | Named exits with rules; the verdict on every exit | a document reaches *To development* with its notes on top |
| 4 | The setup in the panel: purpose → clan proposed → exits | a new board is set up in a minute, with briefs written for its purpose |

## 9. Open questions

1. **The keeper's proposal**: one turn of the light model, or the Warchief's model for a better clan?
2. **A member's model**: does the keeper choose tiers (an elder for Risks), or all the same by default?
3. **Exits shared with the Signpost**: a Review board with many exits looks like a Signpost after
   it; should the map draw its exits the same way (the signs on the roads)?
