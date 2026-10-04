# Design — retros and building goals

Status: design notes, written 2026-10-03; stages 1–4 of §6 are implemented, stage 5 (calibration) is not.
Builds on the self-improvement of `realm/optimize.py` (daily), `realm/weekly.py` (weekly),
`realm/evolution.py` (the orks' own changes), the ledger of `realm/metrics.py`, the quota readers
(`sources/limits.py`) and the 👍 / 👎 of `realm/feedback.py`.

## 1. Why

The self-improvement had one direction: **cheaper**. The daily proposal picked the building with the
most tokens today; the Council could only shrink a prompt, turn an agent into a chain, or a steward
into a script. Two gaps:

- **Absolute tokens say little.** 50k tokens are nothing on a quiet day with a fresh quota and a lot
  when the 5-hour window is nearly spent. What matters is a building's *share* of the camp's spend and
  how much of the *remaining limit* it is going to eat before the quota resets.
- **No way to ask for better.** A cheap building the operator 👎-s had nowhere to go: every allowed
  change makes it cheaper still. And there is little to judge quality by — 👍 / 👎 are pressed rarely.

So: a share-and-pressure measure instead of raw tokens, a **goal** per building (🪙 thrift · ⚖️ balance ·
💎 quality) that the steward and the Council improve towards, and a short **survey** at the weekly
retro that collects the ratings the goals need. The two reviews get names that say what they are:

| Before | Now | When |
|---|---|---|
| Self-improvement (daily proposal) | 🔧 **Building retro** | daily, `optimize_at` (06:20) — one building |
| Weekly self-audit | 🗓 **Town retro** | weekly, `weekly_at` (Sunday 05:00) — the whole camp |

Only the names change in the UI and the docs; modules, settings keys (`optimize_at`, `weekly_at`,
`weekly_model`), files under `.orkcraft/optimize/` and `.orkcraft/weekly/` and checkpoint kinds
(`auto-improve`, `weekly`) stay as they are, so nothing a camp already has is lost.

## 2. Share and pressure (`realm/pressure.py`)

Two numbers per building, from the ledger (`.orkcraft/ledger.jsonl`) and the latest quota read:

```
share     = tokens of the building in the window / tokens of the whole camp in the window
rate      = tokens of the building in the window / the window's length            (tokens per hour)
forecast  = rate × hours until the tightest quota resets
pressure  = forecast / what the camp can still spend before that reset
```

- **The window** is the last 24 h (the daily retro looks at today; a day is long enough for a building
  on a timer to show its rhythm).
- **What the camp can still spend** needs tokens, but subscription quotas come as `% used`. Until the
  calibration of stage 5 exists, it is estimated from the camp's own spend: the tokens of the window
  divided by the quota share used in it is the camp's tokens per 100 %; times the remaining fraction is
  what is left. When nothing is known (no quota read, an API key, a fresh camp) there is no pressure,
  only share.
- **The tightest quota** is the enabled subscription limit with the least remaining (the same one the
  HUD corner shows).

```python
pressure.measure(repo_root, limits, now) -> Camp
Camp.buildings: {id: Use(tokens, share, rate, forecast, pressure)}
Camp.tight: bool          # the camp's own forecast passes the remaining limit before the reset
```

`Camp.tight` is the camp-wide signal: when the whole camp, at its current rate, would run out before
the reset, thrift wins over quality (§3).

## 3. The goal of a building

A three-stop slider, like the autonomy slider: **🪙 Thrift · ⚖️ Balance · 💎 Quality**. Stored in the
Town Scroll as `buildings[].goal`: `"thrift" | "balance" | "quality"`; missing means ⚖️ Balance.
Set from the Info panel: the goal button beside 👍 / 👎 cycles it.

| | 🪙 Thrift | ⚖️ Balance | 💎 Quality |
|---|---|---|---|
| Picked by the Building retro when | its share or pressure leads, and it has no 👍 since its last change | as thrift, or it got a 👎 today | it got a 👎 or a failed run in the last 7 days, or it was never rated |
| The Council may | shrink · chain · script | shrink · chain · script · enrich | enrich (and shrink, when it keeps the liked results) |
| Its prompt says | spend fewer tokens, keep what was liked | fix what was disliked without spending more | make the results better; spending more is fine within the ceiling |

- **enrich** — a new action: the part's prompt gets better: the liked results as examples, the
  disliked ones as what to avoid, a clearer instruction. The check: the new prompt is longer than the
  old one (else it is a shrink) and at most `ENRICH` (2×) as long — the **ceiling** that keeps 💎 from
  eating the quota.
- **The order** of the Building retro (`optimize.leader`):
  1. 💎 buildings the operator 👎-d this week, the most disliked first — the operator asked for
     quality and did not get it;
  2. 🪙 / ⚖️ buildings by pressure (share when there is no pressure), from `MIN_SHARE` (10 %) of the
     camp up — the first that passes its rule; a liked one passes the turn to the next;
  3. 💎 buildings with a failed run this week, or never rated, the most failing first.
  Nothing due → no proposal that day.
- **A tight camp overrides 💎.** When `Camp.tight`, the three heaviest 💎 buildings are treated as ⚖️
  (balance: any action, a shrink included). The Building retro's notice says so: `quality→balance
  (the limit is tight)`.
- **The Town retro** sees each building's goal and may propose `enrich` too, for ⚖️ and 💎 buildings
  only; its check is the same.
- **Autonomy**: `enrich` is applied by the orks themselves only at ⛓️‍💥 Free orks (level 3) — it spends
  more, so it is a bigger step than a shrink. Probation is the same 24 h: a 👎 or more failed runs take
  it back.

## 4. The Town retro survey (`realm/retro.py`)

When the Town retro opens and **the operator rated nothing in the last 7 days** (no 👍, no 👎 on any
building), it first shows up to **4** past results to rate — in all, not per building:

```
┌ 🗓 Town retro — four results from the week, were they good? ─────────────┐
│ 1/4  🏭 Brief · Tue 09:12 · changed by the orks Mon (on probation)        │
│   in   {"title": "release 0.4", "commits": 12}                            │
│   out  ### Release brief — 12 commits, 2 fixes, …                         │
│                         [ 👍 Good ]  [ 👎 Bad ]  [ Skip ]                  │
└───────────────────────────────────────────────────────────────────────────┘
```

- **Which results**: the most useful to know about, in this order, one per building:
  1. a building the orks or the operator changed this week (an answer confirms or questions the change);
  2. a 💎 building with no rating this week;
  3. a run that failed or was escalated (exit 3 / 4, an error);
  4. the building with the highest pressure — the next Building retro's likely candidate.
- **The card**: the building, when, why it was picked, and the input → output cut short (as in the
  Council's run logs, 240 characters each).
- **👍** keeps that output as a reference (`references.jsonl`); **👎** asks the same question as `F` —
  broken inputs or its own logic — and writes an incident with the cascade. **Skip** records nothing.
- When the operator did rate something this week, the survey is skipped; the report follows at once.
- The Building retro never asks: it runs in the morning and leaves at most one proposal.

## 5. What is not changing

- Nothing is applied without the safeguards: checks, the Council, a checkpoint, probation.
- The weekly report's items and the daily proposal's modal stay as they were, with the new titles.
- Billing by API: no limits, so no pressure — share only.

## 6. Stages

1. `realm/pressure.py`: share and pressure; `optimize.leader()` picks by them; the Council's prompt shows
   the share and the forecast instead of a bare token count.
2. Names: 🔧 Building retro, 🗓 Town retro — F10 menu, notifications, modals, Town Hall, reference.
3. `realm/retro.py` + the survey modal before the Town retro report.
4. The goal: `BuildingSpec.goal`, the schema, the Info-panel button, the leader by goal, `enrich`,
   the 💎→⚖️ override, `evolution.LEVEL_FOR["enrich"] = 3`.
5. Later: calibration of tokens per 1 % of each quota from the sampled limits, for a real
   forecast instead of the estimate of §2.
