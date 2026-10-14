# Design — `orkcraft check`: the gate before people use it

Status: built 2026-10-11 (`realm/check.py`, `realm/check_pictures.py`, `check_cli.py`, `gui/idle_check.py`,
`gui/check_runs.py`; tests/test_check.py). Tried on Claude (the mail scenario, once a case): green, every call kept.

## 1. What it answers

Before the first people use Orkline: does it do its main jobs **well enough**, for **the cost it should**, and does a
town **stay quiet** when nothing comes in? The tests (tests/) prove the logic with every model faked; the check runs
the main jobs with real models — **on the cheap AI tool by default (agy, its lightest model; asked 2026-10-11)** — and
says **green** or **red** with the numbers. Its other job is **the logs**: one check leaves everything it saw in one
folder, for an agent (Claude Code, overnight) to read, find what to change, change it and check again (§5, §6).

    orkcraft check                          every scenario, then the quiet town
    orkcraft check --scenario mail          one scenario (more with more --scenario)
    orkcraft check --only idle              only the quiet town: free, no model is called
    orkcraft check --list                   what it would run, and the budget

The exit code is 0 when it is green, 1 when it is red. `--tool` and `--tier` run it on another AI tool.

## 2. The scenarios: the jobs people will be shown first

| Scenario | Building | Cases (Test bench) | What it checks |
|---|---|---|---|
| `mail` Mail sorted | External listeners | customer-orders, on-call, sales-leads | an inbox read: what to keep, how important, who answers |
| `todos` Tasks from mail | Task board | mail-to-todos, long-cards, boiler-with-contacts | to-dos named from letters, planned with the wiki |
| `board` Review board | Review board | planted-flaws, route-a-request | several orks debate a design; a letter sent down the right exit |
| `pictures` Pictures redrawn | UX bench (the Alchemist) | roof-red, ork-hat, icon-bolder | a sprite painted again from a person's words: a PNG of its size, not the same, judged ≥ 6/10 by the AI tool reading both |
| `looks` Windows look right | UX bench (the Alchemist) | every building's window | pictured and held against the last check; a changed one judged broken or not (§12) |
| `wiki` Wiki from mail | Wiki | — | **not checked yet**: the Wiki has no Test bench kit (§7) |

A task for Jira is checked as the Task board's draft of it: a check never writes to Jira, mail or any service.

## 3. The budget

Each case runs `repeat` times (3) in its building and in the bare AI tool on the same model (core/bench.py); the bare
tool's answers are kept and read back, so a second check pays only for the buildings. A case passes when:

- the building passed its check in at least `pass_share` (⅔) of its runs, and in no fewer than the bare tool;
- its median time is at most `time_over` (+50 %) over the bare tool's, and its spend at most `spend_over` (+30 %),
  in tokens when the tool says no price — every token counted, what was read from the tool's cache too, so a
  call on a warm cache weighs as one on a cold cache (agy names its cache apart; docs/nights/2026-10-11.md);
- no run was cut at its spend limit (`max_spend`, $2) or its time.

The quiet town: the dashboard demo built in a temporary folder, ticked a minute a tick for `idle_hours` (8) with every
model seam counted and nothing coming in; it may make `idle_calls` (0) calls. The retros keep their own schedules
(`tools/count_model_calls.py` makes them due every minute, to see what they cost).

A town sets its own budget in `.orkcraft/check/budgets.json` (any of the keys above).

## 4. What it does not tell

- How the person's own buildings are set up: the scenarios raise each building with the config of the person's
  building of that type when there is one, else the type's defaults.
- A fresh install (Homebrew, the first window, the onboarding): that is walked by hand, with a stopwatch.
- What a real inbox brings: the cases are written ones. A 👎 on real work is the better case; turning one into a Test
  bench case is next (docs/design/improve-buildings.md §11).

## 5. The folder, for an agent

`.orkcraft/check/<stamp>/` (`latest.txt` names the last):

- `README.md` — what is where and how to work through it: the ❌ lines first, then the costly ✅ ones; each run's
  analysis, then its calls, the building's against the bare tool's; the smallest change in the code; the tests of
  what changed; `orkcraft check --scenario <id> --repeat 3` again; what changed and what the numbers did.
