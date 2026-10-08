# Design — 🌙 the Night round: the orks look over the work, not the town

Status: written 2026-10-08; stages 1–4 of §7 built the same day. Builds on the retros
(docs/design/retros-and-goals.md: the 🔧 Building retro daily, the 🗓 Weekly retro), the Task Fields'
context and plan (docs/design/fields-board.md §5b, realm/cardlore.py), the steward's work
(docs/design/steward-at-work.md §2) and the Warchief's line (docs/design/calm-town.md §8, the growth news
of docs/design/growth.md §3). Wording: ork, orkestration (CLAUDE.md).

## 1. Why

Everything the town does on a clock looks at **the town itself**: the Building retro makes one building
cheaper or better, the Weekly retro audits the whole camp, quiet hours apply the orks' own changes, the
Wiki checks its own pages. Nothing on a clock looks at **the work**: the to-dos lying on the board, the
code that changed today, the goals the boards were made for.

The job the operator has: *"I sit down in the morning and in a minute I know what to pick up and what has
gone stale — without reading everything."* So the value is in the morning; the night is only when the work
is cheap to do (the operator is away, the quota has room).

## 2. What it is not

- **Not the Town Hall at night.** The Town Hall is the town's own: its audit, the Warchief, the proposals.
  The work lives in the buildings: the to-dos on a 🌾 Task Fields board, the knowledge in a 🗑️ Wiki. So
  the round is each board's **steward** at work (realm/steward.py `WORK`: its goal picks the model), and
  the Town Hall only says the morning's one line.
- **Not a second inbox.** What the round finds goes **onto the board**: a 🌙 mark on the card it is
  about, an idea as a note in **Ideas**. Taking an idea is moving it into To Do (or My to-dos); not taking
  it is deleting it. Nothing new to read, nothing to Apply / Dismiss.
- **Not work for the orks.** The round never creates a task in a status lane and never sends one down a
  road: it writes notes and marks. Whatever the town's Autonomy.

## 3. One night (`realm/nightround.py`, `core/workers/fields_round.py`, `core/retros.py`)

```
 round_at due (daily 04:40) ─► rules, on the town's thread, free
                                 the commits since the last round (git log of the project)
                                 every board's open cards: To Do tasks and open to-dos
                                 per card: the commits that share its words, the wiki pages new or changed
                                 nothing changed since last night ─► the night is skipped, no model at all
                           ─► the model, off the thread, only where the rules found something
                                 per card (not personal): one or two lines, what is new for it
                                 the day's diff: at most 3 cleanup ideas
                           ─► on the board: 🌙 marks, the ideas in Ideas; one line in the morning
```

**When.** `round_at` in the council's settings (`.orkcraft/council/settings.json`, next to `optimize_at`
and `weekly_at`), `daily 04:40` by default: before the Building retro (06:20) and the operator's
morning. Empty is off; Settings → **Night round** turns it on or off and has **Look now**. A board says
`night_round: false` in its settings to be left out. The demo never runs it; a spent budget skips it.

**Since when.** The last round (`.orkcraft/round/last.json`); the first one looks back 24 h.

### 3.1 New context for the cards that lie (stage 1, rules)

The cards looked at are the ones **lying**: tasks in To Do and the person's to-dos not ticked off — not
the ones in progress (an ork works them), not Done, not notes.

- **Commits.** `git log --since` of the project, merges left out, at most 200: each one's subject and the
  files it touched. A commit is a card's when they share words (realm/wiki.py `stems`: by the start of a
  word, any script, the common words left out) — at least two, or one when the card has only one word
  that counts. The three best per card.
- **Pages.** The card's context is looked up again (`find_context`, no model: the board does that
  already, §5b of fields-board.md); a page that was not there before, or that changed since the last
  round, is news.
- A card with news gets a **🌙** mark: what the rules found (`.orkcraft/fields/<id>/cards.json`, the
  card's `news`, next to its 📜 and 🧭). A click shows it: the commits, the pages (a page opens in
  Lake) and **Seen**, which takes the mark off. The next round writes it again only for something new.
- At most 8 cards per board a night: the oldest first (how long a card has lain is `.orkcraft/round/seen.json`).

### 3.2 What is new, in words (stage 2, a light model)

