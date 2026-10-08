# Design — the Agent pool remembers its designs and sees work that collides

Status: written 2026-10-08 and implemented: `realm/claims.py` (§3, §4), `realm/briefs.py` (§5, §6),
`core/workers/barracks_claims.py` (the worker's side), `jobs.TaskGit.would_conflict` / `commit_file`,
tests in `tests/test_pool_claims.py`. Builds on the Agent pool's planning
([barracks-planning.md](barracks-planning.md): the plan, `touches`, `plans.ready`), its review
(`core/workers/barracks_review.py`) and the Task board's join of related cards
([settle-and-join.md](settle-and-join.md), which this note does not change — §9).

## 1. Why

The steward of an 🏕️ Agent pool (Barracks) already plans a big task: subtasks, a brief each, the files
each one `touches`, what waits for what. Two things are missing.

- **The plan is forgotten.** It lives on the task in `barracks.json` and a line in `decisions.jsonl`;
  once the task is done nothing says *why* the code is the way it is. The next task on the same feature
  starts blind, and its steward cannot see that it contradicts what was decided a week ago.
- **Collisions are seen only inside one task.** `plans.ready` keeps two parts of one plan that touch the
  same files from running at once. Two *different* tasks — in one pool, or in two pools on one
  repository — that change the same area run side by side; the second learns of the first at its pull
  request's merge conflict, after both are built.

The change, in four steps (§10): the pool keeps **areas in work** across every task on a repository and
says when a new one lands on an area taken (§3–4, no model); a planned task leaves a **design brief** in
its pull request (§5); a new task is read against the briefs it concerns (§6); a change in a brief's area
keeps the brief true (§7).

The point is not the document. It is that the steward knows what is being done and what was decided, and
says so before the work, not at the merge.

## 2. Words

In `realm/lexicon.py` `TERMS`:

| id | the word | what it is |
|---|---|---|
| `claim` | **Area in work** / Areas in work | the files and folders an open task changes, kept while its work is not merged |
| `overlap` | **Overlap** / Overlaps | a task whose area meets another task's area in work |
| `design_brief` | **Design brief** / Design briefs | the short design a planned task leaves in its pull request |

## 3. Areas in work

One file per repository, `.orkcraft/claims.json`, shared by every Agent pool on it (two pools on one
repository see each other). A claim is:

```json
{"key": "camp:3f2a91c0", "building": "camp", "task": "3f2a91c0", "title": "Build the export",
 "paths": ["src/export/", "docs/export.md"], "guessed": false, "branch": "pool/camp/3f2a91c0",
 "status": "work", "pr": "", "brief": "docs/design/build-the-export.md", "since": "2026-10-08T10:12:00"}
```

- **Where the paths come from.** A plan: every part's `touches`. A task that runs whole: the sort's guess
  (the triage's answer gains `"touches"`, in the same light call; `guessed: true`). Once its work is done,
  what its branch really changed (`changed_files` of the diff) replaces the guess, with `guessed: false`.
- **How long a claim lives.** `status` is `work` while the task is queued, planned or worked, `review`
  once its pull request is open (or its branch waits for one), and the claim is **released** when the pull
  request is merged or closed (`settle_prs`), the task fails, or it is done with no pull request (a local
  document, an answer). A claim older than `claim_days` (14) is released as stale: a PR left open for
  weeks must not hold an area for ever.
- **Paths are compared as `plans.overlap` does** (a folder holds what is under it). A path that would
  claim nearly everything — the root, `.`, `src/`, any single top-level folder that is not a file — is
  dropped from a claim (`claims.too_wide`): it would overlap every task and teach the person to ignore the
  mark. A task whose every path is too wide claims nothing and says so in its decision.

## 4. Overlap: what the pool does

When a task's claim is written or changes (the sort, the plan, the end of the work), the pool compares it
with every other claim on the repository. A meeting is an **overlap**:

| the other task is | this task | the decision (`decisions.jsonl`, action `overlap`) |
|---|---|---|
| in `work` (being built) | **waits** until it leaves `work`, as a part waits for another part that touches its files — unless the setting `claims` is `flag` | *waits for “Build the export” (src/export/)* |
| in `review` (a PR open, not merged) | goes on, told: the other branch, its PR, the paths; after its work the pool tries both branches together (below) | *overlaps “Build the export” — PR open* |

- **What the ork is told.** Its prompt gets *## Work on the same files* — each other task, its branch, its
  pull request, the paths, its brief when it has one — and the order to keep its change compatible and
  small there. The review prompt gets the same, so the steward judges with it.
- **Tried together.** After a task's work, when an overlapping branch is in `review`, the pool asks git
  whether the two would merge (`TaskGit.would_conflict`: `git merge-tree --write-tree --name-only`, writes
  nothing). Conflicting files land on the task (`overlaps[].conflicts`) and in the review prompt; the pull
  request's body names them. The task is **not** sent back for it: the other PR may never be merged.
- **Waiting never deadlocks.** Only the newer task waits for the older (by `since`); a wait ends when the
  other claim leaves `work` or is released, and at most after `claim_wait` minutes (60), after which the
  task goes on flagged.
- **Parts of one plan** keep `plans.ready` as it is; a part also waits for another task's claim in `work`
  on its `touches`.
- **What the person sees**: the task's card in the GUI says **⚠ overlaps “X”**; its detail lists each
  overlap with its paths, its PR and the conflicting files; the pool's window lists the **Areas in work**.

Setting `claims`: `wait` (default), `flag` (never wait, only say), `off`.

## 5. The design brief

A task the steward **plans into two parts or more** leaves a design brief. It costs no extra call: the plan
the steward already writes gains one optional object, `design`:

```json
{"subtasks": [ … ],
 "design": {"why": "…", "decisions": ["…"], "invariants": ["…"], "out_of_scope": ["…"]}}
```

The code (`briefs.render`) writes the brief from it and from what the plan already holds — the request,
the parts, their `touches` — as Markdown with a front matter the pool reads back:

```markdown
---
orkcraft: brief
task: 3f2a91c0
pool: camp
touches: [src/export/, docs/export.md]
---
# Build the export

## Why
## Decisions
## Invariants
## Out of scope
## Parts
## The request
```

- **Where**: `<briefs_dir>/<slug of the title>.md`, `briefs_dir` default `docs/design`; a name taken by
  another brief gets `-2`, `-3`.
- **How**: committed on the task's branch before any part starts (`TaskGit.commit_file`: plumbing — no
  checkout, no worktree), so every part is cut from a branch that already holds it, and the one pull
  request carries it next to the code. Merged, it is in the repository: versioned with the code, read in
  review, found by `git blame`.
- **When not**: `briefs: false`, the sandbox, a pool without worktrees, a task that runs whole. Under
  🪙 thrift the brief is written all the same — it is no extra call — but the plan prompt asks for `design`
  in two lines.
- **Untrusted.** The `design` object is the steward's text built from the request: it is written as Markdown
  in a file, never run, never read as settings; a brief cannot widen what a task may do (as
  [barracks-flows.md](barracks-flows.md) §3 says of `want`).

## 6. A new task is read against the briefs

The pool reads the briefs in its repository's base (`briefs_dir` in the main checkout: the merged ones); a
brief still on a branch in `review` is named, with its path, in the overlap the task is told of (§4).
`briefs.relevant(briefs, paths, text)` picks at most three: those whose `touches` meet the task's paths
first, then those that hold at least `WORDS_SHARE` (40 %, two words or more) of the task's words
(`barracks.words`) — a long brief is not penalised for its length.

- **The plan** gets them under *## Designs this touches* (each brief, cut to 3000 characters) and may answer
  `"conflicts": [{"with": "<brief path>", "why": "…"}]` — the request goes against a decision written there.
- **A task that runs whole** gets the briefs its sort's paths meet in its ork's prompt.
- **A conflict** is a question for the person, as autonomy says ([barracks-planning.md](barracks-planning.md)
  §2): ⛓️ In chains the task waits (🔥 *“Build the import” goes against docs/design/build-the-export.md:
  …* — Enter goes on, anything else is written into the task and it is planned again); 🕰 On the clock it
  waits its minutes, then goes on flagged; ⛓️‍💥 Unchained it goes on flagged at once. It is always in the
  decision and on the task.

## 7. A brief stays true

A brief out of date is worse than none: the steward would quote it with confidence. So when a task's diff
changes files in a merged brief's `touches` and does not change the brief itself, the review prompt (the
steward's read of a whole task, and its last look at a planned one) gets the brief and the rule:

> This change touches the area of `docs/design/build-the-export.md`. If it changes what the brief says,
> answer `REWORK: update docs/design/build-the-export.md: …`; if the brief still holds, add the line
> `DESIGN: unchanged` after ACCEPT.

An accept without that line and without the brief in the diff is accepted all the same, and the decision
says *design not confirmed* — the line is a check the steward makes, not a gate on the work. The pull
request's body names the briefs and what became of them (*updated* · *unchanged* · *not confirmed*).

## 8. Settings

| Where | Key | Default |
|---|---|---|
| Agent pool | `claims` | `wait` (`flag`, `off`) |
| Agent pool | `claim_wait` | `60` minutes |
| Agent pool | `claim_days` | `14` |
| Agent pool | `briefs` | `true` |
| Agent pool | `briefs_dir` | `docs/design` |

A pool written before gets the defaults: its tasks start claiming, and its plans start leaving briefs. A
task saved before has no `overlaps`, no `brief`: it loads as it was.

## 9. Beside the other joins

- [settle-and-join.md](settle-and-join.md) joins two cards about **one wish** before they leave the Task
  board, by their words. This note is about **two wishes on one area** inside the pool, by their paths. A
  card joined there arrives here as one task and claims once.
- The foreman's ♻ affinity (an ork that knows the work takes it) is unchanged: a task that waits for an
  overlap still goes to the ork that knows the area when it is free.

## 10. Stages

1. **Areas in work** (§3–4): `claims.json`, the sort's `touches`, the wait and the flag, `would_conflict` by
   `merge-tree`, the release on merge, close, failure and age; the GUI's ⚠ and the list. No model call.
2. **The design brief** (§5): `design` in the plan, `briefs.render`, `commit_file` on the task's branch.
3. **Briefs read at the plan** (§6): `relevant`, *Designs this touches*, `conflicts` by autonomy.
4. **A brief stays true** (§7): the review's rule, `DESIGN: unchanged`, the PR body.

## 11. Open questions

- A claim per repository assumes the pools share one checkout's `.orkcraft/`. Two machines on one
  repository do not see each other's claims; the open pull requests on GitHub would be the shared list.
- Should a brief move to the Wiki as well (its librarian lends pages today)? This note keeps one copy, in
  the repository; the Wiki may link to it.
