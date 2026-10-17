# Spec 29a — the board in focus: ideas from the phone to `main`, today (17 October, the owner)

The owner tests decisions §43 today: Orkline runs on the owner's computer **on Orkline's own repository**, the owner
drops ideas from the phone all day, and watches them become specs, plans and commits on `main`. Everything is on
Claude (the `claude` harness). The Agent pool is not used: each task is its own Claude session.

Four builders work at once (one branch each), so **this file is the contract**: names, data and files below are
fixed; anything not written here is the builder's own choice inside their files. Read decisions §43 and
`docs/specs/29-tracks-and-ideas.md` first (this spec takes 29's pages as they are and adds the rest of §43 that today's
test needs). Wording: CLAUDE.md (ork, orkestration; the interface in English, today's words).

| part | branch | builds | files (only these, plus their tests) |
|---|---|---|---|
| **A. Pages and keeper** | `spec/29a-keeper` | 29 §1–2; the keeper (batch, talk, plan); host commands; the phone's allowlist and snapshot | `realm/lexicon.py`, `realm/ideas.py`, `realm/wiki.py` (the `owner: board` skip), `core/idea_keeper.py`, `gui/ideas.py`, `gui/host.py` (wiring only), `gui/mobile.py`, `settings.py` (the keys below) |
| **B. Runner** | `spec/29a-runner` | a passed plan's tasks, each a Claude session in a worktree, tested, merged into `main`, pushed | `core/idea_runner.py`, `realm/idea_git.py` |
| **C. Desktop** | `spec/29a-desktop` | in focus, the window is the board only | `gui/static/js/board/*`, the focus switch in the page's entry (`gui/static/js/app.js` or wherever the town is mounted), its CSS |
| **D. Phone** | `spec/29a-phone` | in focus, the PWA is the board only | `gui/static/pwa/board.js` (+ css in `app.css`), the switch in `pwa/app.js`, `pwa/sw.js` (cache list) |

C and D work against the commands below; until A is merged they test with a stub host that answers them (fixtures
from the shapes here).

## 1. Focus
`MachineSettings.focus: str`, default **`"board"`** (alpha; `""` gives the full town back). In focus:
- the desktop window shows only the board (C): no camp, no map, no other building, no Mission. What stays from the
  rest: **Stop all** and today's **spend** in a thin top bar (money and safety stay visible).
- the phone shows only the board (D), with Stop all.
- the snapshot carries `focus` (full and the phone's compact one).

## 2. Where things live
- **Pages** (29 §2): the Wiki joined to the board, else `llm-wiki/general/`: `pages/tracks/<slug>.md`,
  `pages/ideas/<slug>.md`, front matter `owner: board`. Sections of an idea, in order:
  `Gist, Why, In, Out, Risks, Open questions, Estimate, Stages, Decisions`. Track `general` ("General") made on demand.
- **Idea state** beside, never in the page: `<state_dir>/ideas/<slug>/` (`state_dir` = the town's `.orkcraft/`):
  - `state.json` `{"state", "session", "session_at", "context", "batch_at", "error"}`
  - `talk.jsonl` — every turn `{"who": "you"|"keeper", "text", "section", "at"}` (the archive; never read back into a
    model, only shown)
  - `plan.json` — below; written by A, then owned by B (A never writes it after `passed_at`).
- **States** of an idea: `raw → reading → asks → ready → planning → plan → working → done`, and `failed`
  (Needs you). `reading`/`planning` mean a model runs now: the card says *The keeper is reading*.

## 3. `plan.json`
```json
{"idea": "slug", "made_at": "iso", "passed_at": null,
 "estimate": {"tasks": 3, "usd_low": 0.6, "usd_high": 1.8},
 "todos": [{"id": "t1", "title": "…", "kind": "secret|choice|confirm|instructions", "why": "…",
            "choices": [], "steps": [], "for": ["k2"], "done": false, "value": null}],
 "tasks": [{"id": "k1", "title": "…", "brief": "…", "tier": "elder|warrior|laborer", "after": [],
            "state": "waiting", "branch": "", "commit": "", "session": "", "cost": null, "tokens": null,
            "started": "", "finished": "", "error": "", "note": ""}]}
```
Task states: `waiting` (its `after` or `for`-todos not done) · `ready` · `running` · `testing` · `merged` · `failed`
· `held` (the tool's window is spent; `note` says until when). A `secret` todo's `value` is never written here:
A stores it with the machine's secrets (`realm/secrets` if there is one, else the OS keychain through `keyring` if
importable, else `<state_dir>/secrets.json` mode 600, git-ignored) and writes `"value": "stored"`; B passes it to the
task's session as an environment variable named in the todo's title (`API_KEY` …), never in a prompt or a file.

## 4. The keeper (A: `core/idea_keeper.py`)
- **Batch** every `ideas.batch_minutes` (default 30): each `raw` idea, one call on the **laborer** tier, read-only in
  the repository, given the Wiki's `index.md` and the tracks: it fills Gist (rewritten clearly), Why, size `S|M|L`,
  proposes a track (only if `general` is the idea's track) and writes 1–3 questions into *Open questions*. Then
  `asks` (questions) or `ready`.
- **Talk** (`ideas.say`): the **elder** tier, one Claude session per idea (`--resume` its `session`). It answers the
  person and edits only the sections the turn is about; it appends a line to *Decisions* for each decision. It returns
  JSON `{"reply", "sections": {name: text}, "decisions": [..], "questions": [..]}` (its answer is untrusted: only
  known section names are written). **Compaction:** a new session when `session_at` is older than
  `ideas.idle_hours` (default 24) or `context` > 60 % of the tool's window; the new one starts from the page (with
  Decisions and Open questions) only.
- **Plan** (`ideas.plan`): the **elder** tier, once: the page → `plan.json` (tasks ≤ 8, each a brief another session
  can do alone; `after` only where needed; the tier each task needs; todos only those a task cannot start without).
  The estimate from `realm/plans.py` `DEFAULT_COST` per tier, ±50 %. State `plan` (Needs you: *Plan ready*).
- Every model call: `realm/jobs.py` (`run_read` for batch/talk/plan), `harnesses.get("claude")`, `h.pick(tier)`.
  Spend is counted as the town counts it (`sources/telemetry`). The demo runs no model (say so on the card).
- Every change publishes on the bus `ideas.changed` (`slug`), and bumps `ideas_rev` in the snapshot.

## 5. The runner (B: `core/idea_runner.py`)
`IdeaRunner(repo_root, state_dir, settings, bus)`: `start(slug)` (called by A's `ideas.start` after it sets
`passed_at`), `stop(slug)`, `tick()` (the host calls it every few seconds; it never blocks), `stop_all()` (wired to the
town's Stop all / `realm/halt`).
- Runs `ready` tasks in order, at most `ideas.max_parallel` at once (default 1).
- **Each task:** a worktree off the local `ideas.merge_into` branch (default **`main`**; `realm/worktrees.py` /
  `jobs.add_worktree`), branch `idea/<slug>/<task id>`; one Claude session, **work** mode (`jobs.run_work`), model
  `h.pick(task.tier)`; the prompt: the idea page, the task's brief, the briefs of the tasks before it and what they
  merged (their commit subjects), and CLAUDE.md's rules; it must commit its work.
- **Gate:** run `python -m pytest -q tests/test_architecture.py tests/test_cli.py tests/test_updates.py` plus the test
  files named after the modules the diff touches (CLAUDE.md "Alpha"). Red → the same session once more with the
  failure (`--resume`), then `failed`.
- **Merge:** rebase onto the current `merge_into`; a conflict → `failed`. Fast-forward `merge_into` (in the root
  checkout with `git merge --ff-only` when it is checked out there and the touched paths are clean, else update the
  ref only when it is a fast-forward); then `git push origin <merge_into>` when `ideas.push` (default true) and an
  `origin` exists. Record `commit`. All git through `realm/idea_git.py`, one lock for the whole repository (the keeper
  never commits; the pages stay uncommitted in the working tree and git-ignored paths are not needed).
- **Limits:** before a task starts, ask the quota as the pool does (`core/workers/barracks_limits.py` logic): window
  nearly spent → `held` with `note` "after HH:MM"; the tool saying its limit is hit → `held` the same way. No harness
  switch today.
- When every task is `merged`: the idea is `done`; any `failed`: the idea is `failed` (Needs you) with the reason.
- Publishes `ideas.changed` on every task state change.

## 6. Host commands (A: `gui/ideas.py`; the phone may call all of them: `gui/mobile.py` `COMMANDS`)
| command | args | returns |
|---|---|---|
| `ideas.board` | — | `{"tracks": [{"slug","title","about","criteria":[],"deadline","order","count"}], "ideas": [{"slug","title","track","order","state","size","thesis","asks","progress":{"done","total"},"updated"}], "today": {"todos": [{"idea","id","title","kind","why","choices","steps","done"}], "needs_you": [{"idea","kind":"asks|plan|failed|held","title","text"}]}, "batch_next": "iso", "rev": int}` |
| `ideas.page` | `{"slug"}` | `{"slug","title","track","state","size","sections":[{"name","thesis","text"}],"talk":[last 30 turns],"plan": plan.json or null,"busy": bool}` |
| `ideas.add` | `{"text", "track"?}` | `{"slug"}` (state `raw`, no model) |
| `ideas.say` | `{"slug","text","section"?}` | `{"ok": true}`; the keeper answers in the background |
| `ideas.plan` | `{"slug"}` | `{"ok": true}` (background) |
| `ideas.start` | `{"slug"}` | `{"ok": true}` (passes the plan; the runner starts) |
| `ideas.move` | `{"slug","track"?,"before"?}` | `{"ok": true}` |
| `ideas.edit` | `{"slug","section","text"}` | `{"ok": true}` (by hand, no model) |
| `ideas.track_add` | `{"title"}` | `{"slug"}` |
| `ideas.track_set` | `{"slug","about"?,"criteria"?,"deadline"?}` | `{"ok": true}` |
| `ideas.todo` | `{"idea","id","done","value"?}` | `{"ok": true}` |
| `ideas.drop` | `{"slug"}` | `{"ok": true}` (the page and its state go; git keeps what was committed) |
| `ideas.stop` | `{"slug"}` | `{"ok": true}` (the runner stops the idea's tasks) |
Errors: `{"error": "plain words"}`. Thesis = the first line of a section without Markdown.
The phone's compact snapshot gains `focus`, `ideas_rev` and `needs_you` (count); `mobile.news` says
`{"kind": "idea", "slug", "title", "state"}` when an idea enters `asks`, `plan`, `failed` or `done` (a push).

## 7. The board's screens (C desktop, D phone) — the phone first (§43.10)
- **Today** (top on the desktop, the first tab on the phone): Needs you (each opens its idea), then today's to-dos
  from plans (tick; a `secret` asks for its value in a password field; `choice` offers its choices; `instructions` shows
  its steps).
- **Ideas:** tracks (desktop: a column on the left; phone: a switch on top), the ideas in order (drag on the desktop;
  long-press drag or ↑ ↓ on the phone). A card: thesis of Gist, size, state in words (*new · the keeper is reading ·
  asks you · ready · plan ready · working 2/5 · done · needs you*).
- **An idea:** sections as blocks, each its own colour role and icon (design-system roles, never raw colours), the
  thesis bold, the text folded; a question box at the bottom (*Ask or answer the keeper…*; on a section: *About Risks…*);
  the talk below, short. Actions by state: `ready`/`asks` → **Take it to work** (= `ideas.plan`); `plan` → the plan
  (tasks with tier and *after*, to-dos, the estimate) and **Start · N tasks · ~$x–y** (= `ideas.start`); `working` →
  each task's state, commit link, **Stop**; `failed` → the reason, **Start again** (= `ideas.start`).
- **+** (phone tab; desktop button): one field, **Drop it** (`ideas.add`, the chosen track).
- Refresh: on `ideas_rev` change in the snapshot (and every 10 s while an idea is `reading`/`planning`/`working`).
- Browser tests at **390 × 844** (D) and desktop size (C), with the stub host.

## Tests
Each part: its own unit tests and the critical tests. The PM session merges A and B first, then C and D, and runs the
whole loop once with a stubbed `claude` (a script on PATH that answers the JSON) before the owner's test.
