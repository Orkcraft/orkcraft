# Design — roads, ork handlers and stewards

Status: design notes, written 2026-09-30 (the model below is implemented). Builds on garrisons, rally
points, chronicles, the 🪙 / 🪵 telemetry and the Mason & Artisan builders.

## 1. The model

A building has two kinds of orks:

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

## 5a. Routes, return roads and cart travel (implemented)

- **Routes.** A Signpost's rules or a Clan Fire that routes (`routes`, its steward's `ROUTE: <name>`)
  give a cart a route (`Payload.route`; a Signpost's cart is also titled by it). A road with
  `{"route": [...]}` takes only those; the GUI shows such a road's label as a sign on it, always.
- **Return roads.** `{"returns": true}`: the cart goes only to the building its `ref` names, which
  updates the work it sent out instead of starting new work — so a return road is not counted as a
  loop (docs/design/fields-board.md §5a).
- **Cart travel.** The road engine can hold a plain road's cart for the time the face asks
  (`Town.cart_travel_s`; the GUI reads `ORKCRAFT_CART_TRAVEL_S`, default 0) before it arrives, so a
  person sees it on the road before its building acts — `tools/landing_flow.py` films with it. The
  GUI draws every cart moving from gate to gate (`js/town.js`), a filtered one turning back.

## 5b. Roads in words (implemented)

Few people think in events, so a road starts with what the person wants: *"listen to unread messages
and make to-dos of them"*. The receiver's steward reads it (`realm/road_planner.py`, one model call)
and offers up to three roads; the person picks one, the event list waits folded below.

- **Two ways in.** *➕ Listen* on the receiver knows only the target: the steward picks the source among
  the buildings in view. An arrow drawn from one building's + to another knows both: it picks the event.
  The TUI's `Y` → a source → *💬 Say it in words…* is the second.
- **What it sees.** The contracts, never the town's content: what the receiver takes
  (`catalog.takes`), and per building what a plain road from it carries and what a rule's handler can
  take (`core/roads.contract`).
- **What it may offer.** A plain road on an event the source declares, with a `match` filter at the
  source when only some carts should go ("unread", "from my boss"); or a road with a **rule**, which
  goes on to the Recruiter and the Council as *Listen with a prompt* does. Events are never invented:
  a filter or a rule narrows what a type sends. When nothing fits it says what is missing.
- **Checked.** Every option is checked against the sources' events, the filter schema and a copy of
  the scroll (`subscribe`: duplicates, loops, limits); what fails is dropped, and when nothing holds the
  steward gets the problems back once more.
- **On the steward's model.** The planner and the Recruiter think on the receiver's steward's tool, at
  its tier for *Roads* (`steward.USES`). Next: the steward carries out the rules itself
  ([steward-listens.md](steward-listens.md)).

## 5c. A meeting and its brief (implemented)

- **A time on a route.** A Clan Fire that routes may also have its steward name a time (`WHEN: tomorrow
  11:00, 30 min`, realm/team.py): the routed document then begins with a `When:` line.
- **A cart that names a time is an event.** A War Drum that gets a cart with a `When:` line (and no
  meeting of its own) adds the event, titled as the cart (`daybook.find_when`); `calendar.event_added`
  goes out as for any new event. With `prepare_new`, a new event asks for its document at once
  (`calendar.event_upcoming`, titled by the meeting, its ref `<drum>:<meeting id>`).
- **The brief comes home by a return road.** A Barracks' `pool.done` keeps the task's ref, so a return
  road back to the War Drum (`{"returns": true}`) carries the brief to that meeting: its document (the
  report without the `**Task** — who` line) and the first link it gives. The event wears a `📄 doc` pill
  on the closed card and in the Command Card. The `[meet:<id>]` tag stays in the cart's text only, so
  titles read clean; a cart without the ref (past a Signpost) still finds the meeting by the tag.
- **Notes read first.** A Barracks with `notes: ["<scroll dump>"]` hands a new task to that Scroll Dump
  directly (no road back, so no loop); it sends the task on as `knowledge.chunks` — the wiki's map and
  the pages that share the most words with the task (`wiki.relevant`) — and the ork starts when that
  cart arrives. The Scroll Dump's card says what it read and for which task for a while.
- **Signs.** A road named in words (a kebab-case label, `new-meeting`, `prepare-a-brief`) wears its name
  as a sign, as a road that waits for routes does. A `pool.done` cart reads as what came of the task (the
  report's first line), not the task.
- A War Drum's `beats: ["meeting"]` keeps its timeline to the meetings (no scheduled runs, no limits).
- The demo's Meetings (F6, `demo/meetings.py`) plays it: Inbox → Triage (a risk analyst, a tone reader, a
  productivity pulse) → "new meeting" → Calendar → "prepare a brief" → Agents at work, which read Notes
  first ("with the notes") → "brief ready" to Results and "the brief" back to the Calendar.
  `tools/landing_flow.py --flow meeting` films it.

## 6. Open for later

- `on_stream` roads and which receiver consumes a raw stream.
- Script runtime isolation on macOS (`sandbox-exec` is unmaintained): operator review stays the
  main safeguard, the restricted environment is defence in depth.
- Warder guards Claude Code sessions only; scripts run by orkcraft need their own limits.
