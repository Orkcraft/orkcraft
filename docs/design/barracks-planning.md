# Design — the Barracks plans its work; three levels of autonomy

Status: design notes, written 2026-10-06; §2 is implemented, the rest is under way. Builds on the Barracks
(`realm/barracks.py`, `core/workers/barracks.py`), the tiers (`realm/tiers.py`), the building goals
(docs/design/retros-and-goals.md §3) and the autonomy slider (`autonomy.py`, docs/design/onboarding.md §6).

## 1. Why

Today the foreman hands every task, whole, to one ork. It hires by its rules, but the operator also
has a ✚ Hire button, and people read that as "I must hire before anything runs". The model is picked
by the provider's record and "docs or code", never by how hard the task is. A big task runs on one
ork for a long time; a one-line fix may run on an elder.

The change: **the steward plans**. It judges the task; a simple one goes straight to a light model, a
hard one becomes a graph of subtasks, each with the tier it needs and an ork (or a persona) fit for it.
The steward reviews each part and the whole, and sends work back. Nobody hires by hand any more.

Deciding more on their own needs a clearer autonomy model, so the slider shrinks to three levels (§2).

## 2. Autonomy: three levels

| | ⛓️ Chains | ⏳ Timer | ⛓️‍💥 Free orks |
|---|---|---|---|
| A decision (an agent's question, a new persona, a self-improvement) | waits for the operator 🔥 | waits `autonomy_wait` minutes (default 7, 5–10), then the orks decide | the orks decide at once; the operator sees the list afterwards |
| In quiet hours | waits for the operator | no wait: nobody is there to answer | at once |
| The Elders | advise; the operator follows with one key | answer when the timer runs out | answer at once |
| Self-improvement (`evolution.py`, still in quiet hours only) | proposals wait for a click | only what makes a building cheaper or simpler (shrink, chain, demote, run policy, filter) | also what spends more or adds: script, enrich, new road, setting, building |
| The agents' own permissions (📋 guide) | unchanged | today's 🧭 Routine block | today's ⛓️‍💥 Free block |

The same at every level, never relaxed by a timer: what the Warder's rules block waits for the
operator; removing a road or a building is never done by the orks; only a one-time yes is ever sent
(never "always"); every change passes the Council, gets a checkpoint (Z takes it back) and 24 h on
probation.

Silence never makes the camp spend more: that is why ⏳ applies only the cheaper half of the changes.

**Stored** as a word, `autonomy: "chains" | "timer" | "free"` in `~/.config/orkcraft/settings.json`.
An old number still loads, never bolder than it was: 0 Ask me and 1 Morning advice → ⛓️ Chains,
2 Routine → ⏳ Timer, 3 Free orks → ⛓️‍💥 Free orks. A new camp starts at ⏳ Timer.

Touches: `autonomy.py` (levels, `advises` / `answers` become `waits(level, quiet) → minutes | None`),
`settings.py` (the word and the old numbers), `core/night.py` and `realm/elders.py` (the Elders work by
day too, after the timer), `realm/evolution.py` (`LEVEL_FOR` → cheaper at ⏳, the rest at ⛓️‍💥),
`screens/autonomy.py`, the onboarding step, `gui/host.py`, the tests.

## 3. The goal of the steward

A steward has no goal of its own: it works towards its building's goal (`buildings[].goal`,
🪙 thrift · ⚖️ balance · 💎 quality, missing → balance). In the Barracks the goal moves the defaults:

| | 🪙 Thrift | ⚖️ Balance | 💎 Quality |
|---|---|---|---|
| A simple task runs on | laborer | laborer | warrior |
| A subtask's tier | the plan's, one lower (laborer at least) | the plan's | the plan's, one higher (elder at most) |
| Parallel subtasks at most | 2 | `max_orcs` | `max_orcs` |
| A subtask's review | the tests only | the tests + a warrior read | the tests + a warrior read |
| The final review | warrior | elder | elder |

The plan itself is always made by an elder: a wrong plan costs more than everything after it. The
Building retro may propose changes to the steward's planning orders and to its personas' prompts
(shrink / enrich), as for any other part, within its goal's actions.

## 4. The flow

```
task ─▶ triage ─┬─ simple ─▶ a light ork (warm session if related) ─▶ tests (+ review) ─▶ PR
                └─ hard ───▶ plan (graph) ─▶ subtasks in parallel ─▶ each reviewed ─▶ merged
                                                                     into the task's branch
                                                                     ─▶ final review ─▶ one PR
```

### 4.1 Triage: rules first, then the steward

Rules decide when they are sure (free, instant): a follow-up of a ticket, a short text naming one
file, a docs typo → **simple**; a long brief with several tickets, sections or "and then" steps →
**hard**. Otherwise one elder call of the steward, which answers either `SIMPLE` or a plan. The
steward's planning orders are a part of the building like its other orders, so a retro can tune them.

