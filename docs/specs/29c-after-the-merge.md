# Spec 29c — after the merge, decisions in one tap (decisions §44)

Two builders at once; **this file is the contract** (names and data fixed). Read decisions §43–§44,
`docs/specs/29a-board-focus.md` (the board's data and commands), and the board as it is now (v4 kit, spec 29b).
Wording: CLAUDE.md (the Taskmaster is the board's ork; interface in English).

| part | branch | files (only these, plus their tests) |
|---|---|---|
| **A. Host** | `spec/29c-host` | `realm/ideas.py`, `realm/idea_git.py`, `core/idea_keeper.py`, `core/idea_runner.py`, `gui/ideas.py`, `gui/mobile.py`, `settings.py` |
| **B. Screens** | `spec/29c-screens` | `gui/static/js/board/*`, `gui/static/pwa/board.js`, `gui/static/pwa/app.css`, `pwa/sw.js` |

B works against a stub with the shapes below until A is merged.

## 1. Merged without your eyes
- The runner appends each merged task to `<state_dir>/ideas/merged.jsonl`: `{"idea", "task", "title", "goal"` (the
  brief's first line)`, "subject", "commit", "tests"` (e.g. "14 passed")`, "cost", "estimate"` (the task's share of
  the plan's estimate, `[low, high]`)`, "at", "seen": false, "reverted": false}`.
- `ideas.board` → `today.merged`: the unseen, newest first (max 20) and `today.merged_more` (how many beyond).
- `ideas.seen {"idea"?, "task"?}`: marks one, or all when no args. `{"ok": true}`.
- `ideas.revert {"idea", "task"}`: `git revert --no-edit <commit>` in a worktree off `merge_into`, the gate (critical
  tests), fast-forward and push as the runner does; the line gets `reverted: true`, the task's state `reverted`, the
  idea goes to Needs you with *Reverted: <subject>* only if the revert fails (conflict or red: `{"error": …}`, `main`
  untouched).
- Screen: in Today under Needs you, **Merged without your eyes · N**: a line per task — goal (bold), subject,
  `tests · $cost (est. $a–b)`, commit short sha; **Revert** (asks once: *Revert “subject” on main?*) and **Looked**;
  **Looked at all** on the group. Phone: the same, Revert under a long-press or a ⋯ menu, never a single tap.

## 2. Questions as choices
- The batch's answer gives `questions: [{"text", "options": [2–4 short strings], "recommended": <index>, "why"}]`
  (strictly parsed; a question with no options keeps a free answer). Stored in `<state_dir>/ideas/<slug>/questions.json`
  as `[{"id": "q1", "text", "options", "recommended", "why", "answer": null}]`; the page's *Open questions* keeps the
  texts as today.
- `ideas.page` → `questions` (that list). `ideas.answer {"slug", "id", "choice"?: int, "text"?: str}` records the
  answer; when every question is answered, one `say` goes to the Taskmaster with all of them ("Q → A" lines) and the
  questions are cleared. `{"ok": true, "left": n}`.
- Screen: on the idea and on its Needs you card, each question as chips, the recommended one marked
  (*recommended*), its why on hover (desktop) or a tap on ⓘ (phone); *Other…* opens a one-line answer. Chips ≥ 44 px.

## 3. A spec as heavy as the idea
- `ideas.page` → `sections` gains `"shown": bool`: for size `S`, Gist, In, Out and Stages are shown, the others only
  when they hold text; for `M`, `L` and no size, all. The keeper's prompts ask an S idea for those four only.
- Screen: hidden sections behind one **More sections** link at the end.

## 4. Push only what blocks, the rest in a digest
- `mobile.news`: `kind: "idea"` only for `asks`, `plan`, `failed`, `held`. `done`/merged no longer push; a
  `kind: "digest"` news `{"merged": n, "done": n, "spent": "$x"}` goes once at each of `ideas.digest_hours`
  (default `[9, 13, 18]`, local time), only when there is something unseen.
- Settings: `ideas.digest_hours` (list of ints 0–23), cleaned like the other `ideas.*` keys.

## 5. The contract of silence
- Screen only: one muted line at the foot of Today (desktop) / of the Today tab (phone): *The orks ask you when a
  question, a plan, a red gate twice, a conflict or a spent window needs you. Otherwise they work and merge.*

## Tests
A: unit tests for merged.jsonl, seen, revert (temp repo + bare origin: revert lands; a conflicting revert leaves main),
questions parse/answer/all-answered-one-say, S sections, news kinds and the digest at its hour. B: browser tests at
desktop size and 390 × 844 with the stub (merged group, Looked, Revert confirm, chips answer, More sections, the silence
line), both looks; screenshots to `docs/design/img/board-29c/`. Both: the critical tests and `tests/test_gui_wording.py`.
