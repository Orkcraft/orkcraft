# Spec 33 — v1: three windows, Board · Agents · Review (17 October, the owner)

Design: decisions §45 (read it first), §42, §43, spec 29a (this spec builds on its board, keeper and runner as they
are on `main`). Sketch: [docs/design/img/v1/phone-sketch.jpg](../design/img/v1/phone-sketch.jpg). **Builds:**
Claude · **Review:** full · P0 · built Wed 21 – Thu 22 October, before the testers' go / no-go on Fri 23.

v1 is the core drawn plainly: **an idea on the Board → its spec → its plan, passed on the Board → the Grunts' work in
Agents → each result judged at Review before it is merged.** No camp, no map, no road graph, no animation, no Mission
1. External listeners and the Wiki are not shown (idea pages still live in the Wiki, §43.4). Spec 32 (the words
*goal* and *target*) is folded in: part A does `TERMS`, parts B and C write *goal* in their screens.

Three builders work at once, one branch each, so **this file is the contract**: names, data and files below are
fixed; anything not written here is the builder's own choice inside their files. Wording: CLAUDE.md (ork, orkestration,
orks by their orkish names, today's words; tests check the same words).

| part | branch | builds | files (only these, plus their tests) |
|---|---|---|---|
| **A. Review in the runner** | `spec/33-runner` | §2–§5: the `review` state, merge / send back / drop at the person's press, the testers' defaults, the diff, the task log, the commands, the snapshot's limits and counts, spec 32's `TERMS` | `core/idea_runner.py`, `realm/idea_git.py`, `gui/ideas.py`, `gui/mobile.py` (allowlist, compact snapshot), `gui/state.py` (snapshot keys only), `gui/host.py` (wiring only), `settings.py` (the keys below), `realm/lexicon.py`, `realm/event_log.py`, `realm/analytics.py` (§9) |
| **B. Desktop** | `spec/33-desktop` | §6–§7: the IDE-like window | `gui/static/js/board/*` (moved or reused freely), new `gui/static/js/shell/*`, the focus switch in `gui/static/app.js`, their CSS |
| **C. Phone** | `spec/33-phone` | §6, §8: three tabs, the preview on its own screen | `gui/static/pwa/board.js`, new `gui/static/pwa/shell/*` or files beside it, the switch in `pwa/app.js`, `pwa/sw.js` (cache list), `app.css` |

B and C work against the commands of §5; until A is merged they test with a stub host that answers them (fixtures
from the shapes here), as 29a did.

## 1. In focus
`MachineSettings.focus = "board"` (the alpha default, 29a §1) now opens **the v1 shell** instead of the board alone;
`""` still gives the whole town (the owner's own, §45.10). In focus:
- the window is always drawn in **Office's calm look** (`data-look="office"`, the design system's office theme), whatever
  the person's `look` setting, which is left as it is and comes back with the town;
- **the first start:** the onboarding shows only its first screen (trust said plainly, the AI tools found) and the
  repository pick, then opens the shell. The class fork and Mission 1 are not offered (their code stays). If the
  onboarding cannot be cut so in `gui/static/js/onboarding.js` without touching other files, B says so in its report
  and the PM adds the file to B.

