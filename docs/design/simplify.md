# Design — fewer minds, one word each: simplifying the town

Status: written 2026-10-07; stage 0a (the purpose and the ledger on disk) built 2026-10-08, see §11;
*By purpose* in the Spend window (stage 0b) not yet. Stage 0 measures before anything is cut; stage 4 (the
watchers) may start at once. Builds on the Town Hall's Council (`realm/fastpath.py`, `realm/council.py`,
`realm/audit.py`), the Elders (`realm/elders.py`, `core/night.py`), the steward
([steward-at-work.md](steward-at-work.md)), the retros ([retros-and-goals.md](retros-and-goals.md),
`realm/optimize.py`, `realm/weekly.py`, `realm/evolution.py`), the Wiki ([wiki-librarian.md](wiki-librarian.md))
and the Agent pool's paths ([barracks-flows.md](barracks-flows.md)).

## 1. Why

The town grew one mind at a time, each for a good reason, and now a person cannot say who decides what:

- **"Council" means four things.** The Town Hall's Fast Path (five councillors review every new
  building, agent and road), the Town Hall's audit (Warder, Pathfinder, Treasurer), the runtime watchers
  (`realm/council.py`: only the Warder lives, Drummer, Taskmaster, Alchemist and Keeper are names in a
  docstring — the `watchers/` folder they point to does not exist), and the Clan Fire's type id
  `council`, a building that has nothing to do with the Town Hall.
- **Two minds answer the orks' questions.** The Elders answer an agent's permission menu in quiet
  hours; the building's steward answers its orks' questions by the autonomy level. Same job, two
  settings, two logs, two sets of rules.
- **The Warder stands in three places**: in the Fast Path, in the audit and as the live hook — with
  one set of rules, but three names for where it ran.
- **Three layers of retros** (the steward's own watch, the daily Building retro, the weekly Town
  retro) look at the same buildings and propose the same kinds of change.
- **Names collide**: *Drummer* and *Taskmaster* are the War Drum's and the Task board's orks *and*
  runtime watchers; *keeper* is every building's steward *and* a watcher.
- **Model calls nobody asked for**: the Wiki's spot-check after each ingest (`review_sample`, a
  Review board call), the Elders and the steward both reading a question, a Barracks on *balance*
  reviewing every task. The spend of each is not known: the side ledger (`sources/telemetry.py`
  `charge`) keeps only a cost and a `source`, in memory.

The rule this design follows: **one concept, one mind, one word**. Nothing is cut before stage 0 has
measured what it costs.

## 2. Stage 0 — measure first

Every model call gets a **purpose** next to its building, and the ledger is kept on disk:

- `telemetry.charge(usd, source, purpose=…, tokens=…)`; `purpose` is one of a closed list:
  `work` (an ork's task), `sort`, `plan`, `review` (a Review board turn), `check` (spot-check, lint,
  quality), `ingest`, `answer` (a question answered for the person), `look` (Lookout, carried look),
  `retro`, `build` (Fast Path, Recruiter, Town planner), `chat` (the Warchief).
- Transcript runs (`ORKCRAFT_RUN`) carry the purpose in their env, so they count the same way.
- `.orkcraft/spend/calls.jsonl`: one line per call (when, building, purpose, model, tokens, $), kept by
  the housekeeping's log limit.
- The Spend window gains a *By purpose* view: the last 7 days, $ and tokens per purpose, and per
  building inside each.

After a week of the person's own town (and the demo's recorded week), the numbers decide stage 3: a
purpose that costs under 2 % of the week and catches something is kept as it is.

## 3. One word per concept

| Concept | Today | After |
|---|---|---|
| Review every new building, agent, road | Council's Fast Path, five councillors | **Build check** — the same rules and one light call; its five roles are *its checks* (budget, schemas, layout, security, workspace), not orks |
| Look over the standing town | `/audit`: Warder, Pathfinder, Treasurer | **Audit** — unchanged, its orks keep their names |
| Guard every tool call | the Warder's hook | **Warder** — one set of rules, used by the hook, the Build check, the Audit and the night answers; one log (`.orkcraft/warder.jsonl`) says which of them asked |
| Answer an ork's question for the person | Elders (night) + the steward (by autonomy) | **the steward** — the Elders become its quiet-hours mode (§4) |
| Watch the town while it runs | the runtime Council, mostly names | **Watchers** (§6): Warder, Pacer, Treasurer, Alchemist, Peon |
| A building where roles argue and judge | Clan Fire, type id `council` | **Review board**, type id `review` (§5) |
| The Town Hall's settings for all of this | `.orkcraft/council/settings.json` | the Town Hall's settings; the file is read from its old place once and moved |

