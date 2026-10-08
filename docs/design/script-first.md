# Design — script-first buildings: code does the work, the ork wakes on an error or a 👎

Status: written 2026-10-07; stage 1 (the rule, the wakes, the retro's guard) is built, stage 2 (the GUI) is
not yet (§7). Part of the simplification
([simplify.md](simplify.md) §7). Builds on the steward ([steward-at-work.md](steward-at-work.md)), its
keeper (`core/keeper.py`), the 👍 / 👎 (`realm/feedback.py`) and the Building retro (`realm/optimize.py`).

## 1. Why

Many buildings are a script with a face. A Drop file here sorts what is dropped, a Sound alerts plays a
sound by a rule, a Router sends a cart down the road its rules name, a File tree lists files, a Metrics
draws charts, a Calendar reads an `.ics`. No step of that needs judgment, and no step of it should cost
a model call.

Each of these buildings still has an ork: its steward. The question is when the ork thinks.
Two things are wrong today:

- **Nothing promises that the ork stays asleep.** Whether a building calls a model depends on its parts
  (an `agent:` step in a Transformer, an agent handler on a road, a Script's escalation prompt) and on the
  town's own schedules. The building, its card and its window never say which case it is in.
- **When the script goes wrong, nobody wakes.** A Router whose rule no longer matches, a Calendar that
  cannot read its file, a 👎 on a Sound alerts: today none of these reaches a mind. The Building retro
  ranks buildings by what they spend, so a building that spends nothing is never its pick. When it
  does pick one (a 💎 Drop file here with a 👎), it finds no prompt to change and the day's one retro
  goes by with nothing done (measured, §2).

The rule this design follows: **in a script-first building the ork never runs on a cart, a tick, a
refresh or a schedule. It wakes when the script fails or the person gives the building a 👎, and when
the person asks it.**

## 2. Audit: where a model can be called

Every model call ends in one of two seams: a one-shot prompt (`realm/builders.py` `ask`, through
`main_runner`, `runner_for` and the steward's `runner_for`) or an agent process (`realm/roads.py`
`run_agent`, `realm/jobs.py` `run_work`). Grouped by what triggers them:

| Who | Where | Trigger | How often |
|---|---|---|---|
| Drop file here, Sound alerts, Router, File tree, Metrics, Calendar, Review gate, Branches & PRs | their workers (`core/workers/pit.py`, `horn.py`, `signpost.py`, `forest.py`, `crag.py`, `war_drum.py`, `loot.py`, `forge.py`) | — | **never**: rules, files, git |
| Transformer | `core/workers/mill.py` → `realm/mill.py` `default_agent` | every cart, once per `agent:` step (and a failing `script:` step that falls back to the agent) | per cart |
| Script | `core/workers/workshop.py` `run_cart` → its steward's `escalate` | a cart whose script exits 3, only with a steward prompt | per escalated cart |
| External listeners | `core/workers/watchtower.py` → `realm/lookout.py` `judge` | new signals when it has an `intent` (and the light model is on) | per batch of 20 |
| Task board | `core/workers/fields.py` `title`, `fields_lore.py` `plan` | a long card written; ▶ plan | per card / click |
| Agent pool, Review board, Wiki, Publisher, Town Hall | their workers | each task, cart, ingest, message | their work |
| Any building with an agent (or hybrid) handler | `realm/roads.py` `Engine._agent_thread` | a burst of carts on its road (`quiet_s`) | per burst |
| The steward's Watch, Redesign, keeper, Road planner, Ork setup | `gui/steward.py`, `gui/keeper.py`, `gui/road_planner.py`, `gui/recruiter.py` | the person asks (W, D, plain words) | when asked |
| Building retro | `core/retros.py` `daily_job` → `realm/optimize.py` `propose` | `optimize_at` (daily 06:20), one building, when `leader` names one | once a day |
| Town retro | `core/retros.py` `weekly_job` → `realm/weekly.py` | `weekly_at` (Sunday 05:00) | once a week |
| Council's Fast Path, Advisors | `gui/nightly.py`, `gui/host.py` `_night` | quiet hours: a change to apply, a question waiting | ≤ 10 / ≤ 40 a night |

The GUI never runs a steward's Watch on its own. Only the deprecated TUI does, for a steward whose
trigger is `cron`. The steward's metrics (`steward.collect`, `findings`) are local code and free.

**Measured** with `tools/count_model_calls.py`. It builds the dashboard demo, opens it as a real town
with every model seam replaced by a counter, drops pastes into the Gates' Drop file here and ticks the
host a minute apart with the retros due every minute:

| Run | Model calls |
|---|---|
| 20 pastes, 120 ticks | **10**: 7 from the Release notes Transformer's `agent:` step (one per paste the Router sent to it), 2 Building retro (it picked the Agent pool), 1 Town retro. **0** from Drop file here, Router, Script, Sound alerts, Publisher |
| 0 pastes, 👎 on Drop file here (⚖️) | 3 (the retros): the 👎 reached no mind |
| 0 pastes, 👎 on Drop file here (💎) | 1: the Building retro picked Drop file here, found nothing to change and made no call. The day's retro was spent on it |

So the script buildings are already quiet on their carts. What they lack is a promise that they stay
quiet, a word on their card that says so, and a mind that wakes when they fail.

## 3. The rule

**Script-first types**: Drop file here (`pit`), Sound alerts (`horn`), Router (`signpost`), File tree
(`forest`), Metrics (`crag`), Calendar (`war_drum`), Review gate (`loot`), Branches & PRs (`forge`). Their
work is code by construction.

**Script-first when their parts are code**: a Transformer (`mill`) none of whose steps is `agent:`, a
Script (`workshop`) with no steward prompt to escalate to. A Transformer with an `agent:` step or a
Script that escalates is a building that thinks on its carts, and its card says so (§5).

**Either way**, a building that has a handler that thinks (`uses_model`: an agent, a hybrid, and the
steward's road rules once [steward-listens.md](steward-listens.md) lands) is not script-first while it
has one. It keeps working as it does (§7).

`realm/script_first.py` holds the rule:

- `TYPES` and `is_script_first(spec, building)`;
- `thinking(spec, building)` lists what still calls a model (an `agent:` step, the escalation prompt, a
  handler by name).

Every reader asks this module. No face keeps its own list.

External listeners, the Task board and the rest are not script-first: their model calls are their
work. The listeners may join later, when they listen without an `intent`; that waits for the External
listeners work in flight.

## 4. What wakes the ork

In a script-first building the steward's model is called only for:

1. **An error.** The worker says `ERROR` (`Worker.status()`: a Router rule that does not parse, a
   Calendar file it cannot read, a File tree it cannot scan, a Review gate that cannot read its branch, a
   Metrics over its red line), or a run of its own fails (a Script's run `failed`, a Transformer's
   step), or a handler of its garrison (a chain, a script) ends in `error`.
2. **A 👎.** An explicit 👎 on the building: the button, or the retro's rating. It is an incident whose
   `source` is `explicit` and which names the building. The quiet signals (a cart accepted with edits,
   a file reshaped) weigh too little alone. They stay with the retros as today.
3. **The person asks.** Watch, Redesign, the keeper in plain words, Listen in words, Ork setup. These
   are not wakes: they are the person's own call, and they stay as they are.

**Once.** An error wakes the ork once per *spell*: when the building goes into `ERROR` (or a run fails)
after it was well. It does not wake again while the error stays, however many carts fail. It wakes
again only after the building was well once more. A 👎 wakes it once per incident. 👎s that come while
a wake waits for the person fold into it. At most one wake per building is open at a time.

**What a woken ork does.** It is the building's keeper (`core/keeper.py`), asked in words the town writes
for it:

- for an error: *what failed, the error, what it was given*, and "change its settings so it does
  not";
- for a 👎: *the person's note, the kind (its logic, its inputs), its last result*, and "change its
  settings so its next result is what they want; if its inputs were broken, say which building to look
  at".

The keeper may change only its type's subject (the whole `config`, or the part the type registers: the
Router's rules, the Script's code and schedule). Its answer is checked like any spec. It comes back as
a proposal in the building's console, the same job as a keeper asked by hand: a diff and an answer,
**Apply** or close. A wake never changes the building by itself.

**What it costs.** One keeper call (at most `keeper.MAX_ATTEMPTS` rounds when an answer is rejected),
on the steward's tier for `keeper`. No call when the 🪙 limit is reached (the wake waits and is tried
again), and none in the demo, where the wake is shown and the keeper's fake answers.

**What stays free.** The steward's metrics (`steward.collect`, `findings`), the error and 👎 checks
themselves (local files and the workers' state, looked at every few seconds), the wake log.

**The Building retro** skips script-first buildings: they have no prompt it could shorten or enrich,
and their 👎s and failures now reach their own keeper. Its one daily call goes to a building that thinks.
The Town retro still reads the whole town once a week.

## 5. How it looks (GUI only, the TUI is deprecated)

- **The steward's window** (`js/steward.js`): under the steward's head, one line,
  **`Script-first · no model · its ork wakes on an error or a 👎`**. Its tooltip names what is checked.
  A building of a script-first type that thinks (a Transformer's `agent:` step, a handler) says instead
  **`Thinks on its carts: <parts>`**, so the person sees why it is not.
- **Its card** on the town: a script-first building's spend line reads `no model` where today it reads
  `🪙 nothing spent`.
- **A wake**: a toast, *"<building>: its ork woke on an error — a fix waits in its console"* (or *on a
  👎*). The console's job is the keeper's proposal, titled by what woke it. Closing it puts the wake away.
  The next error spell or 👎 can wake it again.
- **The wake log**: `.orkcraft/script_first/wakes.jsonl` (when, building, why, the error or the
  incident). The window's line shows the last wake: *"woke 14:02 on an error"*.

Wording (CLAUDE.md): `TERMS` gets `script_first` → **Script-first**. The line is plain, as a label about
cost should be.

## 6. Settings and migration

- **Nothing to set.** Script-first is a property of the type and of the parts, not a setting. A building
  becomes script-first when its last thinking part goes: a demotion, a Transformer whose `agent:` step
  is replaced. It stops being script-first when one is added.
- **Existing towns load as they are.** No field is added to the Project file or to a building's spec.
  The wake log and its cursor live in `.orkcraft/script_first/`, git-ignored like the rest of `.orkcraft/`.
- **A building whose handler is an agent today keeps working.** It is simply not script-first. The
  steward proposes the demotion as it does today (its Watch: `repeats` → `demote`, replayed before it can
  replace the agent). Once demoted, the building is script-first and its window says so.
- **The Workshop's escalation stays.** A Script with a steward prompt hands its exit-3 carts to its
  steward as today: the person asked for that judgment. Without one it is script-first, and a failed
  run wakes its keeper.
- **The demo** shows the line on every script-first building. A wake there uses the keeper's fake
  runner (`runners.KEEPER_RUNNER`). When there is none, the wake is logged and toasted but asks no model.

**Built (stage 1):**
- `realm/script_first.py` holds the rule (`TYPES`, `WHEN_CODE`, `thinking`, `is_script_first`), the wake
  log (`wakes.jsonl`) and its memory (`state.json`).
- `core/wakes.py` has no face and calls no model. `due` reads the workers' `status()` (a type whose ERROR
  is a reading says so: `Worker.ERROR_IS_FAILURE`, False for Metrics), the last run of each handler and
  the explicit incidents. `taken` remembers and logs a wake. `start`, when the town opens, makes the
  👎s from before not news.
- The Host asks every `WAKE_CHECK_S` (5 s) and runs each due wake as the keeper's job
  (`gui/keeper.py` `keeper_wake`). A wake that cannot run now is due again at the next look: the budget
  is spent, or a wake of the building is still open in its console.
- `core/retros.py` `daily_job` leaves script-first buildings out of the Building retro's goals.
- Incidents are stamped to the second, so the memory keeps the keys of the ones at its cursor's second:
  two 👎s in one second are two wakes.

## 7. Stages

1. **The rule and the wakes** (`realm/script_first.py`, `core/wakes.py`, the Host's check, the keeper
   job, the retro's guard). Tests: a script-first building makes zero model calls over N carts and
   ticks, with a runner that fails the test if called; an error wakes the keeper once; a 👎 wakes it
   once.
2. **The GUI**: the steward window's line, the card, the wake's toast and job. Checked in the real
   demo with Playwright.

Not in this design: turning the External listeners or the Task board script-first, and a Transformer's
`agent:` step replaced by code on its own (the steward's demotion covers handlers; a Transformer's steps
are its keeper's subject, so the person can ask it in words).
