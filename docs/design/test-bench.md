# Design — the Test bench: one building on its own, measured

Status: stage 1 built 2026-10-10 (`orkcraft bench`, the Agent pool only); the rest is the plan.
For the operator only: hidden behind a flag, maybe later for developers. GUI and CLI, no TUI
([calm-town.md](calm-town.md) §9).

| stage | what | state |
|---|---|---|
| 1 | Tech, the Agent pool: a test case runs in a copy of its project, in the building and in the bare AI tool; time, spend, tokens and its check side by side (`orkcraft bench`) | built |
| 2 | the bench window: hidden behind the flag, opened by five clicks on a hut; the case, the tier and the AI tool picked there | |
| 3 | inside the run: the timeline of the steward and its orks (who was started, what ran at once, where it waited) | |
| 4 | test cases written by agents when a building has none, read by the operator before they count | |
| 5 | UX: a browser walk through build → settings → Work / Info → quick actions, with screenshots and the friction it found | |
| 6 | Product: the building's first-session moment (its AHA), its script and the time to it | |
| 7 | **Make tasks**: the findings of 5 and 6 sent to the Agent pool, by a button, never by themselves | |
| 8 | the other buildings: External listeners and Research first | |

## 1. Why

A building is a promise: *these orks, this way, do it better than the bare tool would*. Nothing
checks that promise today. A steward's replay (`realm/steward_metrics.py` `replay`) checks a
building against its own past, never against the plain AI tool it is built on.

The bench answers three questions per building, one tab each:

1. **Tech** — does it work, and does it beat the bare tool? Asked by an architect, an AI engineer
   and an AI researcher.
2. **UX** — is every step from the build menu to the quick actions clear, with no strain? Asked by
   a product manager and a product designer.
3. **Product** — what is the moment a person sees why the building exists, and does it happen in
   the first session? Asked by a product manager and an architect.

## 2. Who and where

- **The operator only**, for now. The bench is shown only when `ORKCRAFT_BENCH=1` is set or the
  machine setting `bench` is on. Then **five clicks on a hut** within two seconds open its bench
  (`js/hut.js`, the click that did not move). Without the flag the clicks do nothing, so nobody
  opens it by chance. `orkcraft bench <type>` works with or without the flag.
- **It never touches the town.** Every run is in a copy of the project
  (`.orkcraft/bench/runs/<run>/`), a clone without its `origin`: nothing is pushed, no pull request
  is opened, no road carries a cart out, and the town's ledger is not written. A changed prompt,
  tier or AI tool is the bench's only. **Apply to the building** sends it the ordinary way
  (`realm/evolution.py`: its ledger, its probation, Z takes it back).
- **Spend is capped.** A run has a limit (`--max-spend`, $2 by default). The building's runs stop
  at it, and the bench says it was cut, not that it failed.

## 3. Tech

### 3.1 A test case

A case is one JSON file: the project it starts from, the task, and how the result is checked.

```json
{
  "id": "slugify",
  "type": "barracks",
  "title": "Add a slugify helper",
  "task": "Add slugify(text) to src/text.py: lower case, words joined by '-', ...",
  "files": {"src/text.py": "...", "tests/test_text.py": "..."},
  "check": "python -m pytest -q tests",
  "expect": "what a good result has, in words, for the judge (stage 4)"
}
```

- `files` is the whole project, so a case runs the same on any machine. With no `files`, the case
  runs on a copy of the town's own project at its `HEAD`.