### 4.2 The plan

The steward answers with a small JSON (untrusted text, checked by code):

```json
{"subtasks": [
  {"id": "api", "title": "…", "brief": "…", "tier": "warrior", "persona": "backend",
   "touches": ["orkcraft/api/"], "after": [], "cheaper_ok": false},
  {"id": "docs", "title": "…", "brief": "…", "tier": "laborer", "persona": "docs-writer",
   "touches": ["docs/"], "after": ["api"], "cheaper_ok": true}
]}
```

The code checks it: ids are unique, `after` names only known ids and makes no cycle, at most
`MAX_SUBTASKS` (6), every tier is a tier. A plan that fails goes back to the steward once with the
errors; after that the task runs whole, as a simple one on a warrior, and the decision says why.

**`touches`** keeps parallel work from colliding: two subtasks whose `touches` overlap never run at
the same time, even when the plan draws them in parallel — the later one waits as if it were `after`
the first.

### 4.3 Personas

A persona is a template, an ork an instance:

- **persona** — a role: a name, a short system prompt (what it knows, how it works), the tier it
  prefers. Kept in `.orkcraft/pool/<id>/personas/<name>.md` (front matter + prompt), one per building.
- **ork** — a running agent: a harness, a model, a worktree, a session, its history. An ork is hired
  *as* a persona and keeps it.

The steward names a persona per subtask. A persona from the cache is used as it is. A new one is
written by the steward and goes through the autonomy level (§2): ⛓️ waits for the operator (🔥 on
the steward), ⏳ waits the timer, ⛓️‍💥 is used at once. While it waits, only its subtask waits; the rest
of the graph runs. A simple task needs no persona.

### 4.4 Which ork, which session

As today, by tickets and shared words (`Foreman.affinity`), now among the orks of the right persona
and tier: an idle ork of that persona whose work is related resumes its own session (♻ warm); an
unrelated one starts fresh; none idle and room in the pool → hire one as that persona; else wait.
A simple task: any idle light ork, the related one first — the context is taken into account even
without a persona.

### 4.5 Branches and assembly

The task keeps its branch `pool/<building>/<task>`. Each subtask gets
`pool/<building>/<task>--<subtask>`, cut from the task's branch as it is when the subtask starts —
so a subtask that is `after` another starts from the merged work it depends on. An accepted subtask
is merged into the task's branch by the steward (in its own worktree). A conflict goes to the steward:
it resolves it itself (it knows the intent best), or sends the subtask back with the conflict as its
rework notes. One pull request, for the whole task, after the final review.

### 4.6 Reviews and rework

- **each subtask**: its tests, then (by the goal, §3) a warrior read against the subtask's brief →
  `ACCEPT` / `REWORK` → back to the same ork.
- **the whole**: once every subtask is merged, the steward reads the task's diff against the
  *original* request and the plan → `ACCEPT` (push, PR) or `REWORK: <subtask>: …` (that subtask
  goes back) — or a new subtask when something is missing.
- **escalation**: a subtask that fails (tests red, or a `REWORK`) goes up one tier on its next try:
  laborer → warrior → elder. Every try counts against `max_reworks`; past it → 🔥 for the operator.

The steward keeps the intent: each planned task has a steward session of its own (planning, its
answers to questions, the final review). When that session is rolled over, the next one gets the
original request and the plan verbatim — never a retelling.

### 4.7 The budget

The plan has to fit `max_orcs` and what is left of `budget_usd` (estimated from the record of each
tier in `stats.json`). When it does not, it is trimmed, never silently cut:

1. fewer at a time — the graph runs with less parallelism (same spend, longer);
2. a lower tier where the steward marked `cheaper_ok`;
3. only then the steward is asked to merge subtasks.

Every trim lands in `decisions.jsonl` with its reason.

## 5. What goes away

✚ Hire (`hire_by_hand`) in the TUI (`screens/typed/pool_view.py`) and the GUI (`gui/views/barracks.py`)
and its tests: the steward hires. `max_orcs`, `providers` and `budget_usd` stay as the limits it
works within.

## 6. Stages

1. **Autonomy in three levels** (§2) — its own change; the personas need it.
2. **No hand hiring; triage; simple tasks to a light tier** with the goal's defaults (§3, §4.1, §5).
3. **The plan and the graph**: subtasks, `touches`, branches and assembly, reviews (§4.2, §4.5, §4.6).
4. **Personas** and their approval by autonomy (§4.3, §4.4).
5. **Escalation and the budget trim** (§4.6, §4.7); the steward's planning orders open to the retros.