The **Council** stays only as the Town Hall's own word for the Build check and the Audit together
(*the Town Hall's council*), never as a building type. `TERMS` gets *Build check* and *Watchers*;
*Advisors* (the Elders) keeps its old spelling in `was` of *Night answers*.

## 4. The Elders become the steward's night

- The steward already answers its orks' questions by autonomy (`steward.py` `TYPE_USES[…]["answer"]`).
  An agent's permission menu (an `Alert` from the terminal) is one more kind of question it answers.
- What the Elders did stays, as the steward's rules for that kind: the Warder first (a block is never
  answered, a warning is answered only by the person), only a one-time yes, the light model as judge,
  `elders_per_night` and `elders_context` as the steward's settings `night_answers` and `night_lines`.
- The autonomy table is the steward's, as today for its other questions: ⛓️ advise, 🕰 answer after the
  wait (at once in quiet hours), ⛓️‍💥 at once.
- One log: `.orkcraft/<type>/<id>/answers.jsonl` of the building whose ork asked; the morning summary
  reads all of them. `elders.jsonl` is read once and split by building.
- A question from a session no building owns (a War Tent session) is answered by the Town Hall's
  steward, the Warchief, under the same rules.
- `realm/elders.py` stays as the rules module the steward calls (`judge`, `_WIDENS`); `core/night.py`
  asks the owning steward instead of the Elders. The Town Hall loses its *Elders* line; each building's
  window shows *Answered tonight: N* in its steward's block.

## 5. The Review board leaves `council`

- Type id `council` → `review`. `catalog.ALIASES` gets `"council": "review"` (beside `team`, `campfire`,
  `clan_fire`), so every Town Scroll, preset and setting written before loads as a Review board.
- Code follows: `core/workers/council.py` → `review.py`, `council_setup.py` → `review_setup.py`,
  `design/buildings/council.json` → `review.json`, `gui/views/` and `js/buildings/` the same; the old
  module names stay as thin imports for one release.
- Event ids and dict keys that other buildings' settings name stay as they are (a road filter on
  `council.verdict` keeps working); new ones are written with `review.`. The Wiki's setting `council`
  (the board that spot-checks it) is read as `review_board`, the old key still accepted.
- `TERMS`: the Review board's id word is `review`; `was` keeps *Clan Fire* and *Council*.

## 6. The watchers, made real

The runtime Council's drafts get a job each, a name that collides with nothing, and live code. A watcher
**uses no model unless stated**: it reads what the town already records and raises an alert or acts by
autonomy. All of them live in `realm/watchers/`, run by the Town Hall's clock, and report to the Town
Hall's *Watchers* block (one line each: what it saw today).

| Watcher | Was | Watches | Acts |
|---|---|---|---|
| 🛡 **Warder** | Warder | every tool call (the hook, as today) | deny / ask, as today |
| 🥁 **Pacer** | Drummer | sessions and runs: a question waiting past its building's wait, a session idle with a task in work, the same tool call repeated (a loop), a run past its time limit | alert; on ⛓️‍💥 stops a looping run (through `halt`), never a session the person is typing in |
| 🪙 **Treasurer** | Taskmaster's budget duty | the spend rate (stage 0's ledger) against the 🪙 / 🪵 limits and the quota's pressure (`realm/pressure.py`): *at this pace the day's limit is gone by 15:00* | alert at 80 % of the pace; on 🕰 / ⛓️‍💥 pauses the building that eats most (its queue, not its running ork) |
| ⚗️ **Alchemist** | Alchemist | model fit, from the ledger and the results: a building whose heavy-tier runs pass every check for a week; a light tier whose runs fail and are retried on a heavier one | a proposal for the Building retro (it picks the next building, §7); **no model call of its own** |
| ⛏ **Peon** | Keeper | the housekeeping (`realm/housekeeping.py`) on a schedule: logs, orphans, prunable worktrees, a demolished building still listening; worktrees of finished tasks | cleans what housekeeping already may clean; anything else is an alert |

The Taskmaster stays the Task board's ork and the Drummer the War Drum's: the watchers take other
names. The Keeper as a watcher is gone: *keeper* is only ever a building's steward.

## 7. Two retros, not three

