# Design — feedback without buttons

Status: design notes, written 2026-10-05; stages 1–5 of §6 are implemented.
Builds on 👍 / 👎 (`realm/feedback.py`), the Loot checkpoint (`loot-checkpoint.md`), the trail of a
cart (`Payload.trail`) and the retros (`retros-and-goals.md`).

## 1. Why

The retros learn from 👍 / 👎, and the buttons are pressed rarely: rating is a chore the operator
does not have to do. But the operator already judges every result they touch: they accept it, fix
it, send it back, throw it away, merge it or ignore it. Those decisions are better data than a
button, because they cost nothing and nobody can forget them. So the camp reads them, and the
operator teaches the orks without thinking about it.

## 2. Signals

`feedback.signal(root, building, good, source, …)` keeps one, about the building that **made**
the result — the last hop of the cart's trail (`feedback.maker`), not the building that carried
it on. A good signal is a reference (as 👍), a bad one an incident (as 👎). Each has a `source`
and a weight (`feedback.WEIGHTS`):

| Where | What the operator did | Signal | Weight |
|---|---|---|---|
| 📦 Loot | ✓ accepted a held cart as it was | 👍 | 0.34 |
| | ✓ Accept all | 👍 | 0.1 |
| | ✎ edited and accepted: only added to | 👍 | 0.34 |
| | ✎ … fixed a few of its lines | 👎 + the edit | 0.34 |
| | ✎ … changed its format | 👎 + the edit | 0.5 |
| | ✎ … rewrote it | 👎 + the edit | 0.75 |
| | ↩ sent back with a reason | 👎 | 0.5 |
| | the rework rounds did not fix it (*needs you*) | 👎 | 0.5 more |
| | ✗ dropped | 👎 | 0.5 |
| 🌊 Lake | an ork's file: fixed | 👎 + the edit | 0.2 |
| | … its format changed, or rewritten | 👎 + the edit | 0.5 |
| | … filled in | nothing | — |
| 🏕 Barracks | the pull request merged | 👍 | 1 |
| | … closed without merging | 👎 | 1 |
| `Z` | took back a retro's change (`auto-improve`, `weekly`) | 👎 | 1 |
| anywhere | a result left in a Lake or a Loot, not opened for a day | 👎 | 0.1 |
| 👍 / 👎 | the buttons, the Town retro's survey | 👍 / 👎 | 1 |

What is **not** a signal:

- a cart that passed a Loot by its rules — nobody looked, so nobody approved (counting it would
  teach the orks to slip past the rules);
- 🛑 Halt All — it stops the whole camp, there is nobody to blame;
- `Z` on the operator's own change — they undo themselves, not an ork.

## 3. Reading an edit (`realm/edits.py`)

An edit is not a complaint by itself. A daily note an ork laid out and the operator writes into
all day is the note doing its job; what says the ork was wrong is a change to **what the ork
wrote**. So an edit is classified by what happened to the ork's own lines (blank lines and
trailing spaces do not count):

| Kind | When |
|---|---|
| `same` | nothing changed |
| `filled` | every line of the ork is still there, in order; only added to — a section's body written, `Mood:` → `Mood: fine`, `- [ ]` → `- [x]` |
| `touched` | some of its lines changed, its headings kept |
| `reshaped` | a heading of the ork is gone, renamed or moved — the format |
| `rewritten` | half of its lines or more gone or replaced |

In a **Lake** the comparison is always with the ork's text as it arrived (`lake.Origins`, kept in
the Lake's state), not with what was on disk when the editor opened. So a note filled in today and
again tomorrow stays `filled`; a line the operator wrote and later deleted is theirs, not the ork's;
and a file is judged again only when it gets worse for the ork (`filled` → `reshaped` →
`rewritten`), so saving five times is one signal. A file with `subtype: personal` in its front matter
keeps no text with the incident, only the summary: a personal note never reaches a model.

