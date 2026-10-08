# Design — 📦 Loot: the review checkpoint

Status: design notes, written 2026-10-04. Stages 1 (the trail), 2 (the checkpoint), 3 (the full window)
and 4 (images) are implemented in the GUI; the TUI is deprecated and keeps what it had (§7).
Builds on roads and handlers (`roads-and-orcs.md`), the 🔥 of a waiting ork and the 🪙 ledger.

## 1. What Loot is

Loot is **not a store**. It is a checkpoint on a road: whatever another building produced (docs
from the Barracks, a ticket an agent changed, files in a worktree) passes through it on the way
to its consumer (Confluence, Jira, the Forge). Rules decide what passes at once and what waits
for a person.

```
 Barracks ──cart──▶ [ 📦 Loot: rules ] ──passed──▶ Confluence / Jira / Forge
                          │
                          ├─ held ──▶ review queue: ✓ accept · ✗ reject · ✎ edit
                          │
                          └─ rework ──▶ back to the source with the reason (≤ 3 times)
```

The built-in 📦 Artifacts building stays a file browser (`./loot/`, `./docs/`); it is one of the
sources Loot can take (its `on_selection_change` sends a file).

## 2. Rules — what needs review

Chosen when the building is created (the Build Wizard), as a form of ready signals with
thresholds; an expression field only in an advanced section. A cart is **held** when any enabled
signal fires, otherwise it **passes** untouched.

| Signal | Config | Reads |
|---|---|---|
| always / never | `review: always \| rules \| never` | — |
| from these sources | `sources: [building ids]` | `payload.source`, the trail |
| these paths | `paths: ["auth/**", "migrations/**"]` | file payloads, files of a worktree |
| chain cost | `max_cost_usd`, `max_tokens` | the trail's totals (§4) |
| size | `max_files`, `max_lines` | the diff of the worktree in the trail |
| the run did not finish clean | `on_failed: true` | the last hop's outcome |
| leaves the town | `external: true` | the target is an egress building (Catapult, a connector) |

The road filters (`roads.py`, `_needs_meta`) already match on payload metadata; the rules reuse
that matching, not a language of their own.

## 3. The review

- **One decision per cart.** A cart is accepted or rejected as a whole; inside it single files
  can be rejected (rolled back, kept under `rejected/`) and the rest goes on.
- **✓ accept** sends `loot.passed` with the original payload and its trail. Loot does not commit;
  committing is the Forge's job.
- **✗ reject** with a reason sends `loot.rework` back to the source (a road Loot → source).
- **↺ restore** brings a rejected file back from `rejected/`.
- **✎ edit** — the full-window view lets the person edit the text (or the file) before accepting. A text
  cart is edited in its window — *Edit*, then *Save* or *Accept this version* — or in Lake; both write its
  draft file (`LootWorker.save_draft`, `draft_path`), so Accept and Accept all take the person's version
  either way. A cart too long for the window is edited in Lake; a file cart is opened there.
- **A file of a held cart's branch** — *Reject this file* puts it back on the branch as the base has it
  (removed, if the task added it) by one commit on the branch (`generated.Branch.reject`; the branch is
  never checked out for it, and a worktree that has it checked out gets the file, unless the file has
  changes there nobody committed). Its content on the branch is kept under `rejected/carts/<cart>/`, the
  cart remembers it (`Item.rejected`), the maker hears it (👎 0.34, `loot.file_rejected`) and
  `generator.rejected` goes down the roads. *Bring it back* commits the kept copy back (a deletion is
  deleted again), not over a newer change of that file on the branch. Only a cart that waits for the
  person has its files decided: one in rework is with its ork. A rework tells the ork which files were
  rejected, so it leaves them.
- **Rework limit.** A cart goes back at most **3 times** (`max_rework`, configurable) or until the
  chain spent `rework_tokens` tokens. After that it is not sent back again: it stays in the queue
  marked `needs you`, highlighted on the hut, for the person to review and fix by hand.
- **Reminders** — a held cart sets the hut on 🔥 like an ork waiting for an answer: its ork asks
  (`LootWorker.orders_alert`), the card glows, then the roof burns, respecting quiet hours; Answers
  lists it — the first cart, why it waits and what else waits — with *Open it* to go to the
  building and *Stop asking until another cart comes first*. The reasons name buildings by their
  titles.

