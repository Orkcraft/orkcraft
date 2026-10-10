# Design — the Test bench: one building on its own, measured

Status: stages 1–9 built 2026-10-10 (runs for the Agent pool, External listeners, the Task board, the Calendar, Research and the Review board); §9 says how it is built.
For the operator only: hidden behind a flag, maybe later for developers. GUI and CLI, no TUI
([calm-town.md](calm-town.md) §9).

| stage | what | state |
|---|---|---|
| 1 | Tech, the Agent pool: a test case runs in a copy of its project, in the building and in the bare AI tool; time, spend, tokens and its check side by side (`orkcraft bench`) | built |
| 2 | the Test bench is a building (Alchemist's Lab in Camp words): a road in says what it tests, a road out where its reports and findings go; its window is the bench | built |
| 3 | inside the run: the steward's and each ork's decisions on the run's clock, a lane each | built (decisions; the runs' own spans later) |
| 4 | test cases written by agents, read by the operator before they count | built (Write a case) |
| 5 | UX: two reviewers read the building's code and flow and name where a person would stop | built (reading code; the browser walk with screenshots later) |
| 6 | Product: the building's AHA moment, its script and its measure | built |
| 7 | **Make tasks**: the ticked findings sent to the Agent pool picked, by a button, never by themselves | built |
| 8 | runs for External listeners, the Task board and the Calendar (§3.5) | built |
| 9 | runs for Research and the Review board (§3.5) | built |
| 10 | runs for the other buildings | |

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

- **A building of its own**, the **Test bench** (`lab`; *Alchemist's Lab* in the Camp's words, its ork
  the *Tester*, Brewmaster of old). It is built from Build like any other (Check → Test).
  - **A road in** from a building says *test this one*: its cases run in a copy of it with its own
    settings. What that building sends along the road is only noted (the window lists it); a run
    starts from the window or the quick action **Run the first case**, never by itself.
  - **A road out** says where results go: each case's whole run as text (`lab.report`), what the
    building missed (`lab.missed`), and the findings Make tasks sends **Down its roads**
    (`lab.finding`). A road to an Agent pool makes them its tasks; to a Task board, cards.
  - Several roads in: the window picks one building at a time.
  - `orkcraft bench <type>` runs the same in a terminal.
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

**The Agent pool's sets** (`realm/bench_sets.py`, with `realm/bench_cases.py`'s own four): fifteen cases, five
of each `level`, the path the pool should take on it:

| level | what it is | the path in the pool |
|---|---|---|
| `simple` | short, no list of steps (`plans.clearly_simple`) | one ork of the goal's tier at once; with a `test_cmd`, no steward call at all: its tests are its review |
| `medium` | one ork's job that needs thought | the steward's sort, one ork, then the steward's review |
| `parallel` | three independent parts, then one that needs them all | the steward's sort and plan, parts at once, the last one after them |

Each has a known solution in `tests/bench_solutions/<case>/`: `tests/test_bench_sets.py` checks that the
case's check fails as given and passes on it, and that its level is the path the rules give.

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

**A series**: `orkcraft bench --case all`, or `--level simple|medium|parallel`, runs the cases one after
another (each with its own spend limit) and ends with a summary: per case, how much more time and spend the
building took than the bare tool, and its check against the bare tool's. A case is **within 10 %**
(`bench.GAP_LIMIT`) when its check is no worse and both time and spend are at most 10 % over. The window's
Case list offers the same series, and *The Agent pool against the bare AI tool* holds the latest run of each
case so (`bench.against`).

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

### 3.5 Buildings whose work is not code (stage 8)

A case of such a building carries its `inputs` and, item by item, what each should come to; its kit
(`realm/bench_kits.py`) says what the bare AI tool is asked and how its JSON reads, and one check judges
both results. The building's side (`core/bench_kits.py`) opens a town on the copy, raises the building
as it is in the operator's town (its sources, accounts and paths left out: a copy never listens to the
operator's mail), gives the input the way its sources would, and reads the result back. Spend and tokens
come from the copy's own ledger of model calls, so every call counts. The bare AI tool runs on the
tier the building's own call ran on when no tier is picked, in a copy of the project it may read.

