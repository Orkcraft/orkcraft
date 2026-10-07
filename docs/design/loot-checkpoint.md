# Design — 📦 Loot: the review checkpoint

Status: design notes, written 2026-10-04. Stages 1 (the trail) and 2 (the checkpoint) are implemented;
stages 3–4 are not.
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
- **✎ edit** — the full-window view lets the person edit the text (or the file) before accepting.
- **Rework limit.** A cart goes back at most **3 times** (`max_rework`, configurable) or until the
  chain spent `rework_tokens` tokens. After that it is not sent back again: it stays in the queue
  marked `needs you`, highlighted on the hut, for the person to review and fix by hand.
- **Reminders** — a held cart sets the hut on 🔥 like an ork waiting for an answer: orange, red,
  then the roof burns (`realm/modes.py`), respecting quiet hours; `!` (🔥 Orders) lists it.

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

**A cart's files.** Under each waiting cart the list shows the files its task committed on its
branch: the latest hop that names a worktree and a branch (`gate.branch_of`), read there as
`git diff --name-status <base>...<branch>` (`generated.Branch`; `origin/<base>` when the worktree
has it). Highlighting one shows its diff, or its content when the diff is binary. The rules
(`paths`, `max_files`) read these files as well as the worktree's uncommitted ones.

Every decision is also feedback for the building that made the cart (the last hop of its trail):
see `native-feedback.md`.

## 4. The trail — metadata that travels with a cart

Every cart carries `Payload.trail`: the hops it went through, each
`Hop(building, orc, kind, tokens, cost, worktree, branch, outcome, at, base)`, and `Payload.ref`, a
stable id of the thing being worked on.

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
- **Full window** — list | diff or preview | the trail with cost. Diffs, images and editing live
  here only.
- **Images** — the preview names a picture by its first bytes: `PNG image · 512×512 · 34.2 KB ·
  o opens it`. `o` hands the highlighted file to the system viewer (`open` on macOS, `xdg-open`
  on Linux); a file that is only on a task's branch is first copied out with `git show
  <branch>:<path>` into a temporary folder, under its own name. Later: the picture inside the
  window by the terminal's own image protocol (kitty / sixel) when the terminal supports it,
  `o` otherwise. No block-character fallback.

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
   each with its diff or content *(done)*. Still to do: editing, per-file decisions inside a held
   cart's branch.
4. **Images** — size, type and dimensions in the preview, `o` opens any file in the system viewer
   (a branch's file copied out first) *(done)*. Still to do: kitty / sixel inside the window.