- `report.md`, `results.json`, `idle.json`.
- `runs/<scenario>/<case>/run-<n>/`: `analysis.md`, `report.json`, `calls/` (each call in full: prompt, output,
  errors, the tool's trail), and for a picture `reference.png`, `out.png`, `judge.json`.
- `check.zip` — all of it.

Every seam that starts an AI tool writes there (realm/call_log.py): an ork's work and a reader (`jobs`), a road's
agent (`road_agents`), a one-off answer (`builders.ask`: stewards, retros, the Council) and a connector's look
(`feeds_agent`).

## 6. In the Test bench

The Test bench's window starts with **Check the main jobs** (gui/check_runs.py, js/buildings/lab.js `Check`): **Run
the check** starts `orkcraft check` in a process of its own, its lines come in as it goes, **Stop** ends it and the AI
tools it started; the last verdict (green or red, its table) stays under it, and **Download (.zip)** is the folder
(`GET /api/check/latest`). The aim (asked 2026-10-11): the whole loop — check, read the logs, change, check again —
in the Mechanic's building, without leaving the product. Today the reading and the changing are an agent's outside
it (Claude Code with the folder); next, the Mechanic does them itself on the night's budget
(docs/design/improve-buildings.md §11), proposing the change and checking it before it is kept.

## 8. Every night, and against the last time (built 2026-10-12)

**The night check** (gui/night_check.py, in gui/nightly.py's quiet hours): once a night (`check_history.night_key`: a
night is its evening's date), in a town that has a Test bench, while the Council's `check_nightly` is on (it is by
default; the Test bench's Check has the switch), `orkcraft check` runs the scenarios in turn — `check_per_night` (2) of
them a night, all of them on Saturday night — and the quiet town. The night's improvements (gui/improve_night.py)
wait while it runs: on one AI tool account two jobs slow each other, and the night of 2026-10-11 showed the numbers
move with it (docs/nights/2026-10-11.md). In the morning one line joins the Elders' toast: what it checked, green or
red, and what got worse (else better) than the last time.

**The history** (realm/check_history.py, `.orkcraft/check/history.jsonl`): each check's cases, a line. A case is
**worse** than its last check when it passed fewer of its runs or its building's median time or tokens grew by more
than a fifth; **better** the other way round; what moved less is the noise of a few runs and is not said. `report.md`
has **Since the last check**; the Test bench's Check lists it (▼ worse, ▲ better).

## 9. A 👎 is a case (built 2026-10-12)

Every cart that comes into a building is remembered, the last one (realm/regressions.py `record_input`, from
core/delivery.py). A 👎 for the building's own logic keeps that cart as a test case of the building
(`.orkcraft/feedback/cases/<building>.jsonl`): its input what came in, its `why` what the person said and what it made
then, its title `👎 <day>: <what they said>`. A 👎 for broken inputs makes none (that is the suppliers' fault), and
nothing does when nothing came in. A Test bench that tests the building takes it in among its own cases, once
(core/workers/lab.py `take_regressions`; its row says *from a 👎*), so Run all and the night run it against the AI
tool alone like any other. The input stays on this machine, as the feedback does.

## 10. The night works on what was found (built 2026-10-12)

The Mechanic's proposals (gui/lab_runs.py `propose`, by day and at night) start from what is wrong, in words
(gui/lab_export.py `findings`): its own runs' stories and changes (realm/explain.py, read from the model calls), the
last night check's on the same building types, and the person's 👎 cases with what they said; each proposal says which
it fixes. At night (gui/improve_night.py) the Test benches with the most wrong go first (`trouble`: cases not good,
and 👎 cases), and one with no goal written works to `lab_cases.DEFAULT_GOAL` — as well as the AI tool alone, for
less time and fewer tokens — instead of being skipped. What it tries is still measured on the virtual building and
kept only when better, by the town's autonomy (improve-buildings.md §8).

## 11. Recorded answers, played back (built 2026-10-12)

`orkcraft check --replay <stamp|latest>` runs each run of a check again with its building's model calls answered from
what that check recorded (realm/call_log.py `replaying` / `answer`): every seam that would start an AI tool — `jobs`,
`road_agents`, `builders.ask`, `feeds_agent` — takes the recorded call of the same kind (`mode`, then `purpose`) whose
prompt is the closest instead, so a date in a prompt or calls made at once in another order do not matter. Nothing is
called, nothing is paid. A run is **the same** when its building finishes, passes or fails its check as it did (the
same checks), and asks for no more and no less than it did; `Unrecorded` when it asks for something the recording has
no answer to. Exit 0 when every run is the same. The Test bench's Check has **Play it back (free)**.

On every commit: `tests/test_replay.py` plays back `tests/recordings/check-mail` — a real check of the mail scenario
on Claude (2026-10-11, its session ids and trails taken out) — and fails when External listeners would no longer sort
those letters as they did. A new recording is a check's `runs/<scenario>/` copied in the same way.

## 12. The windows' look (built 2026-10-12)

The `looks` scenario (gui/look_check.py): the dashboard demo opened in a headless Chromium, every building's window (its
Work) pictured with animations stopped, held against the last check that pictured them, pixel by pixel in the browser;
a window more than 2 % of whose pixels moved is shown, before and after, to a judge (the check's AI tool) that says
whether it is **broken** — cut text, things on top of each other, a part gone, unreadable — or a change that reads
well. Broken is red. The first check only pictures them. It needs Playwright and a Chromium (`orkcraft[browser]`,
`playwright install chromium`); without them it says so and is not red. Tried here: 41 windows in ~40 s, the same twice
over (0 % changed), and a window turned askew in its CSS caught and judged broken.

## 7. Next

The plan (2026-10-11), in layers — evals, not tests: repeats and medians, a baseline (the AI tool alone, and last
night), checks in code wherever code can tell, a judge only where it cannot:

| Layer | What | Model | When |
|---|---|---|---|
| Logic | tests/ | faked | every commit |
| Recorded answers | a building's whole way on answers recorded once (models and MCP: realm/cassette.py does MCP) | recorded | every commit, free |
| Evals | `orkcraft check` | the cheap one | every night |
| Real work | the day logs, 👎, what was sent back | real | always, feeding the evals |
| Quiet and cost | the quiet town | counted | every night |

In order:

1. ~~**The night check in the Mechanic**~~ — built (§8).
2. ~~**A 👎 becomes a case**~~ — built (§9).
3. ~~**Recorded answers**~~ — built (§11).
4. ~~**The Alchemist's visual regression**~~ — built (§12).
5. ~~**The night improvement works on what the check found**~~ — built (§10).

Kits still to write: the Wiki (letters in, the pages that should change and the facts they should hold), a chain
(External listeners → Task board, the whole way a letter takes).

The same Mechanic and Alchemist on any app's codebase, later: docs/design/improve-buildings.md §12.