| building | given | the building's way | checked |
|---|---|---|---|
| External listeners | an intent and a morning's messages (sender, subject, body, list headers) | each message as it arrives (`add_signal`), judged by its Listener with triage | kept or left out per message, importance and who answers where the case says |
| Task board | long cards to name; to-dos to plan; wiki pages in the copy | `write` (its steward names the card), `add` to the person's to-dos, its context from the wiki, `plan` | 2–4 words and the key words for a title; 3–7 steps and the case's words for a plan (the wiki's facts: a policy number, who to call) |
| Calendar | a week's meetings with attendees and invitations; how a brief is written | the calendar reads the copy's `.ics`; `meeting soon` goes along a road to an Agent pool raised with the operator's pool's settings; the brief comes back along `pool.done` | a brief per meeting, the sections asked for, the names and the invitation's points |

| Research | a question whose answer is settled on the open web, the facts it should find, how many sites | `ask`; its plan, a web search by every tool at once, grouping and its code check, rounds; the case's `rounds`, the run's spend as its limit | each fact in a claim that has a source; sources on enough sites. The bare AI tool searches the web too, and its findings are read by the Mine's own parser |
| Review board | a document with flaws planted in it and the roles to read it; or a request and the board's exits | `review`; each role in turn, then its steward; members and moderator on the run's AI tool and tier | the verdict; each planted flaw named in what the board said (never in the document); the exit it was sent down |

Their cases come in the Agent pool's levels (`realm/bench_kit_cases.py`): **simple** — a few clear
items; **medium** — items that take judgement (what only looks like what is wanted, a wiki to use, an
invitation to read, a to-do in Russian, an email the plan must bring back as it was); **parallel** — many
at once (a burst of 14 messages, a board of six cards and two plans, a day of four meetings). Every one
is checked against an ideal answer built from its own expectations, so a case never asks what its
check cannot see.

Research needs the open web: it cannot read local files, so its cases ask about dates and numbers that do
not move. With one web tool on, nothing can reach *confirmed* (two minds are needed), so its check asks
for a sourced claim, not a confirmed one.

Found and fixed on the way: Research ran its rounds of web searching even with fewer tools than a
confirmation needs, spending its limit on what could never be confirmed; now it runs them only when it
could. The calendar dropped an invitation's attendees and description, so a brief
never knew who comes or what the agenda was (`sources/ics.py`, `daybook.invitation`).

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

## 9. As built: the window (gui/bench.py, js/bench.js)

- The Test bench building (`core/workers/lab.py`) knows its roads: the buildings whose road comes in
  (`subjects`), where its roads go (`targets`), what came in (`heard`) and the last run of each. Its
  window (`gui/views/lab.py`, `js/buildings/lab.js`) is `js/bench.js` `BenchView` for the building
  picked; each command names that building and the Test bench (`lab`), so Make tasks can offer
  **Down its roads** and list the Agent pools its roads reach first. When a case's run ends,
  `gui/bench.py` hands the kept run to every Test bench that tests the building, and it says it down
  its roads. Its card: the building it tests and its last run (its own, else the latest kept of that
  type), or *Nothing to test* with how to give it one.
- **Tech.** *Run a case*: the case (only cases read count), the AI tool, the orks' tier, both sides or
  one, the spend limit, and the steward's instructions for this run only. A run is `orkcraft bench` in a
  process of its own (one process holds one town), registered in Stop all; its lines show as they come,
  its last line names the kept run. *Runs*: the kept ones, newest first, side by side, the checks'
  last lines, the reports, and *Inside the run*. *Cases*: each with its task, check and project;
  a written one says *not read yet* until **I read it: it counts**. **Write a case** asks one agent.
- **Reviews.** Tech: architect, AI engineer, AI researcher (the last run in their prompt). UX: product
  manager, product designer. Product: product manager, architect, each with the AHA moment shown above
  the findings. Every reviewer is one AI tool call that only reads Orkcraft's own source and answers in
  JSON (`realm/bench_review.py`), kept in `.orkcraft/bench/reviews/<type>/<tab>.json` with the
  Orkcraft version: a newer version marks it to review again.
- **On open.** A building whose type has no review kept gets all seven reviewers at once, the first
  time its bench opens (what the operator asked for); after that only **Review again** starts them.
- **Copying for an analysis.** A run's terminal keeps to its last four lines; **Copy** takes every line it
  wrote. **Copy for analysis** on a run gives the whole of it as text (`bench.analysis`): the table, then
  each side's model, every check, how it went, its decisions on the clock, its check's last lines and its
  report. On the summary of cases it gives the building against the bare tool, case by case.
- **Make tasks.** The ticked findings of any tab go to the Agent pool picked, one task each, with the
  reviewer, the tab, the finding, where, its severity and Orkcraft's version.
