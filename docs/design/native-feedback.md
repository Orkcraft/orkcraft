# Design — feedback without buttons

Status: design notes, written 2026-10-05; stages 1–7 of §6 are implemented.
Builds on 👍 / 👎 (`realm/feedback.py`), the Loot checkpoint (`loot-checkpoint.md`), the trail of a
cart (`Payload.trail`) and the retros (`retros-and-goals.md`).

## 1. Why

The retros learn from 👍 / 👎, and the buttons are pressed rarely: rating is a chore the operator
does not have to do. But the operator already judges every result they touch: they accept it, fix
it, send it back, throw it away, merge it or ignore it. Those decisions are better data than a
button, because they cost nothing and nobody can forget them. So the camp reads them, and the
operator teaches the orks without thinking about it.

## 2. Signals

`feedback.signal(root, building, good, source, …)` keeps one, about the building whose ork
**wrote** the result (`feedback.maker`): the last hop of the cart's trail that writes — an agent, a
hybrid, a War Tent task — not a Clan Fire that reviewed it after, nor a Mill's chain or a Signpost
that carried it on (a trail with no writing hop: its last hop). A cart with no trail was made by no
ork (a file dropped in a Pit): what the operator does with it teaches nobody. A good signal is a
reference (as 👍), a bad one an incident (as 👎). Each has a `source` and a weight
(`feedback.WEIGHTS`):

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
| | … closed without merging (not a duplicate) | 👎 | 0.5 |
| `Z` | took back a retro's change (`auto-improve`, `weekly`) | 👎 | 1 |
| anywhere | a result left in a Lake or a Loot, not opened for a day | *unused* (§5) | 0.1 |
| 👍 / 👎 | the buttons, the Town retro's survey | 👍 / 👎 | 1 |

What is **not** a signal:

- a cart that passed a Loot by its rules — nobody looked, so nobody approved (counting it would
  teach the orks to slip past the rules);
- 🛑 Halt All — it stops the whole camp, there is nobody to blame;
- `Z` on the operator's own change — they undo themselves, not an ork;
- a pull request closed as a duplicate — labelled `duplicate` or `superseded`, or another task of
  the Barracks with the same title merged (while that one is still open, the closed one waits);
- accepting a cart past the rework limit as it is — the operator gives up on it, that is no 👍 (the
  rounds were already 👎s); an edit then still says what was wrong.

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
`rewritten`), so saving five times is one signal. It is judged when the operator leaves the editor,
when the app closes with the editor open (what is in it is saved first), and when an edit was saved
and then left alone for `JUDGE_IDLE_S` (10 minutes) — never in the middle of typing, when a heading
deleted to be retyped would read as a new format. A file with `subtype: personal` in its front matter
keeps no text with the incident, only the summary: a personal note never reaches a model.
A file git tracks with no change since the last commit is not kept on arrival: an ork that only
pointed at a document of the operator's did not write it, and editing it says nothing about the ork.

In a **Loot**, `e` opens a held text cart; ctrl+s accepts the operator's version. A bad edit keeps
two things: the incident with the diff (what was wrong) and the operator's version as a reference
of weight 0 (what it should have been) — the pair the Council's `enrich` needs. A personal note
keeps neither text.

## 4. Who is blamed

The maker, for its logic. When the reason says the inputs were broken — the ↩ chip "what came in
was wrong" — the buildings before the maker in the cart's own trail pay, the nearest first, by the
same cascade as 👎 (1, ½, ¼), scaled by the weight. The trail is what actually happened to that
cart; the session's roads (what 👎 uses) are only a guess at it.

The blame is what the retros read, not the building the incident was told about
(`Incident.share`, `feedback.disliked`, `feedback.blaming`): a cart sent back for broken inputs
weighs nothing on its maker, which passed on what it got, and 0.5 / 0.25 on the two buildings
before it. So the 🔧 Building retro picks the supplier that keeps breaking what comes after it — from a weight
of 1 in a week (`feedback.fed_broken`), whatever it spends: a cheap supplier is under `MIN_SHARE` and
would never be looked at otherwise; a 🪙 one is worked on as ⚖️ that turn, since a shorter prompt alone
does not fix what it passes on, and only one that called a model this week (a chain has no prompt) —
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

Everything that acted on "a 👎" acts on weight now, from `feedback.ENOUGH` (1). Two kinds of
signal are kept apart from quality, because they would push the retros the wrong way:

- **a result nobody opened** (`NOT_QUALITY`) says the building may be unused, not that its work is
  bad; making a 💎 building "better" for it would spend more on something nobody reads. It is not
  in `disliked`, probation or the survey — only in the weight by source, where the 🗓 Town retro
  sees it (and may remove the building);
- **"too expensive"** (the ↩ chip `cost`) is a 👎 for a 🪙 / ⚖️ building (a thrift retro is
  what it asks for), never a reason to enrich a 💎 one.

And quiet acceptances are evidence a result is *good enough*, not a shield:

- **🔧 Building retro** (`optimize.leader`): a 💎 building is "disliked this week" from a weight of 1
  (without `cost`); next, a supplier whose results came back as broken inputs weighing 1 this week
  (§4); then a ⚖️ one "disliked today" the same; "never rated" is less than 1 of either. A
  🪙 / ⚖️ building skips its thrift turn only for a 👍 or a merged pull request since its change
  (`liked(strong=True)`): carts accepted as they were are exactly when spending less is safe to try,
  and the thrift prompt keeps them as "what was liked".
- **Probation** (`evolution.verdict`): a change of the orks goes back when what the operator did
  since adds up to a 👎 — one reshaped file alone does not take it back; a reshape and a rework do.
- **🗓 Town retro**: the survey is skipped when the week's signals weigh 1 or more (the operator
  told the camp enough by working); the report shows each building's weight by source.
- **The Council's prompt** lists incidents with how they were told (`[loot.reshaped · format]`) and
  the operator's edit under them.
- **Examples in the orks' prompts** (`feedback.examples`, read by agents on roads, Workshops and the
  Council): the operator's own versions and 👍 first, merged pull requests next, quiet acceptances
  last — newest first within each — so a stream of accepted carts never pushes the best examples out.
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
   selecting that building sees it; after a day it is counted as unused (`sweep_unseen`, with the
   probation check). *(done)*
6. Second pass: a supplier with broken inputs is a Building retro candidate whatever it spends;
   a closed pull request weighs 0.5 and a duplicate nothing; the Lake judges on closing the app and
   after an edit left alone. *(done)*
7. Calibration: `orkcraft feedback calibrate` (§8). *(done)*

## 7. Known limits

- **Seen means selected.** A result counts as seen when its building is selected; one read on the
  hut or an open window without selecting it counts as not opened. That is why it weighs 0.1 and
  never counts as a dislike.
- **The writer takes the blame for what carried it on.** A Mill's chain that broke the format after
  an agent wrote the text: the agent is blamed, unless the operator says the inputs were wrong.
- **A closed pull request may be a duplicate** nobody labelled, of a task with another title; it
  weighs 0.5 for that.
- **The Lake judges an edit left alone for 10 minutes**: a file left half-done that long (a heading
  deleted, the new one not typed yet) is judged as it stands, and a judgement is never taken back.
- **A file brought to a Lake again** is the ork's again: its text then, the operator's notes in it
  included, is what later edits are compared with.

## 8. Calibrating the weights (`realm/calibrate.py`)

The weights of §2 are a first guess. `orkcraft feedback calibrate [--days N]` measures them on what
the camp kept (`incidents.jsonl`, the references): for each quiet signal, the 👍 / 👎 pressed on the
same building within 7 days of it are the ground truth — mostly 👍 agrees with a good signal, mostly
👎 with a bad one, as many of each says nothing. The share that agrees is the source's precision p,
and the weight it has earned is `2p − 1` (a coin toss is worth nothing, always right is a 👍), taken
at the Wilson lower bound of p (80 %) so that a few matches do not pass for certainty, never below
0.05; with fewer than 5 matches the source is left as it is. Beside it, `/week` is what the source
adds up to on one building in a week at its weight now — a frequent source near 1 acts alone,
which is what `ENOUGH` was meant to avoid. Nothing is changed: the operator reads the table and
edits `WEIGHTS`.

Its limit: the buttons are pressed rarely, and not at random — the operator presses them when
something is notable. So the matches are few and lean to the extremes; read a suggestion as a
direction (this source is noise, that one agrees every time), not as the number to type in.

Later: commits the operator added on top of an ork's pull request before merging (a measure of how
much it needed fixing); a merged branch reverted within a week; ✎ edit in the Clan Fire; "seen" as
opening a result rather than selecting its building.