For a card the rules marked and that is not 🔒 personal, the board's steward (`news`: Tell what is new
for a card — 🪙 laborer · ⚖️ laborer · 💎 warrior) gets the card, the commit subjects and the pages'
starts, cleaned first (realm/privacy.py), and answers in one or two sentences, in the card's language:
what is new for it, and whether it may be done already. When nothing it was given matters to the card it
answers `NOTHING` and the mark goes: the rules overshoot, the model trims. At most 5 cards per board a
night. What left is logged as a fact (`sent.jsonl`), never as its text. A personal card keeps the
rules' mark without words.

### 3.3 Cleanup ideas from the day's code (stage 3)

When there were commits, the first board that takes part (the scroll's order) gets **at most 3** ideas
from the day's diff: dead code, a duplicate, a test missing for what changed, a TODO left behind, a name
that no longer says what a thing does. The steward's `ideas` (🪙 laborer · ⚖️ warrior · 💎 elder) gets
the commits and their diff (at most 12 000 characters, cleaned), and answers in JSON: a title and one
line of why, each with its file. An idea whose title is already a card's on the board is left out.

Each idea is a **note in Ideas** (the lane is made when the board has none), marked 🌙 and *from the
night round*. What becomes of it is how the round learns (`.orkcraft/round/ideas.json`):

| what the person did | it is |
|---|---|
| moved it out of Ideas (to To Do, My to-dos, another lane) | taken |
| deleted it | dropped |
| left it | open |

Three dropped in a row and the next night gives **one** idea; six and it gives **none** and says so
in its morning line; one taken and it is back to three. So a round nobody wants goes quiet by itself.

### 3.4 The goals, weekly (stage 4)

Goals do not change overnight: re-weighing them every night is noise. The **Weekly retro** gets a new
part, **THE WORK**: every board's open cards with how long each has lain (personal ones by their first
word only), what the week's rounds found and what became of their ideas. It may give at most two `note`
items about the work itself, titled `Work: …`: a to-do lying for weeks to drop or split, a goal the boards
no longer serve, a direction the week's commits point to. They are advice: shown with the other items,
nothing to apply.

## 4. The morning (`growth.tell`, the Warchief's line)

The round says what it did **once**, in the Warchief's line, as growth news does (said once, then seen):

> 🌙 Night round: 3 cards have news, 2 cleanup ideas · Task Fields

A click opens the board. Nothing found, nothing said. The line says plainly what happened; the voice of
the camp stays for the Warchief's own words.

## 5. Cost and safety

- **Free when nothing changed.** No commit, no page changed, no card news → no model call, the night is
  written down as skipped (`nights.jsonl`).
- **Bounded.** At most 5 light calls per board and one ideas call a night; the steward's goal picks the
  tier, and a tight quota picks 🪙 (realm/pressure.py `Camp.tight`, as everywhere).
- **Private stays home.** A 🔒 card never reaches a model (it gets the rules' mark only); everything that
  leaves is cleaned of what has a shape first and logged as a fact.
- **Writes only notes and marks.** Never a task, never a cart.
- Each night is a line in `.orkcraft/round/nights.jsonl`: when, the boards, the cards with news, the
  ideas, the model calls, or why it was skipped. Settings shows the last one.

## 6. Words

`night_round` → **Night round** in `realm/lexicon.py` `TERMS`. The marks and lines: 🌙, *What's new*,
*from the night round*, *Seen*, *Look now*. Code keeps its own names (`nightround`, `round_at`, `news`).

## 7. Stages

| stage | what | state |
|---|---|---|
| 1 | rules: the cards that lie, the commits and pages that are theirs, the 🌙 mark, the morning line, Settings | done |
| 2 | a light model says what is new for a marked card, or trims the mark | done |
| 3 | at most 3 cleanup ideas from the day's diff as notes in Ideas; the round learns from what is taken | done |
| 4 | the Weekly retro's THE WORK and its `Work:` notes | done |
| later | the Wiki's librarian on the round: pages the day's commits made stale | |
| later | a 🌙 card's news into the task it becomes when it goes to an Agent pool | |
| later | the round in the TUI: it is deprecated (calm-town.md §9), the GUI only | |

## 8. Measures

- **Taken / given** of the ideas over 30 days (`ideas.json`): under 1 in 5 and the ideas are noise.
- **Seen / marked** of the 🌙 marks: news nobody opens is news not worth giving.
- **Cost a night** (`nights.jsonl`), against the Building retro's.