**A draft waiting for approval.** A cart whose last hop ended `approval` (a Barracks ork's post to Jira or Confluence, sent as `pool.question`) is always held, whatever the rules. ✓ accept also tells its maker directly (`app.return_approved`), and the ork posts the accepted text, edits included; ✗ reject sends the draft back with the reason.

Carts are matched across rework rounds by `Payload.ref` (§4), so the attempt counter survives the
round trip through the source. A cart that comes back is always held again, whatever the rules.

**The way back is not a road.** Roads may not form a loop, so Loot hands the cart straight to its
source (`app.return_for_rework`): the source must redo delivered work (`TAKES_REWORK` — the
Barracks queues the task; a Clan Fire only reviews, so it is not one), else the latest building in the
cart's trail that does (past a Signpost, a Mill or a Clan Fire on the way) and keeps the `ref` on what it sends next. A
source that cannot take work back (a War Tent task, a plain building) makes the cart *needs you*
at once. `loot.rework` also goes down Loot's roads, for a Horn or a Herald.

Keys in the list: `a` accept · `e` edit a text cart and accept your version · `r` reject a file /
send a held cart back (a chip for the reason, and a note) · `d` drop a cart · `u` restore a
rejected file · `o` open the highlighted file in the system viewer. Quick actions: ✓ Accept all
(held carts), ✓ Accept files.

**Accept all asks first.** It lists what it would accept — each held cart with its type, the
drafts that go out as soon as they are accepted (and where), the person's edits — and accepts
exactly those, not a cart that came while the dialog was open. Each cart is accepted as accepting it
alone would be: the person's edit of it (its draft file), a draft handed back to its ork to be
published. **Drop asks too**: a dropped cart is gone for good and its maker hears it was not wanted.

**A cart's files.** Under each waiting cart the list shows the files its task committed on its
branch: the latest hop that names a worktree and a branch (`gate.branch_of`), read there as
`git diff --name-status <base>...<branch>` (`generated.Branch`; `origin/<base>` when the worktree
has it). Highlighting one shows its diff, or its content when the diff is binary. The rules
(`paths`, `max_files`) read these files as well as the worktree's uncommitted ones.

Every decision is also feedback for the building that made the cart (the last hop of its trail):
see `native-feedback.md`.

## 4. The trail — metadata that travels with a cart

Every cart carries `Payload.trail`: the hops it went through, each
`Hop(building, orc, kind, tokens, cost, worktree, branch, outcome, at, base, ms, model, decision, round,
run)`, and `Payload.ref`, a stable id of the thing being worked on.

- `at` is when the hop ended, `ms` how long the cart was in that building (`Hop.started` = `at` − `ms`:
  the first hop's is when the request came in); `model` what did the work (`a+b` when steps differ);
  `decision` the building's own call in one line of at most 80 characters (a Clan Fire's tally and route,
  a steward's accept / rework, a plan's parts, or why a run did not finish); `round` the rework round
  (unset the first time); `run` the building's own record of the work — the handler run, the task, the
  discussion — where the full input, output and reasoning are.
- The trail never goes into a prompt, so a hop costs no tokens; it stays small all the same (a few
  short fields, nothing said is not stored), and anything longer than a line stays in the record `run`
  names. Loot's chain table shows how long each hop took, on what, and what it decided.

- A handler run merges the trails of the carts it ran on and appends its own hop (its tokens and
  cost); its output, and whatever its building sends next, carries that trail.
- A finished War Tent task adds a hop with the ork and its worktree / branch.
- Typed buildings that pass a cart on (`emit_typed(..., trail=...)`) keep it.
- `pipes.trail_totals(trail)` gives the chain's tokens and cost; `pipes.trail_line(trail)` the
  readable chain: `Barracks 12k tok $0.08 → Council 40k tok $0.31 = 52k tok $0.39`.

This replaces reading a cost out of the text (`$1` in a shell snippet is not a cost), and gives
authorship: the files to review are the files of the worktree named in the trail, not every
change in the working tree.

## 5. The views

- **What a cart is** — every cart says it before it is opened (`realm/content.py`): a **message**
  (Slack, mail, Telegram…), a **doc** (Confluence, Notion, a Markdown page), a **ticket** (Jira,
  Linear, an issue), **code**, an **image**, **data** (JSON, CSV…) or **text**. Nothing in a cart says
  so on its own; it is read off what the cart carries: a draft waiting for approval names it first
  on its `PUBLISH: <kind>, <where>` line (`PUBLISH: ticket, Jira, project APP` — the orks are told
  the kinds, `barracks.PUBLISH_KINDS`; an older draft without one is read by its place), and the
  place is shown beside it (`Message · Slack #release`); a file cart by its
  name, the files its work committed on its branch, else the text (JSON is data, Markdown with a
  heading a doc). A card in the queue shows the type, where it goes, the title and the first lines of
  what goes out — a draft without the ork's report — or thumbnails of its pictures. The closed card
  names the first waiting cart's type and shows the waiting carts' pictures small: a picture is judged
  by looking at it. An open cart shows what goes out first, rendered (Markdown with raw HTML off), the
  pictures large, the whole cart with the report folded under it.
- **Hut** — counters and the queue only: `3 held · 1 needs you`, the first titles, `passed: 12`,
  the total cost of what passed today. No preview.
- **The panel** — two tabs: the **carts** (one flow of cards, the ones that need you first, what
  passed folded under them) and the **changed files** of the working tree, which no cart brought
  (accepted, rejected and brought back one by one). A cart opens over the list; a decision on it —
  Accept, Rework, Drop — opens the next one that waits, and a changed file accepted or rejected the
  next file. A held cart's first act is Accept; one that **needs you** ran out of rounds, so its first
  act is Edit (a file: open it) and Accept as it is comes second; once edited, Accept takes the edit.
- **Full window** — the list on the left, the chosen cart beside it: what it is in the middle (its
  text, its pictures, its branch's files with their diffs), why it waits and the chain with each
  step's cost on the right.
- **The rules** are read out in plain words in the Rules dialog (`gate.describe`): what waits, what
  passes by itself, how often a cart goes back; below them the steward is asked to change them.
- **Images** — the preview names a picture by its first bytes: `PNG image · 512×512 · 34.2 KB ·
  o opens it`. `o` hands the highlighted file to the system viewer (`open` on macOS, `xdg-open`
  on Linux); a file that is only on a task's branch is first copied out with `git show
  <branch>:<path>` into a temporary folder, under its own name. In the GUI the picture shows inside
  the window, over what is said of it (without the `o` hint): a cart's, a file of its branch, a changed
  file of the working tree (up to 2 MB). The terminal's own image protocol (kitty / sixel) was planned
  for the TUI and is not built: the TUI is deprecated. No block-character fallback.

## 6. Events

| Event | Kind | When |
|---|---|---|
| `loot.passed` | as received | a cart passed (by the rules or accepted) |
| `loot.rework` | text | a cart sent back with the reason |
| `loot.needs_you` | text | the rework limit is reached |
| `generator.accepted` / `generator.rejected` | file | a single file decided (kept) |

## 7. Stages

1. **The trail** — `Hop`, `Payload.trail` / `ref`, handler runs merge and extend it, the vault
   records the chain's tokens and cost instead of parsing `$…` out of the text. *(done)*
2. **The checkpoint** — rules in the wizard, the queue, `passed / rework / needs_you`, the rework
   limit, 🔥 reminders, ↺ restore; the rules read the files of the trail's worktree; Loot's own
   `loot/` is never up for review; file names are read unescaped. *(done)*
3. **The full window** — diff, the trail with cost; a held cart's branch files listed under it,
   each with its diff or content; a text cart edited in the window; one file of a held cart's
   branch rejected and brought back while the rest goes on *(done, GUI)*.
4. **Images** — size, type and dimensions in the preview, `o` opens any file in the system viewer
   (a branch's file copied out first) *(done)*. The picture inside the window: the GUI shows it — a
   cart's, a file of its branch, a changed file of the working tree *(done)*. Kitty / sixel in the
   terminal is not built: the TUI is deprecated (`calm-town.md` §9) and gets fixes only.
