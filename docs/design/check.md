# Design — `orkcraft check`: the gate before people use it

Status: built 2026-10-11 (`realm/check.py`, `realm/check_pictures.py`, `check_cli.py`, `gui/idle_check.py`,
`gui/check_runs.py`; tests/test_check.py). Tried on Claude (the mail scenario, once a case): green, every call kept.

## 1. What it answers

Before the first people use Orkcraft: does it do its main jobs **well enough**, for **the cost it should**, and does a
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
| `wiki` Wiki from mail | Wiki | — | **not checked yet**: the Wiki has no Test bench kit (§7) |

A task for Jira is checked as the Task board's draft of it: a check never writes to Jira, mail or any service.

## 3. The budget

Each case runs `repeat` times (3) in its building and in the bare AI tool on the same model (core/bench.py); the bare
tool's answers are kept and read back, so a second check pays only for the buildings. A case passes when:

- the building passed its check in at least `pass_share` (⅔) of its runs, and in no fewer than the bare tool;
- its median time is at most `time_over` (+50 %) over the bare tool's, and its spend at most `spend_over` (+30 %),
  in tokens when the tool says no price;
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

## 7. Next

1. A Wiki kit: letters in, the pages that should change and the facts they should hold, checked by words.
2. A chain case: External listeners → Task board, the whole way a letter takes.
3. A 👎 becomes a case of its building, kept with the town's own cases.
