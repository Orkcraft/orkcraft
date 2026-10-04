# Design — roads, ork handlers and stewards

Status: design notes, written 2026-09-30 (the model below is implemented). Builds on garrisons, rally
points, chronicles, the 🪙 / 🪵 telemetry and the Mason & Artisan builders.

## 1. The model

A building has two kinds of orcs:

- **Steward** (top, in the window frame badge) — watches how well the building is used and how it
  could be automated or improved. Usually a *hybrid*: a script collects metrics on a schedule
  (free), and an agent is woken only when the script finds a reason (a metric moved, the window has
  gone unused, a road's agent keeps doing the same thing). Its main output is proposals: a new
  road, a new ork, a spec change, or demoting an agent to a chain / script.
- **Handlers** (bottom, the Clan Roster in Building state) — each works on one or more **incoming
  roads** of this building.

Orks sit on **incoming** roads, not outgoing ones: the receiver knows what to do with the data, a
source never needs to know its consumers (subscription, fan-out for free), and processing cost is
spent only where there is a consumer and is charged to that building's 🪙.

## 2. Roads

A road = source building + event (`on_selection_change`, `on_task_completed`, later `on_stream`)
+ optional **source filter** (only failing tests, no personal nodes — also the privacy boundary of
what leaves a building) + an optional handler at the receiver.

- **Plain road** — no handler; code shows / copies the payload (today's Scrying Spire preview).
  Free and instant; the right choice for chatty events like selection changes.
- **Road with a handler** — for rarer, heavier events.
- **Gates** — every road has a visible exit gate on the source frame and an entry gate on the
  receiver frame (a glyph on the border, on the side facing the other building, in the handler's
  colour). Gates stay clickable even when the road itself is hidden behind windows; when windows
  move, the road is re-routed gate to gate.
- `Y` flips meaning: on a selected building it **subscribes** it to another building's output
  (pick the source, then the handler or "none").

### Visibility — three levels

| State | Roads |
|---|---|
| nothing selected | faint, only in the gaps between windows (on the biome: grass, snow …) |
| building selected | its incoming and outgoing roads more visible, gates highlighted |
| road selected (click a road or a gate, or pick its handler) | drawn **over** the windows, bright, labelled `🧌 Scribe · ⚒️ Forge → 🔮 Spire`; the console shows the road card (events, filter, handler) |

Routing: orthogonal paths between gates around windows (A* on the terminal cell grid, recomputed
only when the layout changes), drawn with the biome's glyphs.

## 3. Handlers

### Kinds — tried in this order when an ork is created from a prompt

| Kind | What it is | Safety |
|---|---|---|
| `chain` | declarative pipeline of whitelisted ops: filter, pick fields, regex extract, count, group, Markdown template, join a batch | data, not code — validated like a building spec; can run at once |
| `script` | a small Python script written by Claude | code: enabled only after the operator reviews it; runs with JSON in/out on stdin/stdout, empty temp dir, stripped env, time / memory limits, no writes to the repo; kept in the repository |
| `agent` | Claude / agy session(s) | judgment; always within the 🪙 limit |
| `hybrid` | a script with escalation to an agent | the steward's usual shape |

Claude decides the kind when the ork is created and explains in the preview why a cheaper kind
was not enough (as Mason does). **Scripts are in the spec from day one; their runtime comes later**
(until then the UI says so instead of pretending).

**Demotion**: the steward sees an agent doing the same thing over and over (its Unit Chronicles)
and proposes a chain or script, shown with input → expected-output examples from past runs; the
new version is replayed on those examples before it replaces the agent.

### Several roads, rerun on new data

A handler can listen to several roads. It keeps the **latest payload of every road** and is
**re-run on every new event** with that whole snapshot (roads that never fired are empty) — like
a spreadsheet cell recomputing. No join windows, no required / optional roads.

- `chain` / `script`: rerun immediately — they are cheap.
- `agent` / `hybrid`: a **quiet period** (e.g. 30 s) coalesces a burst into one run, and a new
  event arriving during a run **restarts** it (the stale run is interrupted); the 🪙 of interrupted
  runs is still counted.

### Harness scheme

`harness` is a list of steps `role → harness`, not a single string — e.g. `[write: agy,
review: claude]` (a plan → write → review division of labour), `[plan: claude, write: agy, review:
claude]`, other agents later, or a reference to an existing multi-agent system pipeline
(`product-studio/pipelines/…`), making the ork the entry point of that system.

## 4. Visual language

- Icon = kind: 🗿 totem — script / chain (mechanical, no head); 🧌 ork — agent; 🗿🧌 — hybrid.
- Colour + letter = harness: Claude amber `C`, agy cyan `A`; schemes read as `A→C`, `C→A→C`
  (long ones: first and last harness + step count).
- Handlers appear under their building in the roster, each with its roads; the steward stays in
  the frame badge.

## 4a. Carts and coins

- **Carts** travel along roads and are **real events only** — one cart = one payload or one
  coalesced batch. Colour = cargo status: normal · filtered at the source (the cart turns back) ·
  handler error (red, stops at the entry gate). A **jam** is carts piling up at the entry gate
  while the handler is busy or restarting — visible before any metric, and a signal for the
  steward. Clicking a cart shows what it carries (node, file, report).
- Visibility: off · selected building (**default**) · all roads. Motion pulls attention (the
  spec's ambient-awareness principle), so at high rates a counter `🛒×N` at the gate replaces the
  stream.
- **Coins** are a separate signal, not cargo: a short 🪙 flash at a building when its agent spends
  budget on a run — where the money burns, next to the HUD's 🪙.
- Rendering: carts move along the road's cell path at 6–10 fps and only while something is moving
  on a visible road; no redraws when idle.

## 5. Schema (Town Scroll v3)

Implemented in `schemas/town-scroll.v3.json`, `orkcraft/scroll.py`. One change
from the sketch below: roads are stored on the **receiving building** (`building.roads`, each
with `handler: <handler id> | null`), not inside the handler — plain roads need a home too, and
one list keeps a single source of truth. A handler's roads are `building.roads_of(handler_id)`.

The first sketch, for reference:

```jsonc
"garrison": {
  "steward": {"id": "smith", "kind": "hybrid", "harness": [{"role": "review", "harness": "claude"}],
              "prompt": "…", "schedule": "daily 05:00"},
  "handlers": [{
    "id": "scribe", "kind": "chain", "harness": [],
    "roads": [{"from": "forge", "event": "on_task_completed", "filter": {"status": "failed"}}],
    "run": {"quiet_s": 0, "restart_on_new": true},
    "chain": [{"op": "pick", "fields": ["id", "title"]}, {"op": "template", "md": "…"}]
  }]
}
```

Migration from v2: the building-level `rally_point` becomes a plain road subscribed by its target;
today's garrison lead becomes the steward; other members become agent handlers without roads.

## 6. Open for later

- `on_stream` roads and which receiver consumes a raw stream.
- Script runtime isolation on macOS (`sandbox-exec` is unmaintained): operator review stays the
  main safeguard, the restricted environment is defence in depth.
- Warder guards Claude Code sessions only; scripts run by orkcraft need their own limits.
