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

Carts are matched across rework rounds by `Payload.ref` (§4), so the attempt counter survives the
round trip through the source. A cart that comes back is always held again, whatever the rules.

**The way back is not a road.** Roads may not form a loop, so Loot hands the cart straight to its
source (`app.return_for_rework`): the source must redo delivered work (`TAKES_REWORK` — the
Barracks queues the task; a Clan Fire only reviews, so it is not one), else the latest building in the
cart's trail that does (past a Signpost, a Mill or a Clan Fire on the way) and keeps the `ref` on what it sends next. A
source that cannot take work back (a War Tent task, a plain building) makes the cart *needs you*
at once. `loot.rework` also goes down Loot's roads, for a Horn or a Herald.

Keys in the list: `a` accept · `r` reject a file / send a held cart back (asks for the reason) ·
`d` drop a cart · `u` restore a rejected file. Quick actions: ✓ Accept all (held carts), ✓ Accept
files.

## 4. The trail — metadata that travels with a cart

Every cart carries `Payload.trail`: the hops it went through, each
`Hop(building, orc, kind, tokens, cost, worktree, branch, outcome, at)`, and `Payload.ref`, a
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

- **Hut** — counters and the queue only: `3 held · 1 needs you`, the first titles, `passed: 12`,
  the total cost of what passed today. No preview.
- **Full window** — list | diff or preview | the trail with cost. Diffs, images and editing live
  here only.
- **Images** — shown only in the full window, by the terminal's own image protocol (kitty /
  sixel) when the terminal supports it, otherwise an `open in…` button hands the file to the
  system viewer. No block-character fallback.

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
3. **The full window** — diff, edit, the trail with cost; per-file decisions inside a held cart's
   worktree.
4. **Images** — kitty / sixel in the full window, or the system viewer.