- **The steward's watch** stays: it is free (rules over its own building's records).
- **The Building retro** (daily) takes its pick from the Alchemist and the steward's findings instead
  of ranking every building again; it stays one proposal a day.
- **The Town retro** (weekly) stays, and its input gains stage 0's *By purpose* week.
- What goes, if stage 0 says it costs and catches little: the Wiki's spot-check after each ingest
  becomes part of the Librarian's quality check (rules first, a model call only for the pages that
  changed, once per check, not per ingest); a Barracks on *balance* reviews a task only when the
  Alchemist or the steward flagged its building, not every task.
- A building whose work is code calls no model: its ork wakes on an error or a 👎 ([script-first.md](script-first.md)).

## 8. Migration

- Every Town Scroll, preset and setting written before loads: `council` is an alias; the Council's
  settings file and the Elders' log are read from their old places once.
- A town that relied on the Elders keeps the same answers at night: the owning steward applies the
  same rules with the same limits, moved from the Council's settings.
- No setting is removed in this design; a setting that loses its meaning (the Elders' two) is read into
  its new key and kept one release.

## 9. Stages

0. **Measure**: `purpose` on every charge and transcript run, the on-disk ledger, *By purpose* in Spend.
1. **Review board leaves `council`** (§5) and the words of §3 in `TERMS`, the GUI and the docs.
2. **The Elders into the steward** (§4).
3. **The cuts of §7**, each decided by stage 0's numbers and written into this document with them.
4. **The watchers** (§6): Pacer, Treasurer and Peon first (no model, records the town already keeps),
   then the Alchemist (it needs stage 0's ledger for a week of data; until then it reads the run
   history only). `realm/council.py` becomes `realm/watchers/` with a thin import.

Stages 1, 2 and 4 do not depend on each other; 3 waits for a week of stage 0.

## 10. Open questions

- Should the Pacer ever stop a run on 🕰, or only on ⛓️‍💥? This text says only ⛓️‍💥.
- A War Tent session's question at night: the Warchief answers, or nobody (it waits for the person)?
  This text says the Warchief, under the Warder's rules.

## 11. As built

**Stage 0a — 2026-10-08** (the night session P3):

- `sources/telemetry.py`: `PURPOSES` is the closed list of §2. `charge(usd, source, purpose=, tokens=,
  building=, model=)`; a call with no purpose of its own takes the one its caller set with
  `telemetry.tagged(purpose, building)` (a context variable, so per thread), else `work`; a word not on the
  list is never written. The in-memory ledger keeps `Charge` tuples; the snapshot adds `side_by_purpose`
  and `by_purpose` (all of this run's 🪙, transcripts included).
- `.orkcraft/spend/calls.jsonl`: one line per call — `at`, `building`, `purpose`, `model`, `tokens`,
  `usd` (null: unpriced), `source`. The town turns it on (`keep_ledger`) when it starts; a call that only
  runs in memory (a test, a CLI with no town) writes nothing. `telemetry.calls(repo_root, since)` reads
  it back for stage 0b. The housekeeping's `LOG_LIMIT` already covers every `*.jsonl` under `.orkcraft/`.
- Transcript runs: a call that carries `ORKCRAFT_RUN` (a road's agent, a Barracks ork) is still not added
  to 🪙 (its transcript counts it) but gets its ledger line with `"transcript": true` (`telemetry.noted`),
  so *By purpose* sees it. `roads.run_agent` puts `ORKCRAFT_PURPOSE` in such a run's env, and the
  session hook records it in `sessions.jsonl`; `Telemetry.refresh` sums transcript spend by that purpose.
- Who says what: the steward's tasks map to a purpose in `steward.PURPOSE` (`purpose_of`; the Town
  Hall's `answer` is `chat`), applied by `steward.runner_for` and `Worker.steward_runner` through
  `builders.tagged`, and by the Barracks steward. The Fast Path is `build`, the Elders `answer`, the
  Building and Town retros `retro`, the Lookout and the Watchtower's agent feed and Catapult's carrier
  `look`, a Review board's discussion `review`, the Wiki's ingest `ingest` and its lint and spot-check
  `check`. The building comes from `ORKCRAFT_ORC` when a call carries it. Everything else is `work`.
- Not done here: the Spend window's *By purpose* (stage 0b, queue item B04). A call through a path not
  listed above counts as `work`: the first week's numbers will show if a big one hides there.
- Tests: `tests/test_telemetry.py` (the ledger, tags, transcripts, hook, housekeeping, a road agent).
