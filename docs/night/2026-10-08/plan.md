# Night audit 2026-10-08 — plan

Ordered by the owner: a deep night audit in three roles — the architect (tech debt), the PM (design
docs that are not built yet: build what is worth it) and the designer (assess and fix the GUI). One
session starts every 20 minutes so they do not get in each other's way; everything goes into `main`.

The orchestrating session (`orkcraft code`) starts each session from this file at its time.

## Queues

Each audit session writes its queue here; the sessions after it take items from it.

| file | written by | taken by |
|---|---|---|
| `tech-debt.md` | A1 | A2, A3 |
| `design-docs.md` | P1 | P2, P3, P4 |
| `ui.md` | D1 | D2, D3 |
| `report.md` | everyone (3–5 lines each) | F, then the owner in the morning |

An item is a checkbox line: `- [ ] <id> <what> — <files> — <size S/M/L> — <why>`. To take one, change
it to `- [~] <id> … — taken by <session title>` and push that to `main` at once; when it is merged,
`- [x] … — <commit or PR>`. An item that turned out wrong or too big: `- [-] … — <why>`.

## Schedule (UTC)

| # | at | session | role |
|---|---|---|---|
| A1 | 20:35 | Night A1: tech-debt audit + quick fixes | architect |
| P1 | 20:55 | Night P1: triage of unbuilt design docs | PM |
| D1 | 21:15 | Night D1: GUI audit + quick fixes | designer |
| A2 | 21:35 | Night A2: tech debt from the queue | architect |
| P2 | 21:55 | Night P2: build from the design-docs queue | PM + engineer |
| D2 | 22:15 | Night D2: GUI fixes from the queue | designer + engineer |
| P3 | 22:35 | Night P3: build from the design-docs queue | PM + engineer |
| A3 | 22:55 | Night A3: tech debt from the queue | architect |
| D3 | 23:15 | Night D3: GUI fixes from the queue | designer + engineer |
| P4 | 23:35 | Night P4: build from the design-docs queue | PM + engineer |
| F  | 00:15 | Night F: full suite, fix red, release, morning report | release |

## Common rules (every night session gets these)

1. The owner is asleep and has allowed merging into `main` for this night **without asking in the
   session**, by the alpha rule of `CLAUDE.md` (the critical tests and the tests of the touched
   modules). Do not wait for a human: when a call is disputed, take the conservative option, write it
   as a *question for the morning* in `report.md`, and go on.
2. The Camp look, the orks, the sprites and the gamification (growth, Renown, stages, classes,
   mascots, Fire on the roofs) **stay** — the owner's decision. Simplify around them, never remove them.
3. The TUI gets fixes only (`CLAUDE.md`). New work goes to the GUI.
4. Pull `main` before every merge: other night sessions merge too. Small commits, merge often.
5. Do not raise `__version__` or touch `updates.json`: F makes one release at the end.
6. Before you finish, add 3–5 lines to `report.md`: what you did (commits), what you left, what may
   be broken, questions for the morning.
7. Wording, the lexicon (`realm/lexicon.py` `TERMS`) and the architecture rules of `CLAUDE.md` hold.
8. Work for at most ~2 hours; stop at a merged, green-critical state.

## The sessions

### A1 — tech-debt audit + quick fixes (architect)
Audit the code as an architect: dead code and unused modules, duplicates, modules past ~600 lines,
`realm/` structure (118 flat modules), the many ways an agent is started (`harnesses` ask/read/work/
interactive, `feeds_agent`, `fastpath`, …) and whether one registry knows every running agent,
`realm/modes.py` (CLAUDE.md says there are no modes), the runtime wording layer (`was`, `say()`,
`tui/wording.py`), the cost of the deprecated TUI (~20k lines), test speed and flaky tests (the
`test_mine` flake under load). **Push a first `tech-debt.md` within 15 minutes**, then refine it:
each item with files, size and why, ordered by value/risk. Then fix the S-sized safe items yourself.
TUI removal is *not* tonight: put it in the list as a recommendation with a plan.

### P1 — triage of unbuilt design docs (PM)
Read every `docs/design/*.md` and its status line; list what is designed but not built (e.g.
`landscape.md`, `simplify.md`, `mine-next.md`, `watchtower-automation.md`, `mobile.md` beyond stage 0,
`barracks-flows.md` stage 4, `steward-at-work.md` §3, `phone-places.md` later stages, `road-sound.md`
§1/§3, `catapult-mcp.md` phase 4, `codex-limits.md`, `yards.md` — built on an unmerged branch).
Check what other sessions already did today (`git log`, the building-simplification PM session's
work on `landscape.md`). Decide as a PM what is worth building now and what not (say why).
**Push a first `design-docs.md` within 15 minutes**: build items cut into stages of S/M size, best
value first; *not now* items with the reason. Then build the top S item yourself.

### D1 — GUI audit + quick fixes (designer)
Be the product designer. Run the GUI (`orkcraft --demo` or the demo city; Playwright + Chromium are
installed), take screenshots of every building's window, Settings, the portrait menu, onboarding,
the phone width (<640 px), in both looks (Camp and Office). Judge consistency (`docs/design-system.md`,
`docs/design/gui-design-system.md`), hierarchy, empty states, errors, wording, tap targets,
overflow and scroll, dark/light. The owner's notes from today are being done by other sessions
(onboarding, windows and map, icons, Watchtower/Calendar): check `git log` and do not redo them.
**Push a first `ui.md` within 15 minutes**: each item with the screenshot path, where, size, why.
Save screenshots under `docs/night/2026-10-08/ui/`. Then fix the S items yourself.

### A2, A3 — tech debt from the queue (architect + engineer)
Take the 1–3 highest open items of `tech-debt.md` that fit your time, mark them taken, do them,
merge. Prefer items that remove code. Never two sessions on one item.

### P2, P3, P4 — build from the design-docs queue (PM + engineer)
Take the highest open build item of `design-docs.md`, mark it taken, build it to its design doc,
update the doc's status line and *As built*, merge. If time remains, take the next.

### D2, D3 — GUI fixes from the queue (designer + engineer)
Take the highest open items of `ui.md`, mark them taken, fix them, add a screenshot after under
`docs/night/2026-10-08/ui/`, merge.

### F — full suite, fix red, release, morning report (release)
Run the **full** test suite including the browser tests. Fix what is red (a failing test is never
skipped). Then one release by `CLAUDE.md` → Releases: raise `__version__`, add the entry at the top of
`updates.json` (`critical: false`, notes saying plainly what changed tonight). Write the top of
`report.md`: a morning summary for the owner in Russian, short (they read it on a phone): what was
done by area, what is left in each queue, what to check by hand, questions that need their decision.
