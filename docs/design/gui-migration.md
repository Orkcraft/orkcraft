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
| 4 | Office in the GUI: plain widgets, the same town graph | in progress: the stack is chosen and the shell stands (§5) |
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

The GUI stack is chosen in §5: a web face (HTML/CSS/SVG in `pywebview` or a browser) over the
core. Fonts, roads as SVG paths, sprites and `xterm.js` for the agents' terminals all come with it.

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
- **The design system is the source of truth** ([gui-design-system.md](gui-design-system.md),
  `design-system/`). `design/tokens.json` keeps the roles a UI document names and the TUI's hex
  values; its `gui` section maps each role onto the design system (a font role to a type style per
  look, a colour role to a colour token), and `tokens.roles_css()` writes the `.ok-font-*` and
  `.ok-tone-*` classes from it. `tests/test_design.py` checks that every mapped name exists there.
- **The graph stays simple** (the invariant Office and Camp must keep): one kind of edge, the
  road. No ports or parameters on the canvas. A building shows its name and up to three status
  lines, and all its settings live inside its window. Positions are the person's, never an
  automatic layout.

## 5. Stage 4 — Office in the GUI

### Decided

| question | answer |
|---|---|
| where it runs | macOS first (Linux works too); `pip install 'orkcraft[gui]'`, no app bundle: the product is for geeks |
| the window | `pywebview`: the system's own web view (WKWebView on macOS), so no browser ships with it. `orkcraft gui --browser` opens the same page in a tab |
| between the page and the core | one WebSocket on 127.0.0.1: snapshots and toasts out, commands in. It is the daemon's boundary from §1 already |
| the page | Preact + htm + `@preact/signals` as ES modules from `gui/static/vendor/` (~26 KB, no build step, no Node) |
| the first look | Office; Camp is stage 5 |
| the first buildings | the War Map, the HUD, 🌊 Lake, 🌾 Task Fields, 🗑️ Scroll Dump (they have workers and contracts), Orders and toasts; the other types follow their workers (§2, 1) |
| terminals | the sessions service (§2, 2) is built for the GUI: processes and PTYs in the core, `xterm.js` in the page |
| two faces at once | no: one face owns a project at a time until the daemon comes (§1) |
| tokens | `design-system/` is the source of truth (§4) |
| fonts | kept with the design system (`design-system/fonts/`, SIL OFL), never loaded from the network |
| input | the mouse first: every act is a click; keys come later and only as shortcuts |
| Shift | the core decides the look by the hour (`schedule.plain_now`) and the snapshot says it (`look`) |

### How it is built

```
orkcraft/gui/
  host.py     the Town, its clocks (roads, roster, treasury) and the page's commands, on one thread
  state.py    the snapshot: project, HUD, orkspaces, buildings (spot, status lines, garrison, question), roads
  server.py   websockets: the page, /ds/ (the design system), /roles.css, and /ws
  launch.py   `orkcraft gui`: the server on a thread, the window on the main thread (macOS wants it)
  views/      per type with a worker: what its window shows (`detail`), its acts (`ACTS`), its timer
  markdown.py Markdown as HTML, raw HTML off
  static/     index.html (import map), app.js, js/ (link, chrome, town, windows, layout, dialog),
              js/buildings/ (one per type the GUI draws), office.css
```

- **The protocol.** The host sends a whole snapshot (`gui/state.py`) when the town changes, at most
  every 50 ms and only when it differs; the page keeps it in a signal, so only what read a changed
  part draws again. Commands are `{"t": "cmd", "id", "name", "args"}` answered by a `reply`; the host
  keeps a closed list of them (`Host.commands`). Toasts go out as they come. A text that may carry
  emoji comes twice, as it is and `_plain`, for Office.
- **Only its own page drives the town.** The socket takes a random token from the page's address
  and an `Origin` of this server; anything else gets 403.
- **The layout is the design system's.** `office.css` places the components (HUD on top, the War
  Map and the buildings on the left, the town, an editor group of opened buildings on the right,
  the status bar) and uses tokens only.
- **A building's window is its UI document.** `js/layout.js` lays out the document's groups and
  panes as written (rows or columns by share, `auto` panes as tall as their content) and gives each
  pane its font and tone classes; `js/buildings/<type>.js` fills each pane id. The state behind it
  is the worker's, sent by `gui/views/<type>.py` as a `detail` only to the pages that have the
  building open (`watch`), again whenever the worker says it changed. Its acts are
  `{"name": "act", "args": {"id", "act", "args"}}`, each one a call on the worker.
- **Huts stand where the person put them**: `hut` in the Town Scroll, fractions of the room, the
  same the TUI reads. Dragging a hut saves its spot; a hut without one stands in a grid.
- **Roads run as in the TUI**: `js/roads.js` is `wm/roadmap.py` ported to the page (gates on the
  side that faces the other end, spread along it; orthogonal A* paths that keep to the gaps and
  turn as little as they can), so a road follows a hut while it is dragged. A road is keyed by
  `scroll.road_key` (`<target>:<road id>`): a road's own id is only unique in its building.

### Done

- The shell: HUD (Office words for the resources), War Map (switches the orkspace), the building
  list, the town with huts and orthogonal roads, an opened building as a tab with its status lines, garrison
  and roads, toasts, Halt All in the status bar.

- The windows of 🌊 Lake (Markdown rendered, a diff side by side, a file edited in place with the
  same autosave, conflict and judging as the TUI), 🌾 Task Fields (the board: drag a card to a lane,
  add, open, colour, task ⇄ note, send, delete) and 🗑️ Scroll Dump (the librarian's state, the
  wiki and its sources as a tree, a page rendered; take in, check, stop, add a folder).

### Next

1. The sessions service in the core and the War Tent's terminals in `xterm.js` (binary frames on
   the same socket); Orders answer an ork's question.
2. Building, roads and settings from the GUI; the other types' windows as their workers come.