In a **Loot**, `e` opens a held text cart; ctrl+s accepts the operator's version. A bad edit keeps
two things: the incident with the diff (what was wrong) and the operator's version as a reference
of weight 0 (what it should have been) — the pair the Council's `enrich` needs.

## 4. Who is blamed

The maker, for its logic. When the reason says the inputs were broken — the ↩ chip "what came in
was wrong" — the buildings before the maker in the cart's own trail pay, the nearest first, by the
same cascade as 👎 (1, ½, ¼), scaled by the weight. The trail is what actually happened to that
cart; the session's roads (what 👎 uses) are only a guess at it.

The blame is what the retros read, not the building the incident was told about
(`Incident.share`, `feedback.disliked`, `feedback.blaming`): a cart sent back for broken inputs
weighs nothing on its maker, which passed on what it got, and 0.5 / 0.25 on the two buildings
before it. So the 🔧 Building retro picks the supplier that keeps breaking what comes after it,
probation takes back a supplier's change when what it fed is disliked downstream, and the Council
sees those incidents marked "downstream, at X: this building fed it broken inputs". A 👎 for broken
inputs on a building nobody feeds falls on the building itself. The other quiet signals (an edit,
a drop, a pull request, `Z`, a result nobody opened) blame only the maker: what the operator did
does not say the inputs were wrong, and spreading the blame by default would have the retros fix
buildings that work.

The ↩ dialog offers six reasons as chips (`feedback.REASONS`: did the wrong thing · incomplete ·
wrong format or style · facts are wrong · what came in was wrong · too expensive), `1`–`6` or a
click, and a note. The reason that goes back to the source reads `wrong format or style: no
headings`; the incident keeps the chip as its `tag`.

## 5. Weights, and who reads them

`scores.json` keeps, per building, the buttons pressed (`likes`, `dislikes`), the `penalty`, and
now the weighted sums `liked` / `disliked` and `by` — the weight by source, signed. Incidents and
references carry `source` and `weight` (old ones read as `explicit`, 1).

Everything that acted on "a 👎" acts on weight now, from `feedback.ENOUGH` (1):

- **🔧 Building retro** (`optimize.leader`): a 💎 building is "disliked this week" from a weight of 1,
  a ⚖️ one "disliked today" the same; "liked since its change" likewise; "never rated" is less than 1
  of either. So two carts sent back are a 👎, one quiet acceptance is not a 👍.
- **Probation** (`evolution.verdict`): a change of the orks goes back when what the operator did
  since adds up to a 👎 — one reshaped file alone does not take it back; a reshape and a rework do.
- **🗓 Town retro**: the survey is skipped when the week's signals weigh 1 or more (the operator
  told the camp enough by working); the report shows each building's weight by source.
- **The Council's prompt** lists incidents with how they were told (`[loot.reshaped · format]`) and
  the operator's edit under them.
- **The Town Hall** shows the weight of what the operator did beside the buttons, and how each
  incident was told.

## 6. Stages

1. The Loot: accept, ✎ edit, ↩ with reason chips, drop, *needs you* — attributed by the trail. *(done)*
2. The Lake: the ork's file kept on arrival, the edit judged against it; filling in says nothing. *(done)*
3. Pull requests of the Barracks (merged / closed, read with `gh` every 10 minutes) and `Z` on a
   retro's change. *(done)*
4. Weights: `source` and `weight` on incidents and references, `liked` / `disliked` / `by` in the
   scores; the retros, probation, the survey and the Town Hall read them. *(done)*
5. Results nobody opened: a cart that stays in a Lake or a Loot waits (`feedback.await_view`);
   selecting that building sees it; after a day it is a light 👎 (`sweep_unseen`, with the
   probation check). *(done)*

Later: commits the operator added on top of an ork's pull request before merging (a measure of how
much it needed fixing); a merged branch reverted within a week; ✎ edit in the Clan Fire.
