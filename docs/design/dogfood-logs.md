# Design — logs for real use: what is kept, what to switch on, what is missing

Status: written 2026-10-12. The owner starts building a game with Orkcraft and wants every insight from real use:
technical logs, product analytics, and logs to analyse the AI and its orkestration. §1 is what the code keeps today
(checked in the code, not assumed); §2 is what to switch on before starting; §3 is what is missing, with priorities.

## 1. What is kept today

### 1a. Technical

| what | where | notes |
|---|---|---|
| crash reports: uncaught errors, broken commands, the clock's failures, the window's own errors (`js/crashes.js`) | `~/.orkcraft/crashes/` (full traceback, always); Sentry through the proxy when usage stats are on | `core/crashes.py`, [crash-reports.md](../crash-reports.md). A Sentry session per run: ok, exited, crashed, abnormal |
| an AI tool that failed | a toast with Retry and Details (`gui/failures.py`) | **not kept in a file** (§3) |
| a building's mutations | `.orkcraft/history/buildings/<id>.events.jsonl` (`realm/chronicles.py`) | settings changed, built, demolished; short fields only |
| the Warder's denies and asks | `.orkcraft/warder.jsonl` | |

### 1b. Product analytics

| what | where | notes |
|---|---|---|
| 13 events: app opened and closed, building built and demolished, road laid, session opened, deed, stage, autonomy set, Stop all, **install started, install step, install finished** | Amplitude through the proxy (`core/usage.py`, [usage-stats.md](../usage-stats.md)) | opt-in; counts as buckets; nothing in the demo. The install funnel exists, but only for the `sh` installer (§3) |

### 1c. The AI and its orkestration

| what | where | notes |
|---|---|---|
| **every model call in full**: prompt, whole output, errors, the tool's own trail (Claude Code's transcript with its thinking and tool calls; agy's brain folder), seconds, exit code, cost, tokens | `.orkcraft/logs/<day>/<building>/calls.jsonl` and a gzipped file per call (`realm/call_log.py`) | **a day is cleared the next morning** unless asked for or 👎'd that day, then kept 14 days (`realm/day_log.py`), unless the switch of §2 is on |
| spend per call: building, purpose, model, tokens, $ | `.orkcraft/spend/calls.jsonl` (`sources/telemetry.py`) | |
| the CLI sessions Orkcraft started, with their transcript paths | `.orkcraft/sessions.jsonl` (`hooks/session.py`) | |
| the Agent pool steward's decisions: hires, reworks, waits | `decisions.jsonl` in the analytics zip | |
| the 👎 with what the person said | `dislikes.jsonl` in the analytics zip (`.orkcraft/feedback`) | |
| the Council's reviews, the Elders' advice, the night's improvements | `.orkcraft/council/reviews.jsonl`, `elders.jsonl`, `improve.jsonl`, `days/` | |
| per-building runs: the Transformer's, a Router's routes, a listener's signals, the Review gate's stored carts, the Publisher's shots | `.orkcraft/<kind>/<id>/runs.jsonl` and the like | each building its own file |
| **all of it for a period, as one zip** | Town settings → analytics download (`realm/analytics.py`, `/api/analytics`): README, `summary.json`, per day and building | made for handing to a person or an agent to analyse |

**In short:** the AI's side is kept very well, the technical side well, product analytics thinly (13 events, as
buckets, made for strangers' privacy, not for the owner's own insight).

## 2. Switch on before starting the game (no code)

1. **Town settings → keep logs for analysis** (`logs_for_analysis`, off by default). Without it every day's model
   calls are cleared the next morning, and the game's first weeks are lost.
2. **Usage stats and crash reports: yes** (`orkcraft usage on`), so the owner's own runs reach Amplitude and Sentry
   like a tester's would.
3. **The game's repository ignores `.orkcraft/`** in its `.gitignore`: the logs hold whole prompts and outputs, the
   game's code among them. Check before the first commit.
4. **Use 👎 with a note as the insight log.** Every "this was wrong / slow / confusing" said on the building or the
   output it is about lands in `dislikes.jsonl` with its day's calls kept. No new feature for notes: the 👎 is it.
   What has no building to land on goes into a plain diary file.
5. **Once a week, download the analytics zip** and hand it to an agent with the question of that week.

## 3. What is missing

| gap | why it matters | priority |
|---|---|---|
| **A local, full-detail product event log.** Amplitude gets 13 events as buckets, by design; the owner's own use needs every event, exact, on the machine only (`.orkcraft/usage/events.jsonl`), whatever the opt-in answer, never sent | the P0 checks of the console cannot be measured without it: how long a ❓ waits for its answer ([ork-console.md](ork-console.md) §13), whether Work is opened ([lighter-buildings.md](lighter-buildings.md) §4) | **P0** |
| **The events the P0 checks need:** a question asked and answered (with the wait), the console opened and at what depth, a Work panel opened (which type), a wait seen and skipped (Start now, Run anyway, Approve), a building set up or left "needs setup" | the same; to the local log in full, to Amplitude as buckets | **P0** |
| **Every wait, with its reason and how long it lasted** ([ork-console.md](ork-console.md) §19) | the owner's daily question "why is it not moving"; today only the Agent pool steward's waits are in `decisions.jsonl` | **P0**, with §19 |
| **An AI tool's failures kept in a file**, not only a toast | today a failed run is seen once and gone; the analysis cannot count them by tool and cause | **P1** |
| **One id per cart across its stops** (a trace): the buildings, sessions and waits it went through | analysing the orkestration end to end; today each building keeps its own file, and joining them is guesswork. Also the base of a cart's price ([ork-console.md](ork-console.md) §17) | **P1** |
| **Assumptions an ork made, structured** ([ork-console.md](ork-console.md) §4) | the log check of §1a is done by reading by hand until the ask channel marks them | comes with the ask channel, **P0** stage 1 |
| **The install funnel for Homebrew and pipx**, not only the `sh` installer | the launch plan's week 2 measures installs; most people will use brew or pipx | **P1**, before the testers |

**Not needed:** a separate notes feature (the 👎 with a note does it), session recording of the window (the testers'
own screen recordings do it), a dashboard of the logs inside Orkcraft (the analytics zip and an agent do it).