## 2. The task's new state: `review`
Today a task goes `running → testing → merged` by itself (29a §5). From now on the person merges:
- **tests green** → `review` (no merge yet);
- **tests red** after the one automatic retry → `review` too, with the failure (not `failed`): the person decides;
- a task in `review` holds its worktree and branch; its `after` dependants keep waiting until it is `merged`.
- `plan.json` task fields gain: `"tests": {"passed": int, "failed": int, "failing": [names, ≤ 20], "tail": "last 40
  lines"}`, `"diff": {"files": int, "added": int, "removed": int}`, `"round": int` (1, then +1 each send back),
  `"conflict": ""`, `"why": ""` (the last send-back's line). Counts are parsed from pytest's summary line; a gate
  without pytest says `{"passed": 0, "failed": 0, "failing": [], "tail": …}` and the card says *no tests ran*.
- `ideas.review` setting, default **true**; `false` is today's behaviour (merge by itself), kept for the owner only.

## 3. The person's three answers at Review
- **Merge into `<branch>`** (`ideas.merge`): only when the tests are green and there is no conflict. `idea_git.land`
  into `ideas.merge_into`, pushing only when `ideas.push`. A conflict at that moment → the task stays in `review` with
  `conflict` set (*conflicts with dev in a.py, b.py*), never merged. Then `merged` as today, and the idea goes on.
- **Send back** (`ideas.back`, with one line *why*, required): the same Claude session is resumed (`--resume`) with the
  line (and, when red, the failing tests' tail; when in conflict, *rebase onto `<branch>` and resolve*), `round` + 1,
  `running → testing → review` again. On red tests or a conflict the button reads **Fix** and the line is prefilled.
- **Drop** (`ideas.drop_task`): the task `failed` with *dropped by you*, its worktree removed, its branch kept; the idea
  goes to Needs you as any failure does. A secondary action (a menu or a quiet button), never next to Merge.

## 4. The testers' defaults (§45.7)
- `ideas.merge_into` default **`dev`** (was `main`); the branch is created from the repository's current default
  branch's head when missing. `ideas.push` default **false** (was true). A machine with these keys already written
  keeps them: the owner sets `main` / `true` for himself.
- **Merge into ▾** at the top of Review shows the branch and changes it there (the local branches, and *New branch…*);
  it writes `ideas.merge_into`. Push is a switch in the shell's settings (the gear), off by default, said plainly:
  *Push after merging (sends your code to origin)*.

## 5. Host commands (A: `gui/ideas.py`; the phone may call all: `gui/mobile.py` `COMMANDS`)
| command | args | returns |
|---|---|---|
| `ideas.review_list` | — | `{"into": "dev", "push": false, "results": [{"idea", "idea_title", "task", "title", "round", "tests": {…}, "diff": {…}, "cost", "conflict", "finished"}]}`, oldest first |
| `ideas.diff` | `{"slug","task"}` | `{"base", "branch", "commits": [{"sha","subject"}], "files": [{"path","added","removed","patch"}], "truncated": bool}`; the patch per file ≤ 60 KB and ≤ 300 KB in all, the rest `"patch": null` (*too large to show*) |
| `ideas.merge` | `{"slug","task"}` | `{"ok": true, "commit"}` or `{"error"}` (red, conflict, plain words) |
| `ideas.back` | `{"slug","task","why"}` | `{"ok": true}` |
| `ideas.drop_task` | `{"slug","task"}` | `{"ok": true}` |
| `ideas.stop_task` | `{"slug","task"}` | `{"ok": true}` (a running task stops, goes back to `ready`, *stopped by you*; the idea's other tasks go on) |
| `ideas.agents` | — | `{"roles": [{"role": "taskmaster", "name": "Taskmaster", "state": "waiting\|reading\|talking\|planning", "waits_on": {"idea","text"} or null, "chips": [{"idea","title","state"}]}, {"role": "grunt", "name": "Grunts", "chips": [{"idea","idea_title","task","title","state","tier","note"}]}], "done_today": [{"idea","task","title"}]}` |
| `ideas.task` | `{"slug","task"}` | the task's fields from `plan.json`, its idea's title, and `"log": "last 200 lines"` |
| `ideas.into` | `{"branch"}` | `{"ok": true}` (sets `ideas.merge_into`; creates the branch when missing) |
| `ideas.log` | `{"event": "opened", "what", "ref", "device"}` | `{"ok": true}` (§9; any other event is refused) |

- **The log:** the runner keeps each task's session output in `<state_dir>/ideas/<slug>/<task>.log` (append, cut to the
  last 2 000 lines), shown, never fed back to a model. A secret never appears in it (the env var's value is masked).
- **The snapshot** (full and the phone's compact) gains `limits: [{"provider": "claude", "name": "Claude", "left":
  0.62, "rows": [{"window": "5h", "left": 0.62, "reset": "iso"}, {"window": "week", …}]}]` — **`left` is the smallest
  `remaining` of the provider's rows** (§45.3), from `sources/limits.fetch_limits`, read in a thread every 5 minutes
  (reuse what the host already reads for the HUD's quota if it has it); only providers that are installed. It also
  gains `review_count` (results waiting) and `needs_you` (already there for the phone) for the tab counts.
- Every change publishes `ideas.changed` and bumps `ideas_rev`, as in 29a.
- `realm/lexicon.py`: spec 32 §1–2 (the `track` entry shows *goal / goals*, `was` "track"; the setting Goal shows
  *Target*, `was` "Goal"); `orc.fields` stays **Taskmaster**.

## 6. What every screen shows
**The top bar** (all tabs, all panes): *Orkline* · for each installed AI tool its mark and what is left, the smaller of
the window and the week (*✱ 62 %*), warning colour at ≤ 20 %, danger at ≤ 5 %; a hover (desktop) or tap (phone)
shows each window with *resets at 18:00* · today's **Spend** · **Stop all** · the gear (Push after merging; the
theme follows the system). Design-system roles only, never raw colours (docs/design-system.md).

**Board** (today's 29a board, kept): the goal at the top (a switch when there are several), **New idea**, Today
(Needs you, then to-dos), the ideas in order with their state in words (*new · the keeper is reading · asks you ·
ready · plan ready · working 2/5 · needs you · done*), no badge. **A click on an idea opens its spec in the preview; a
click on a to-do opens the idea's plan in the preview, scrolled to that to-do, highlighted, with one line on what it
unblocks** (*tasks k2 and k3 wait for it*). Take it to work and Start (the plan passed) stay in the idea's preview.

**Agents:** a block per role, its name and state: **Taskmaster** (*waiting for your answers on "<idea>"* → opens that
idea; *reading "<idea>"*; *planning "<idea>"*; *nothing to do*) and **Grunts**: one chip per live task — *working* ↻,
*testing*, *at Review*, *queued*, *after 18:00* (held), *needs you* ⚠ — each with its idea's title small. *Done today
(n)* folded below. A chip opens the task in the preview: its brief, idea, state, tier, branch, round, spend, the log's
tail (refreshed every 5 s while it runs) and **Stop**. No *Add agent* and no *Edit* in v1 (§45.8: next, after the
owner's test).

**Review:** **Merge into `dev` ▾** at the top, then the results, oldest first, one card each: the task's title and its
idea, *round 2* when sent back before, **tests** (*20 / 20 passed* ✓ or *10 / 20 failed* ✗ with the first failing
names), **changes** (*14 files, +320 −41*), **cost**, a conflict in plain words if any. Actions on the card and in its
preview: **Merge into dev** (disabled with the reason when red or in conflict), **Send back** / **Fix** (one line,
required), **Drop** (secondary). A click on the card opens its code in the preview.

**The preview** shows one thing at a time: an idea's spec (29a's sections view, unchanged), an idea's plan, a task, or
a result's code: commits, then the files changed (path, +/−), each file's patch folded, monospace, added and removed
lines in the design system's success and danger roles; *too large to show* where the patch is `null`; the result's
actions stay pinned at its foot.

## 7. The desktop: one screen, as an IDE (B)
```
┌──────────────────────────── top bar: Orkline · ✱ 62 % · ∩ 40 % · Spend $1.20 · Stop all · ⚙ ────────────────────┐
│ Board        │ the preview (an idea's spec · a plan · a task · a result's code)              │ Review           │
│ goal ▾       │                                                                               │ Merge into dev ▾ │
│ New idea     │                                                                               │ ┌──────────────┐ │
│ Today        │                                                                               │ │ result card  │ │
│ Ideas        │                                                                               │ └──────────────┘ │
│ To-dos       ├───────────────────────────────── drag ────────────────────────────────────────┤ ┌──────────────┐ │
│              │ Agents  (Taskmaster · Grunts: chips)                         ▾ hide            │ │ result card  │ │
└──────────────┴───────────────────────────────────────────────────────────────────────────────┴──────────────────┘
```
- **Board** on the left (≈ 300 px), **Review** on the right (≈ 340 px), both full height; **the preview** in the
  centre; **Agents in the lower part of the centre, as VS Code's terminal**: about a third of the height by default,
  its top edge dragged to resize, a button (and `Ctrl+J`) to hide and show it; the height and hidden state are kept in
  `localStorage` (read and written in try/catch; the layout works without it).
- Nothing opened: the preview says *Open an idea, a task or a result* and lists the first Needs you item, if any.
- Down to 1 024 px wide the side columns narrow; below that the desktop shows the phone's layout (§8).
- Keyboard: `Esc` closes the preview; `↑ ↓` move through the Review cards; no shortcut merges.

## 8. The phone: three tabs, the preview on its own screen (C)
- Bottom tabs **Board · Agents · Review**, each with its count when it is not zero (Board: Needs you + to-dos that block
  something; Review: `review_count`). The top bar as in §6, the limits as one chip (the smallest of all tools) that
  opens the rest.
- **The preview opens on its own full screen** over the tab (an idea's spec, a plan, a task, a result's code), with
  **Back** (and the system back gesture) to the tab it came from; its actions sit in a bar pinned at the bottom
  (Take it to work / Start; Stop; Merge / Send back / Drop). A file's patch scrolls sideways inside its own box, the page
  never does.
- Designed at 390 × 844 first (§43.10); the paired-link rule for secret to-dos stays (29a).
- A push when a result reaches Review (`mobile.news` `{"kind": "result", "slug", "task", "title"}`), as for ideas.

## 9. Every action logged, for the day's analysis (the owner, same day; part A, with B and C sending their events)
The owner downloads the day's logs at the end of the working day and analyses them. Reuse what exists, add no new log:
- **Events** go to the local event log (`realm/event_log.py`, `.orkcraft/usage/events.jsonl`, never leaves the
  machine). Part A adds to its closed list `EVENTS` (and may edit that file):
  | event | fields |
  |---|---|
  | `idea_added` | idea, track, chars, device |
  | `idea_said` | idea, section, chars, device (the person's turn to the keeper) |
  | `keeper_state` | idea, state (`reading` · `asks` · `ready` · `planning` · `plan` …), seconds in the previous state |
  | `plan_made` | idea, tasks, todos, usd_low, usd_high |
  | `plan_passed` | idea, tasks, device, seconds from `plan_made` |
  | `todo_done` | idea, todo, kind, device, seconds since the plan |
  | `task_state` | idea, task, state, round, tier, seconds in the previous state, tokens, cost |
  | `result_ready` | idea, task, round, passed, failed, files, added, removed, cost |
  | `result_decided` | idea, task, round, decision (`merge` · `back` · `fix` · `drop`), why (the line), into, pushed, conflict, device, **seconds from `result_ready`** (§37.3: how long a decision took) |
  | `task_stopped` / `stop_all` | idea, task (or how many), device |
  | `into_changed` | branch, device |
  | `opened` | what (`idea` · `plan` · `todo` · `task` · `result` · `tab`), ref, device — every preview and tab the person opens (B and C send it through one command, `ideas.log {"event": "opened", …}`, which accepts only this event) |
  | `limits_read` | provider, left, window (once an hour at most, and whenever a task is held) |
  `device` is `desktop` or `phone`. The texts the person wrote are kept (cut at `TEXT_MAX`); **a secret's value never**.
- **Model calls** are already kept by `realm/call_log.py` (every keeper and Grunt call, through `realm/jobs.py`): check
  that the keeper's and the runner's calls carry the idea and the task in their record so the two logs join; add them if not.
- **The download:** the gear gets **Download today's logs** (and *the last 7 days*): the existing analytics zip
  (`/api/analytics?days=`, `realm/analytics.py`) with the event log's lines of those days added as `events.jsonl`,
  and each idea's `state.json`, `plan.json` and task logs (`<task>.log`, secrets masked). On the phone the same item
  in its menu (the file is downloaded on the phone).
- Tests: each action writes its event with its fields; an unknown event through `ideas.log` is refused; the zip holds
  `events.jsonl` for the days asked and no secret value.

## Not in this spec
Roles, models and limits editable (§45.8, next); the Alchemist; the daily batch at Review (§39); External listeners and
the Wiki as windows; the camp. Nothing in `orkcraft/realm/` or `orkcraft/core/` other than the files of part A.

## Tests
- **A:** the runner with a stubbed session and gate: green → `review`, not merged; red after the retry → `review` with
  counts; Merge lands into `dev` (created when missing) and does not push by default; Merge refused when red or in
  conflict; Send back resumes with the line and bumps `round`; Drop fails the task and keeps its branch; Stop on one task
  leaves the others; `ideas.review = false` merges by itself as before; the log is cut and masks a secret; the
  snapshot's `limits.left` is the smallest row; the commands' shapes.
- **B:** browser tests at 1 440 × 900 with the stub host: the three columns and Agents under the preview; dragging and
  hiding Agents; a click on an idea, a to-do (scrolled to it), a chip and a result opens the right preview; Merge
  disabled on red with its reason; Send back needs its line; no camp element in the page.
- **C:** browser tests at 390 × 844: the tabs and their counts; each preview on its own screen with Back; the pinned
  actions; no horizontal scroll of the page.
- Each part: the critical tests (CLAUDE.md "Alpha") and the test files of what it touches; `tests/test_gui_wording.py`.
  The PM merges A first, then B and C, and runs the whole loop once with a stubbed `claude` before the owner's test.
