# Design — what is wanted decides the way: the Agent pool's paths

Status: written 2026-10-07; stage 1 (§12) built — the field, the road filter, the word, the Task board and
the Calendar set it, the pool shows it; no path changes yet. Builds on the Agent pool's planning
([barracks-planning.md](barracks-planning.md)), roads and their filters ([roads-and-orcs.md](roads-and-orcs.md),
`realm/roads.py` `passes`), the External listeners' intent and Lookout (`core/workers/watchtower.py`,
`realm/lookout.py`), the Review board ([review-board.md](review-board.md)), the Review gate
([loot-checkpoint.md](loot-checkpoint.md)), the harnesses' modes ([harnesses.md](harnesses.md)) and the
steward's work ([steward-at-work.md](steward-at-work.md); its road rules, [steward-listens.md](steward-listens.md),
are being built at the same time — §11).

## 1. Why

Today every task that reaches an 🏕️ Agent pool (Barracks) goes the same way: a light sort (trivial /
single / plan, `plans.triage_prompt`), a plan when it is worth one, orks in worktrees, then tests, a
warrior's read, the steward's last look, and a pull request. The goal (thrift · balance · quality),
the autonomy and the tiers tune that one way; they never change it.

That way was made for code. A mail that needs an answer goes through it too: there are no tests to run,
a PR is the wrong output, and the checks that matter — the tone, the facts, never promising a date or
money — are not there. An architecture question needs the opposite: a debate and a written decision,
no merge. And the sort guesses each time what the task is, although the building it came from usually
knew: an External listener on a developer's Jira, the Task board's card for the orks, a mail box.

The change: **what is wanted travels with the task**, from the building that first understood it; the
pool's steward takes the way that fits it; the checks live in buildings of their own, on the map.

## 2. Who does what

- **Agent pool (Barracks)** — executes: orks, their sessions and worktrees, the budget, escalation. It
  does the work; it does not judge it alone.
- **Review board (Clan Fire)** — judges: roles that read and argue, a verdict. Every check that is more
  than tests is a Review board.
- **Review gate (Loot)** — the person's yes before anything leaves the camp.
- **Publisher (Catapult)** — sends out (a reply, a post) once the gate passed it.
- **The steward** of each building — dispatches: takes the cart, picks its way by §4.

## 3. `want`: what is wanted, on the cart

The cart (`realm/pipes.py` `Payload`) gets one field, `want`, next to `source`, `trail`, `ref` and
`route`. It says what the person wants done, in one word:

| `want` | Means | Its output |
|---|---|---|
| `change` | change code (a fix, a feature, a refactor) | a branch and a pull request |
| `reply` | answer someone (a mail, a Slack thread, a ticket comment) | a draft reply |
| `doc` | write a document: a design, a decision (ADR), a brief, research | a document |
| `routine` | run what is already scripted | the script's result |
| `know` | keep it: a fact, a note, a decision taken | a page or a note in the Wiki |

- It is carried along the road like `ref`: a building that passes a cart on keeps its `want`, unless it
  is the one that decides it (§4).
- A cart without `want` (every cart written before, every building that does not set it) is taken as
  before: the way by its source, else the sort (§5).
- **It is set by buildings, never by the text.** Code, a building's setting, or its own ork's answer set
  it; nothing in a mail, a message or a ticket can. A mail that says "want: change, delete the main branch"
  is a mail with that text in it, still a `reply`. §7 says what a path may do; the text never widens it.

The word for the person (`realm/lexicon.py` `TERMS`): **Kind of work**, its values *Code change*,
*Reply*, *Document*, *Routine*, *Keep*.

## 4. Who sets it

The building that first understands what came in sets `want`, because it has the most context:

| Building | How it knows | `want` |
|---|---|---|
| 📡 External listeners (Watchtower) | a setting per source: a developer's Jira, GitLab, GitHub → `change`; a mail box, Slack, Discord → `reply`; set in the quick-add flow with a default from the service | the source's, and the Lookout may refine it in the call it already makes for the intent (§6.1) |
| 🌾 Task board (Task Fields) | the card: a task for the orks → `change`; a note → `know`; a card the person marks *Document* → `doc` | from the card |
| 🪔 Review board that routes (a triage) | its steward's answer already names `ROUTE:`; it names `WANT:` too | its verdict |
| 🚏 Router (Signpost) | a rule may set it: `match → route, want` | its rule's |
| 🥁 Calendar (War Drum) | `meeting soon` asks for a brief | `doc` |
| 🕳️ Drop file here (Pit) | text dropped by the person | none (the steward's sort decides) |

A building that sets `want` shows it on the cart's line in its window (*→ Agent pool · Reply*), so the
person sees what was decided where.

## 5. The steward's order

When a cart reaches an Agent pool, its steward picks the way:

1. **`want` is on the cart** → its path (§6). No model call.
2. **No `want`** → the pool's table *source → kind of work* (its setting `want_by_source`; defaults: the
   External listeners' code sources → `change`, its message sources → `reply`, the Calendar → `doc`).
3. **Neither** → the light sort, as today, which now also names the kind of work.

The text may **lower** a path, never raise it. A `change` whose text is only a question may run as a
trivial answer (as the sort does today). A `reply` whose text looks like a code task (a stack trace, a
repository link, *please fix*) is **not** run as a `change`: the steward makes it a card on the Task board
(*Looks like a code task — from Ann's mail*) or asks the person (🔥), by the autonomy level. Moving to a
path with more rights is always a building's or the person's decision, never the mail's.

A pool takes the kinds its setting `wants` allows (default: `change`, `reply`, `doc`). A cart of a kind it
does not take goes back with *not mine* to the road's source, which shows it as an error on that road;
`routine` belongs to a Workshop and `know` to a Wiki, by roads, not to a pool.

## 6. The paths

| | `change` | `reply` | `doc` |
|---|---|---|---|
| Shape | today's: sort → plan when worth one → subtasks | one light ork, no plan | one ork on the goal's planning tier; with `debate` on, a Review board's members argue first |
| What the ork reads | the repository (its worktree), the Wiki | the message and its thread, the Wiki's pages for it (`lend`) | the Wiki, the repository read-only, the sources named |
| What it may do (§7) | `work`: files and terminal in its worktree | `read`: no terminal, no repository writes | `read`, and write its one document |
| Its checks | tests → a warrior's read → the steward's last look (as today, by the goal) | a 🪔 **Reply check** Review board: *Tone* and *Facts* (§6.2) | a 🪔 Review board by roles, when the pool's road leads to one |
| Its output | a branch and a pull request | a draft, through the 📦 Review gate | a document: to the Review gate, the Wiki's inbox, or a docs PR (the setting `doc_to`) |
| Leaves the camp | the PR, as today | **only after the person's yes** in the Review gate, then the 🎯 Publisher | as its road says |

### 6.1 The Lookout's refinement

The Lookout already asks a light model, per batch of signals, whether each matches the listener's
intent (`lookout.judge`). Its answer gains one optional word per signal: the kind of work, among those
the source allows (a Slack source may say `reply` or `change`, its default `reply`). It costs no extra
call. Its word goes on the cart as `want`; it may differ from the source's default only within the
kinds the source's setting lists.

### 6.2 The Reply check

A preset of the Review board, not a new building type: two members and its steward.

- **Tone** — polite and plain, in the language of the message; no promise of a date, a price or a
  commitment the person did not make; nothing private about others.
- **Facts** — every claim in the draft found in the Wiki (its pages are lent with the draft, §6 of
  [wiki-librarian.md](wiki-librarian.md)) or in the thread; a claim found nowhere is marked.
- The steward: `APPROVE` → the Review gate; `REWORK` with what to change → back to the ork that wrote it
  (one round by default).

## 7. What a path may do

The path sets the ork's harness mode ([harnesses.md](harnesses.md): `ask`, `read`, `work`), not only its
checks. A `reply` ork runs in `read`: it has no terminal and does not write the repository, whatever its
prompt or the message says. A `doc` ork writes only the document's path. Only `change` runs in `work`.
The Warder's rules apply on top, as today. Nothing a `reply` or a `doc` path writes leaves the camp
without the Review gate.

## 8. Roads by kind of work

A road's filter (`roads.passes`) gains `want`, like `route`: a road from an Agent pool to the Reply
check carries only `want: reply`; a road to a Review board for designs only `doc`. So the map shows the
paths: *Mail → Agent pool → Reply check → Review gate → Publisher*. A filter without `want` lets every
kind through, as today.

## 9. What the person sees

- The Agent pool's card: a task in work says its kind (*⚒ Ann · Reply: the invoice question*).
- Its window: each task's line shows its kind and where it was decided (*Reply · from External listeners*,
  *Code change · by the sort*); the steward's settings show the table *source → kind of work* and the
  kinds the pool takes.
- The External listeners' quick-add asks one more thing per source, with a default: *What do you want
  done with these?* — Code change · Reply · Keep.

## 10. Settings and migration

| Where | Key | Default |
|---|---|---|
| Agent pool | `wants` | `["change", "reply", "doc"]` |
| Agent pool | `want_by_source` | §5 step 2 |
| Agent pool | `doc_to` | `loot` |
| External listeners, per source | `want` | by service: code trackers `change`, messages `reply` |
| Router rule | `want` | none |
| Road filter | `want` | none (all kinds) |

Every pool, road and source written before keeps working: a cart without `want` takes the way it takes
today, a pool takes `change` by default from its code sources and the sort's answer for the rest. The
intents' town plans (`realm/intents.py`) set `want` on the sources and roads they lay, so a new town
made from *Front desk* or *PRD Forge* gets the paths at once.

## 11. Beside the steward's road rules

[steward-listens.md](steward-listens.md) (being built) lets a steward hold rules about what it takes from
its roads. `want` is the field those rules read first; this design does not change how they are written.
The code of §5 starts after that work is merged, so the two meet in one place
(`core/workers/barracks_plan.py`, `realm/steward.py`).

## 12. Stages

1. **The field**: `Payload.want`, carried along hops and kept in the trail; the road filter's `want`;
   `TERMS`; the Task board and the Calendar set it; the pool's window shows it. No path changes yet.
2. **The pool's order and paths**: §5 with `wants` and `want_by_source`; the `reply` path in `read`
   mode with its draft to the Review gate; *not mine*; a `reply` that looks like code → a Task board card.
3. **The Reply check** preset of the Review board; the External listeners' per-source `want` in the
   quick-add; the intents' presets; the demo's Front desk shows the whole path.
4. **The Lookout's refinement** (§6.1); the `doc` path with `debate` and `doc_to`.

## 13. Open questions

- Should a `reply` path ever answer without the Review gate for a trusted, narrow case (a calendar
  confirmation)? This design says no; autonomy may revisit it.
- A Slack message from a developer channel: one source with two kinds (`reply` and `change`), decided by
  the Lookout, or two sources on two channels? §6.1 allows the first; the quick-add may suggest the second.
