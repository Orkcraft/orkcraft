# Spec 34 — v1, round 2: goals and ideas by dialog, straight to the keeper; agents by task type; modals; the phone

The owner tested spec 33 (17 October) and found: no dialogs to create a goal or an idea; an idea never reaches the
model (the keeper reads new ideas only in a batch every 30 minutes); no way to create an agent; the settings menu
opens on a transparent background. This round fixes the mechanics. Design: decisions §43, §45 (§45.8's roles come in
now, by the owner), spec 33 (build on it as it is on `main`). **Builds:** Claude · **Review:** full · P0.

Three parts, one branch each, built in this order by one session; **this file is the contract** (names, data,
commands); the rest is the builder's choice inside its files. Wording: CLAUDE.md (orks by orkish names, today's
words: *goal*, *idea*, *agent*, *task type*).

| part | branch | builds | files (and their tests) |
|---|---|---|---|
| **A. Backend** | `spec/34-backend` | §1–§4 data, the keeper's goal reading, ideas now/later, roles and task types, the runner picking a role, events | `realm/ideas.py`, `core/idea_keeper.py`, `core/idea_runner.py`, `core/idea_review.py`, new `realm/roles.py`, `gui/ideas.py` (+ a new `gui/ideas_*.py` if it grows past ~600 lines), `gui/mobile.py` (allowlist), `realm/event_log.py`, `realm/lexicon.py`, `settings.py` |
| **B. Desktop** | `spec/34-desktop` | §5–§7 on the desktop | `gui/static/js/shell/*`, `gui/static/js/board/*`, reuse of `gui/static/js/phones.js` `PairQr` (import, don't fork) |
| **C. Phone** | `spec/34-phone` | §5–§7 on the phone | `gui/static/pwa/*` (the shell's files), `pwa/sw.js` (cache version), `app.css` |

B and C branch from A once A is pushed (as in 33).

## 1. A goal: a dialog, then straight to the keeper
**New goal** (and **Edit** on a goal) opens a dialog (§5) with:
- **Title** (required) · **Description** (a few lines)
- **Metrics:** a list, each *what is measured* and *the target* (e.g. *weekly installs · 50*), add / remove rows
- **Priority:** *High · Normal · Low* (goals are listed by priority, then by the person's drag order inside a priority)
- **Links:** a list of documents: a path in the repository, a Wiki page, or a URL
- **Deadline** (optional)

Kept in the goal's page (`pages/tracks/<slug>.md`, front matter `title, priority, deadline, metrics: [{name, target}],
links: [..]`, sections *Description, Summary, Metrics, Open questions*), as 29 keeps tracks.
**Saving sends the goal to the keeper at once** (no button, no batch): one call on the **warrior** tier, read-only:
the goal, the files and Wiki pages it links (URLs are kept as links, never fetched), the Wiki's `index.md`. It
writes *Summary* (what the goal means for this repository, 3–5 lines), makes each metric measurable (how it is
counted, where), and puts 0–3 questions in *Open questions*. Goal states: `reading` → `asks` | `ready` (shown in
words on the goal, like an idea's). Editing a goal sends it again. A goal that `asks` shows in Needs you.

## 2. An idea: a short text, Process now or later
**New idea** opens a dialog: one **text** field (short; the phone's keyboard dictation is the voice) and the **goal**
(the goal open on the board, or *General*). Two buttons:
- **Process now** → saved and the keeper reads it at once (29a's batch call for this one idea, now, not in the batch);
- **Later** → saved `raw`; the batch reads it.
**Closing the dialog with text in it saves it as Later** (never lost); closing it empty saves nothing.
When the keeper reads an idea it now also fills, from its goal: **its priority** (*High · Normal · Low*, from the
goal's priority and how much the idea moves the goal's metrics, with one line why, in *Why*) and **its place** among
the goal's ideas (the keeper proposes; the person's drag wins and is never undone by it). The rest as 29a (Gist, Why,
size, sections, questions).

## 3. Agents: roles, and a role for each task type
- **A role** = a name, a **model** (the Claude harness's models and tiers, as `harnesses.get("claude")` offers them),
  an **instruction** (free text, added to every task prompt of that role), and **at most N at once** (1–8). Kept as
  one small file per role, `<state_dir>/roles/<slug>.md` (front matter `name, model, max_parallel`; the body is the
  instruction), so it is seen and undone by hand. Two exist by themselves and can be edited, not deleted:
  **Taskmaster** (the keeper: its model is the one the keeper uses for talk and plans) and **Grunt** (the default
  worker). A role the person makes keeps the name they give it.
- **Task types**, a fixed list `TASK_KINDS` in `realm/roles.py`: **code · tests · docs · text for people · research**.
  Each type is assigned one role (default: Grunt). The keeper's plan marks each task with its type (`kind`); a task
  without one is `code`.
- **The runner** runs a task as its type's role: that role's model (instead of the tier's) and its instruction ahead
  of the task prompt; each role's `max_parallel` is held besides `ideas.max_parallel`. The task records `role`; the
  result card and the task show it; spend is summed by role in `ideas.agents`.
- **Agents (window):** the roles as blocks (as in 33, a block per role, its chips), each with **Edit**; **+ Add agent**
  at the top; under them **Task types**: each type with a select of the roles and *New agent…* (which opens Add agent
  and assigns it). Deleting a role moves its types back to Grunt (said in the confirm).

## 4. Commands and events (A)
| command | args | returns |
|---|---|---|
| `ideas.goal_save` | `{"slug"?, "title", "about", "metrics": [{"name","target"}], "priority", "links": [], "deadline"?}` | `{"slug"}` (new or edited; the keeper reads it at once, in the background) |
| `ideas.goal` | `{"slug"}` | the goal's fields, sections, state |
| `ideas.add` | `{"text", "track"?, "now": bool}` | `{"slug"}` (`now`: the keeper reads it at once) |
| `ideas.read_now` | `{"slug"}` | `{"ok": true}` (a `raw` idea read at once: the card's *Process now*) |
| `ideas.roles` | — | `{"roles": [{"slug","name","model","max_parallel","instruction","builtin","spend_today"}], "kinds": [{"kind","label","role"}], "models": [..]}` |
| `ideas.role_save` | `{"slug"?, "name", "model", "max_parallel", "instruction"}` | `{"slug"}` |
| `ideas.role_drop` | `{"slug"}` | `{"ok": true}` (not for the two built in) |
| `ideas.kind_set` | `{"kind", "role"}` | `{"ok": true}` |
`ideas.board`'s goals gain `priority, state, metrics, links`; ideas gain `priority`. All callable from the phone
(`gui/mobile.py`). Events (spec 33 §9, same log): `goal_saved` (goal, new, metrics, links, priority, device),
`goal_read` (goal, state, seconds), `idea_added` gains `now`, `role_saved` / `role_dropped` (role, model,
max_parallel), `kind_set` (kind, role); `task_state` and `result_ready` gain `role`.

## 5. Dialogs and menus: always on a dimmed backdrop (B, C)
One modal for everything that opens over the shell (New goal, Edit goal, New idea, Add / Edit agent, the gear's
menu, Drop's confirm): a **dimmed backdrop**, an opaque panel (the design system's panel role), a title, **Close**
(×) and **Esc**, the focus kept inside while open, back on what opened it after. On the phone: a sheet from the
bottom, full width, its buttons pinned at its foot. Fixes the gear opening on a transparent background.

## 6. The phone, from the shell (B, C)
- The gear gets **Pair a phone**: the existing pairing (`phones.pair`, `phones.pair_stop`, `PairQr` in
  `js/phones.js`) inside the modal: the QR, the code's time left, and in plain words how the phone will reach the
  machine: *on this Wi-Fi* and, when Tailscale is found (`gui/tailnet.py`), *anywhere on your tailnet: <name>.ts.net*;
  without it, one line: *Away from home? Install Tailscale on this computer and the phone.* The paired phones listed
  with **Forget** (as Settings → Phones does in the town).
- Today a paired phone can only be paired from the full town's Settings; after this, from the shell.
- The phone's two nits from 33: the top bar's spend cut to *$— / $…* (show today's spend whole), and the empty grey
  band above the top bar.

## 7. Screens (B, C)
- **Board:** goals with their priority and state in words (*reading · asks you · ready*), **New goal**, a goal's
  **Edit**; the ideas with their priority (*High · Normal · Low*) and a **Process now** on a `raw` idea's card.
- A goal opens in the preview (desktop) or its own screen (phone): Description, Summary, Metrics (name, target, how it
  is counted), Links (a repository path or Wiki page opens in the preview; a URL opens in the browser), Open
  questions with a box to answer (the same talk as an idea's, `ideas.say` on the goal's slug).
- **Agents:** §3.

## Not in this spec
Image making (the Alchemist), other harnesses than Claude for roles, fetching URLs, a model choosing the order of
goals, External listeners and the Wiki as windows, the camp.

## Tests
- **A:** a goal saved is read at once (stubbed model) and its Summary and Metrics written; editing reads it again;
  `ideas.add` with `now` is read at once, without it waits for the batch; the keeper's priority and order (the
  person's drag wins); a role saved, edited, dropped (types back to Grunt), the built-ins refused; the runner runs a
  task with its type's role's model and instruction and holds the role's `max_parallel`; each event with its fields.
- **B:** browser tests at 1 440 × 900: New goal (metrics rows, links, priority) → the goal shows *reading* then its
  Summary; New idea → Process now / Later / closed with text → saved Later / closed empty → nothing; Add agent and a
  type assigned; every modal has a dimmed backdrop and closes on Esc; Pair a phone shows the QR.
- **C:** the same at 390 × 844 as sheets; the top bar's spend whole; no empty band; no horizontal scroll.
- Each part: the critical tests (CLAUDE.md "Alpha"), the touched modules' tests, `tests/test_gui_wording.py`,
  `tests/test_board_loop.py`. The PM merges A, then B and C.
