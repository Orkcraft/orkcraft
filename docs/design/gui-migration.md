# Design — toward a GUI: one core, two faces

Orkcraft draws everything as terminal cells: one monospace font, one grid. A town where a
building's name, its status lines and its code each wear their own font needs a real GUI. The
town itself must change, not just a full-screen view. Rewriting ~20k lines of Textual at once
would stop all other work, so the move goes in stages. The TUI keeps working the whole way.

| stage | what | state |
|---|---|---|
| 0 | where the core lives | decided (§1) |
| 1 | the logic apart from the interface | the core, the road engine and the first workers stand; what is left is listed in §2 |
| 2 | no file everybody has to touch | done for `app.py` (§3) |
| 3 | the design system and the building's UI as JSON | done: tokens, the document, three contracts, `D` (§4) |
| 4 | Office in the GUI: plain widgets, the same town graph | paused |
| 5 | Camp in the GUI: tiles and sprites in the spirit of Warcraft II | paused |

## 1. Stage 0 — where the core lives

**One owner per project.** Only one process runs agents, lays roads, keeps the budget, saves the
Town Scroll and answers 🛑 Halt All. Without one owner, two faces open on the same project would
start the same ork twice and both write `.orkcraft/`.

- **Now: in process.** `orkcraft/core/` is a package with no Textual and no Rich. The TUI builds a
  `core.Town`, subscribes to its bus and calls its services.
- **Later: a daemon.** The same `Town` runs headless behind a local socket, and the TUI and the GUI
  become its clients. What crosses the boundary is already data: commands are plain method calls
  with JSON-able arguments, and events on the bus carry JSON-able payloads (`core/bus.py`). Putting
  a socket between them later changes no service.
- **Not chosen:** two full apps over the same files. Locks on every file would be needed, and Halt
  All would only stop half of what runs.

The GUI stack is chosen at stage 4: a web face (HTML/CSS/SVG in `pywebview` or a browser) over
the core. Fonts, roads as SVG paths, sprites and `xterm.js` for the agents' terminals all come
with it. Nothing in stages 1–3 depends on that choice.

## 2. Stage 1 — the logic apart from the interface

```
orkcraft/
  core/      the town without a face: state, services, bus, runner seams     (no textual, no rich)
  realm/     the domain: roads, orks, buildings, retros, checkpoints         (no textual, no rich)
  sources/   sessions, telemetry, quota                                      (no textual)
  design/    tokens and the building UI spec (stage 3)                       (no textual, no rich)
  tui/       the Textual face: the app's parts, by domain
  screens/ widgets/ wm/   the Textual face's views (move under tui/ when touched anyway)
```

`tests/test_architecture.py` enforces it: `core/`, `realm/` and `design/` import neither
`textual` nor `rich`.

What the core owns:

- **`core.Town`**: the project (repo root, config, demo), the Town Scroll, the custom building
  specs, the building registry's ids, the telemetry snapshot, and the bus. It saves through a
  hook the face registers (the TUI's desktop records window and hut positions first).
- **Services**, each a module with plain functions or a small class over the `Town`. Roads (lay,
  remove, change the handler, what a source can send), the treasury (spend, limits, HUD texts),
  feedback (👍 / 👎), checkpoints and revert. Quiet hours work (the Elders, the orks'
  self-improvement and probation) and raising a building from a checked spec are services too.
- **The bus** (`core/bus.py`): topics such as `toast`, `roads`, `roster`, `hall`, `spec`, `hud`,
  and what roads carry: `delivered`, `output`, `cart`, `run`, `loot`, and `worker` (a building's
  worker changed its state). A service never shows anything. It publishes, and each face decides
  how to show it.
- **Workers** (`core/workers/`): a building's job without its face, one per building, made by
  `Town.worker(id)` the first time it is asked for. A worker keeps the building's state and does
  its acts (`receive`, `halt`, `status`, `emit`, `save_config`); its view draws that state again
  on `worker` and calls the acts. Slow work runs in the worker's threads and comes back through
  `Town.call`, the hook a face sets to reach its own thread (the TUI's UI thread).
- **Runner seams** (`core/runners.py`): the model calls tests replace (`BUILD_RUNNER`,
  `ELDERS_RUNNER`, …), in one place for every face.

What stays in the face: dialogs and their flow, focus, keys, layout, windows, huts, carts,
terminals. A dialog's *decision* calls a service, and the dialog itself is the face's.

**Moved so far:** `core/town.py` (the state, the machine's settings, save, checkpoint,
chronicle), `core/bus.py`, `core/roads.py`, `core/treasury.py`, `core/buildings.py` (raising a
spec, Z, goals, 👍 / 👎, the retros' and stewards' proposals, the UI document), `core/night.py`
(the Elders, the orks' own changes, probation), `core/roster.py` (the garrisons, the questions,
the deployments), `core/runners.py`, and:

- **The road engine** is the `Town`'s (`town.roads`, built by `core/delivery.py`). A cart
  delivered, a handler's result, a run that ended and a cart on the road are core functions that
  record what happened and publish it; `tui/delivery.py` draws them (the 📥 note, the carts, a
  failed run's mark, the coin, the Loot list). `Town.budget_ok` is the 🪙 hook the face sets.
- **Workers** for 🌊 Lake (`workers/lake.py`: what is shown, the file open in the editor),
  🌾 Task Fields (`workers/fields.py`: the board, its acts and events) and 🗑️ Scroll Dump
  (`workers/scrolls.py`: the librarian, the spot-checks, halt). Their views keep the widgets, the
  keys, the dialogs and the timers; their old names read the worker, so callers did not change.

`tests/test_core.py` runs all of it with no app at all.

**Left for stage 1**, the largest first:

1. **Workers for the other types.** A typed view (`screens/typed/*`) of every other type still
   both draws and does the building's job: `receive` runs or queues work, `halt` stops it, a
   webhook, a Barracks' orks or a Clan Fire's discussion runs in it, `burning` and `orders_alert`
   raise fire. Each gets a worker the way the three above did; a delivery goes to the worker when
   there is one (`delivered` says so), else to the view.
2. **Sessions and terminals**: the War Tent's terminals (pyte) are the face's, but deploying an
   ork, the processes and the roster's view of running sessions are not. Split them into a
   sessions service in the core that keeps the processes, and terminals that draw them (pyte
   today, xterm.js later).
3. **🛑 Halt All through the `Town`.** `Town.halt()` stops the road handlers and every worker,
   but the TUI's Halt All still walks the views and the War Tent itself. Once every type has a
   worker and sessions are a service, Halt All is `town.halt()` plus the face's own terminals.

**How it moves:** one domain at a time, with the whole suite green after each. A service lands in
`core/`, and the TUI's part for that domain calls it instead of doing the work itself. Method
names on `OrkcraftApp` stay, so tests and views that call `app.add_road(...)` keep working.

## 3. Stage 2 — no file everybody has to touch

`app.py` was 3.6k lines with ~215 methods: every feature touched it, and parallel branches
conflicted there. Now:

- `app.py` keeps only the class that composes the parts, its bindings, `compose` and `on_mount`.
- `tui/<domain>.py` holds one domain of the app each: focus, layout, commands, orkspaces,
  sessions, delivery (carts and payloads), roads, recruiting and stewards, the treasury and roster,
  building, night (quiet hours), onboarding, retros. Each is a mixin of `OrkcraftApp`, so
  `self.<method>` calls between them still work.
- **Rule of thumb:** a module over ~600 lines is split by domain before a feature is added to it.
  A new feature goes into its domain's module, or into a new one, never into `app.py`.
- Next in line, when they are touched anyway: `wm/desktop.py`, `screens/onboarding.py`,
  `screens/console.py`.

## 4. Stage 3 — the design system and the building's UI as JSON

See [`docs/design-system.md`](../design-system.md) for the rules (written for people and for the
orks that rebuild buildings). Shipped: `design/tokens.json`, `schemas/building-ui.v1.json`,
contracts for 🌊 Lake, 🌾 Task Fields and 🗑️ Scroll Dump, the document kept per building in the Town
Scroll, `D` 🎨 (the steward redesigns from a wish), and the TUI drawing it (`tui/ui_apply.py`). Next:
a contract for each remaining type as its view is split into named panes. The short version:

- **Tokens, not values.** Font roles (`title`, `body`, `mono`, `status`, `label`), colour roles
  (`ok`, `wait`, `fire`, `muted`, `accent`, the harness colours), spacing steps. Camp and Office
  are two themes over the same roles. The TUI maps a font role to a text style (bold, dim, …),
  and the GUI maps it to a real font.
- **One building, one UI document.** Every building has a UI document (`building-ui.v1`):
  panes of components laid out in rows and columns by share. Each type ships a default in its
  contract (`orkcraft/design/buildings/*.json`), and a building's own document lives in its Town
  Scroll entry (`ui`). A steward that rebuilds a building's UI writes that document, and the
  validator checks it against the contract. A Mason & Artisan custom building keeps its layout in
  its spec's panes.
- **Components are a closed list** (`list`, `table`, `counter`, `markdown`, `editor`, `board`,
  `diff`, `tree`, `terminal`, `chart`, `form`, `log`). Each face renders each component in its
  own way. Nothing in the document is code, a raw colour or a font name.
- **The graph stays simple** (the invariant Office and Camp must keep): one kind of edge, the
  road. No ports or parameters on the canvas. A building shows its name and up to three status
  lines, and all its settings live inside its window. Positions are the person's, never an
  automatic layout.