- `check` is a command run in the result's tree: exit 0 is a pass. A check that can say it in
  code says it in code. A model judges only what code cannot, blind (it is not told which result
  is the building's), in stage 4.
- Where cases live: `realm/bench_cases.py` ships a few per type, and the town's own go in
  `.orkcraft/bench/<type>/*.json`. Agents write a missing case and its check (stage 4). A written
  case counts only after the operator has read it (`"reviewed": true`), so runs stay comparable:
  a case is never written again on each open.

### 3.2 A run

One run is one case, two sides, the same model:

| side | what runs | where |
|---|---|---|
| **building** | the building as raised in the town (its config, its steward's rules), with the bench's tier and AI tool when set; the task arrives as a new task | a town opened on its own copy of the project (`core/bench.py`) |
| **bare** | the AI tool with only the task as its prompt (`jobs.run_work`), on the same tier's model | a second copy of the project |

The bare side gets the same model as the building's orks, so the comparison is of the building,
not of the model. A decision wants three runs or more, because one run says little when models
vary (a `--times` that repeats a run is still to come).

Measured on each side: **time** (wall clock), **spend** ($, the steward's included), **tokens**,
**the check** (pass or fail, its last lines), **the change** (files and lines). The building's side
also says **how it went**: its decisions (`decisions.jsonl`), how many orks it started, the parts
of its plan, its reworks.

The run is kept in `.orkcraft/bench/runs/<run>/report.json`, next to both copies, so the bench window
shows the last runs and any two can be compared.

As built (stage 1):

- The building's side copies the config of the operator's building of the type (`--building` names
  which), drops what points at the operator's project (`repo`, `notes`, `base`), and sets
  `worktrees`, `budget_usd` (the spend limit) and `test_cmd` (the case's check; the
  pool and Branches & PRs now start a test command that needs a shell through `sh -c`). `--tool` / `--tier` set its `providers` and `steward`.
- It is done when its task is done or failed, or when the steward asks the operator (the bench says
  so and stops: nobody is there to answer), or at its spend limit or 45 minutes (*cut*).
- Tokens are the orks' only: the pool does not count the steward's yet. Spend counts both.
- The building's result is checked in a worktree of its task's branch (`building-result/`), the
  bare tool's in its own copy, what it left uncommitted included.

### 3.3 Inside a run (stage 3)

What the steward and its orks did, on one time axis: a line per ork, a bar per run, the steward's
judging and reviews on their own line, a question to the steward as a mark. For the Agent pool
it shows how the plan was split and what ran at once; for Research and the Review board, their own
inner agents. The events come from the bus (`core/bus.py`) and the building's decisions.

### 3.4 Tiers, AI tools, prompts

In the bench every ork's tier (Novice, Seasoned, Veteran) and AI tool can be changed, and the
steward's and the orks' instructions edited, for the next run only. Two runs differing in one of
them are put side by side.

## 4. UX (stage 5)

A walk in a browser (Playwright, the GUI in `--browser`), on a fresh town in a temp folder: build
the building from the build menu, set it up, open Work and Info, press each quick action. At each
step it keeps a screenshot and counts the decisions asked, the fields, the clicks, and any word
that is not today's (`realm/lexicon.py` `TERMS`, CLAUDE.md Wording). A product manager and a
product designer (two agents, the Usability reviewer's prompt as their base) read the walk and
name each place a person would stop and wonder: what is it for, what does it cost, what happens
if I press it.

The walk runs on **Review again**, never on each open: its findings are kept with the building's
version, and the tab shows the last ones and what changed since.

## 5. Product (stage 6)

For each building, its **AHA**: the first moment a person sees why it is worth having, reached in
the first session. A product manager and an architect write it as a hypothesis, a script and a
measure:

| building | the moment | measure |
|---|---|---|
| External listeners | a test mail sent to your own address arrives sorted, with its reply drafted, within a minute | minutes from build to the first sorted mail |
| Agent pool | a small real task on your project comes back as a pull request with green tests, and you see which orks split it | minutes to the first accepted task |

The bench holds the design and the measure. The moment itself goes into the building's first run
for everyone (its setup in the Warchief's line, [select-a-building.md](select-a-building.md) §7),
not into the bench.

## 6. Make tasks (stage 7)

Every finding in UX and Product has a box. **Make tasks** sends the ticked ones to an Agent pool
the operator picks, one task each, with the finding, its screenshot and the files it names. Never by
itself: a finding is advice until the operator presses the button.

## 7. Where the code goes

| what | module | why there |
|---|---|---|
| cases, the copy of a project, the bare side, the report | `realm/bench.py`, `realm/bench_cases.py` | no face; it never imports the GUI or the core |
| the building's side: a town on the copy, the task in, wait, read its state | `core/bench.py` | it opens a `Town` |
| `orkcraft bench <type>` | `cli.py` | |
| the window (stage 2) | `gui/views/bench.py`, `static/js/bench.js` | |

Agents are started through `jobs.run_work`, so Stop all stops them (`realm/halt.py`).

## 8. Not doing

- Opening the bench for everyone: it is a tool to build buildings, not a part of the town.
- Writing a case again on each open: runs would not compare.
- Changing a building from the bench without Apply.
