# Design — toward a GUI: one core, two faces

Orkcraft draws everything as terminal cells: one monospace font, one grid. A town where a
building's name, its status lines and its code each wear their own font needs a real GUI. The
town itself must change, not just a full-screen view. Rewriting ~20k lines of Textual at once
would stop all other work, so the move goes in stages. The TUI keeps working the whole way.

**The TUI is deprecated** ([calm-town.md](calm-town.md) §9): `orkcraft` opens the window, new features
go to the GUI only, and the TUI gets fixes until it is removed.

| stage | what | state |
|---|---|---|
| 0 | where the core lives | decided (§1) |
| 1 | the logic apart from the interface | the core, the road engine, the sessions and a worker for every type stand; what is left is listed in §2 |
| 2 | no file everybody has to touch | done for `app.py` (§3) |
| 3 | the design system and the building's UI as JSON | done: tokens, the document, three contracts, `D` (§4) |
| 4 | Office in the GUI: plain widgets, the same town graph | in progress: the shell, Lake, the keeper and every type stand; the calm town replaced the console ([calm-town.md](calm-town.md)) |
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
the deployments), `core/keeper.py` (a building's keeper: plain words in, its rules or settings
out), `core/runners.py`, and:

- **The road engine** is the `Town`'s (`town.roads`, built by `core/delivery.py`). A cart
  delivered, a handler's result, a run that ended and a cart on the road are core functions that
  record what happened and publish it; `tui/delivery.py` draws them (the 📥 note, the carts, a
  failed run's mark, the coin, the Loot list). `Town.budget_ok` is the 🪙 hook the face sets.
- **A worker for every type** (`core/workers/<type>.py`): 🕳️ The Pit, 🗼 Watchtower, 🚏 Signpost,
  ⚙️ The Mill, 📯 The Horn, 🌾 Task Fields, 🏕️ Barracks, 🪔 Clan Fire, 🥁 War Drum, 🌲 File Forest,
  🗑️ Scroll Dump, 🌊 Lake, ⚒️ The Forge, 📦 Loot Vault, 🪨 Tally Crag, 🎯 The Catapult, 🏰 Town Hall
  and 🛠️ Workshop. `workers/lake.py` also keeps the town's one Lake (`TownLake`, its documents in
  tabs). A cart goes to the building's worker (`core/delivery.py`). The TUI's typed views
  (`screens/typed/*`) keep the widgets, the keys, the dialogs and the timers and read their worker;
  their old names read the worker, so callers did not change.

`tests/test_core.py` runs all of it with no app at all.

**Left for stage 1**, the largest first:

1. **Workers for the other types.** Done: every type has its worker (above), and the typed views
   only draw it.
2. **Sessions and terminals**: the War Tent's terminals (pyte) are the face's, but deploying an
   ork, the processes and the roster's view of running sessions are not. Split them into a
   sessions service in the core that keeps the processes, and terminals that draw them (pyte
   today, xterm.js later). Done: `core/sessions.py` runs every session (processes, screens,
   deployment, the report of an ork that went home); the TUI's `Terminal` draws a session with
   pyte and the GUI's with xterm.js.
3. **🛑 Halt All through the `Town`.** `Town.halt()` stops the road handlers and every worker.
   Done in both faces: Halt All interrupts every session, kills every agent process
   (`halt.halt_all`) and calls `town.halt()`, so a worker whose window is closed stops too. The
   TUI also cancels the terminals it runs agents in; its toast says how many sessions, processes
   and buildings were stopped.

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
- `wm/desktop.py` keeps only the `Desktop` class (its bindings, messages and lookups) and the
  taskbar; its domains are mixins beside it: `wm/layout.py` (orkspaces, saving, biome),
  `wm/focus.py` (z-order, focus, the preview link), `wm/arrange.py` (window operations and window
  mode), `wm/town_view.py` (huts and the ghost), `wm/roads.py` (roads, traffic, rally mode).
- `screens/onboarding.py` is now a package, one module per part: `common`, `person`, `town`,
  `machine`, `raising`, `flow`.
- `screens/console/` is split by part: `cards.py` (what Info says, as text), `warmap.py`,
  `info.py`, `garrison.py` (the Clan Roster and the Inventory), `command_card.py`, and the
  `Console` itself in `__init__.py`, which still exports every name.

## 4. Stage 3 — the design system and the building's UI as JSON

See [`docs/design-system.md`](../design-system.md) for the rules (written for people and for the
orks that rebuild buildings). Shipped: `design/tokens.json`, `schemas/building-ui.v1.json`,
a contract for every type of the catalog (`design/buildings/<type>.json`; the retired Custom keeps the
one-pane `main`), the document kept per building in the Town Scroll, `D` 🎨 (the steward redesigns
from a wish), and the TUI drawing it (`tui/ui_apply.py`). The last two were 🌲 File Forest (the head
and the tree, with small previews) and 🏰 Town Hall (the tab strip and a pane per tab, Hall, Sessions
and Limits, only the open one shown). Next: a pane split further where a view grows a part people
would lay out on their own (the File Forest's text preview stays the TUI's own for now). The short
version:

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
  (core/sessions.py: the orks' CLIs on PTYs, a pyte screen and a backlog each, for every face)
  info.py     what the console says of a selected building or ork: Info, listens, the Inventory
  console.py  the console's acts (👍 / 👎, goal, pin, revert, recruit, orders, model, roads), made of
              parts: jobs.py (a model call in a thread, taken or let go), keeper.py (lake.open and
              keeper.ask), recruiter.py (the Recruiter, then the Council), steward.py (its watch, a redesign)
  views/      per type with a worker: what its window shows (`detail`), its acts (`ACTS`), its timer
  markdown.py Markdown as HTML, raw HTML off
  static/     index.html (import map), app.js, js/ (link, chrome, town, hut, roads, windows,
              console, acts, types, lake, keeper, layout, dialog, tent, orders, build, terminal), js/buildings/ (one per type the GUI
              draws, loaded when one opens), layout.css (every look), office.css, camp.css
```

- **The protocol.** The host sends a whole snapshot (`gui/state.py`) when the town changes, at most
  every 50 ms and only when it differs; the page keeps it in a signal, so only what read a changed
  part draws again. Commands are `{"t": "cmd", "id", "name", "args"}` answered by a `reply`; the host
  keeps a closed list of them (`Host.commands`). Toasts go out as they come. A text that may carry
  emoji comes twice, as it is and `_plain`, for Office.
- **Only its own page drives the town.** The socket takes a random token from the page's address
  and an `Origin` of this server; anything else gets 403.
- **The layout is the design system's.** `layout.css` places the components (HUD on top, the town, the
  panel over its right half, the orkspaces and the Warchief's line at its foot — [calm-town.md](calm-town.md))
  and uses tokens only.
- **A building, closed and open.** Closed (its hut card) and open in the panel (Work, Info): what each
  type shows, the hooks a type keeps (`card`, `panes`, `quick`) and how the work is split across
  branches — [building-views.md](building-views.md).
- **A building's window is its UI document.** `js/layout.js` lays out the document's groups and
  panes as written (rows or columns by share, `auto` panes as tall as their content) and gives each
  pane its font and tone classes; `js/buildings/<type>.js` fills each pane id. The state behind it
  is the worker's, sent by `gui/views/<type>.py` as a `detail` only to the pages that have the
  building open (`watch`), again whenever the worker says it changed. Its acts are
  `{"name": "act", "args": {"id", "act", "args"}}`, each one a call on the worker.
- **Terminals are the core's sessions drawn by xterm.js.** `core/sessions.py` runs each CLI on a
  PTY, keeps a pyte screen (the roster reads questions off it) and the last 512 KB of output. The
  page shows a session in the War Tent (the Town Hall's window, as in the TUI) with xterm.js, loaded
  the first time a terminal opens: `term.replay` sends the session as it stands, then its bytes
  come as binary frames to the pages that show it (`term.attach`); keys go back as `term.input`.
- **Orders**: the questions in the snapshot (`alerts`, the longest waiting first); the person picks
  an answer and `orders.answer` hands it to `Muster.answer` (typed into the session, or the
  Warder's acknowledged). A building whose ork asks burns: its hut and its orkspace say `?`.
- **Huts stand where the person put them**: `hut` in the Town Scroll, fractions of the room, the
  same the TUI reads. Dragging a hut saves its spot; a hut without one stands in a grid.
- **Roads run as in the TUI**: `js/roads.js` is `wm/roadmap.py` ported to the page (gates on the
  side that faces the other end, spread along it; orthogonal A* paths that keep to the gaps and
  turn as little as they can), so a road follows a hut while it is dragged. A road is keyed by
  `scroll.road_key` (`<target>:<road id>`): a road's own id is only unique in its building.

### Done

- **The calm town** ([calm-town.md](calm-town.md)), over what is listed after it: the console, the status
  bar, the advisor and Build went; a building opens in one panel on the right with Lake's documents
  (Work, Info, the documents' tabs); the orkspaces at the bottom left; the right click; the Warchief's
  line (`/` commands, `@` names, hints) and his cards, the work he gives the Town Builder, the road
  planner, the Recruiter and the keepers (`core/warchief.py`). What follows is how it was before.

- The shell: HUD (Office words for the resources), the town with huts and orthogonal roads, toasts,
  Halt All in the status bar. The strip over the town's bottom is the TUI's console: the War Map
  (the orkspaces only, a small block at the left, about a fifth of the window high; its list scrolls) and, for the selected
  building, its Info, its garrison (or a picked ork's Inventory) and its Command Card, laid out as
  the TUI's console.

- A building three ways, as in the TUI: its hut (the status lines its type keeps); selected (one
  click: Info in the room after the War Map and its garrison beside it, both as tall as the War Map,
  then its Command Card, a square window half the window high, at the right); open (a click on the selected hut, or Open:
  its whole window over the town). Esc steps back; a click on the bare town lets go.

- The console, as the TUI's: **Info** — the name with Good / Bad (what went wrong: the inputs or
  its logic) / its goal / Demolish, why it is here (three lines), one line of what it spent and its
  runs with History, one line of who it listens to with Listen (a road there picks it: its handler,
  removing it). An ork's Info: Good / Bad / Dismiss, why it is here, its spend with History. The
  **garrison** beside it; an ork picked there turns it into its 🎒 **Inventory** (model and tier per
  step, a click changes them; the tools of its latest runs). The **Command Card**: the type's own
  actions, Answer, Open, then the commands the TUI keeps on keys — Recruit (the Recruiter, then the
  Council; or by hand), Pin (a pinned hut is not dragged), Revert, Redesign; for an ork Deploy,
  Orders & trigger, Halt, the steward's Watch now and its report. A model call runs
  as a job (`jobs` in the snapshot) the page shows until the person takes it or lets it go.

- The windows of 🌊 Lake (Markdown rendered, a diff side by side, a file edited in place with the
  same autosave, conflict and judging as the TUI), 🌾 Task Fields (the board: drag a card to a lane,
  add, open, colour, task ⇄ note, send, delete) and 🗑️ Scroll Dump (the librarian's state, the
  wiki and its sources as a tree, a page rendered; take in, check, stop, add a folder).

- The War Tent: new Claude, Codex and agy sessions, earlier ones reopened, a garrison ork deployed
  with its orders (Deploy in its building's window), interrupt, stop; Orders answer the orks'
  questions; Halt All interrupts the sessions and kills every agent process too.

- The Elders in quiet hours: the host runs `core/night.py` as the TUI does; their advice shows in
  Orders with its option marked, and Follow the Elders sends it as the person's answer (at ⛓️‍💥 Free
  orks they answer themselves, as in the TUI).

- Changing the town (`gui/builder.py` over `core/buildings.py` and `core/roads.py`): Build raises a
  building from the catalog with its defaults; Demolish in a window takes it down (the Town Hall
  always stands); a road is pulled out of a hut's `+` handle onto another hut and laid with one of
  the events it may carry; a road clicked shows what it is and is taken up from there.

- 🏰 The Town Hall as the town's way in (`core/workers/town_hall.py`, `gui/views/town_hall.py`,
  `js/buildings/town_hall.js`): its hut is Build (in one: say what you need, or pick from the
  catalog by what it is for) and Ask me anything; its Command Card the Warchief's chat (a building
  it names is built on a click), the live sessions, the audit, spend and quotas; its window the tabs
  Hall, Sessions (the War Tent) and Limits. The status bar keeps Halt All, Answers and the project.
  The TUI's Hall reads the same worker.

- 🌊 Lake is the town's window, not a building (`TownLake`, `gui/views/lake.py`, `js/lake.js`): one
  Lake for the whole town, the right half of it or all of it with a click, documents in tabs —
  Markdown, code, a diff, a picture, a PDF, a web page; code and Markdown edited in place with
  autosave. Any building opens a document there (`openInLake`). An old scroll's Lake buildings leave
  the map, and a road into one becomes "open in Lake" on its source.

- The keeper (`core/keeper.py`, the host's `keeper.ask`, `js/keeper.js`): the person says in plain
  words what a building should do, and its keeper writes its rules or settings (a whole `config`,
  or the part a type registers: the Signpost's `rules`). Its proposal comes back as a job — the
  change line by line and its answer — then Apply, or Drop; Revert takes it back. On a selection in
  Lake the keeper of the building the document came from answers about it.

- Every type three ways — closed, command, full, as [building-views.md](building-views.md) §3 has
  it — on its own worker, `gui/views/<type>.py` and `js/buildings/<type>.js`: 🕳️ The Pit, 🚏 Signpost
  and ⚙️ The Mill; 🗼 Watchtower (counters per source, the newest per source, the feed, the intent),
  📯 The Horn (mute and volume on the card, the page plays the sounds) and 🥁 War Drum; 🌾 Task Fields,
  🌲 File Forest and 🗑️ Scroll Dump; 🏕️ Barracks (a tab per ork with its terminal) and 🪔 Clan Fire;
  ⚒️ The Forge, 📦 Loot Vault and 🎯 The Catapult (rules, schema and address through the keeper);
  🪨 Tally Crag (a dashboard) and 🛠️ Workshop (its runs and Test).

### Porting a building type

The recipe the three first types followed (🌊 Lake, 🌾 Task Fields, 🗑️ Scroll Dump); a type is
found by its files, so a port touches no shared list and parallel ports do not collide.

1. **The worker** — `orkcraft/core/workers/<type>.py`: a `Worker` subclass with `TYPE = "<type>"`
   (the catalog id). Move into it everything the view does that is not drawing: its state, its
   acts, its threads (results come back through `self.town.call`), `receive`, `halt`, `status`,
   `mini_status` / `hut_lines`, and `self.changed()` whenever its state changes. No Textual, no
   Rich (`tests/test_architecture.py`). It registers itself.
2. **The TUI view** — `orkcraft/screens/typed/<type>_view.py` keeps its widgets, keys, dialogs and
   timers, and reads and calls the worker (`self.worker`); its old attribute names read the worker,
   so callers and tests keep working. It draws again on `WORKER` (see `lake_view.py`).
3. **The contract** — `orkcraft/design/buildings/<type>.json`: the panes the window has, the
   components each may wear and the default document (`design/ui.py`). Name the panes in the TUI
   view's `UI_PANES`.
4. **The GUI's side** — `orkcraft/gui/views/<type>.py`: `detail(worker)` (plain data the page
   draws, Markdown rendered by `gui/markdown.py`, emoji also as `_plain`), `ACTS` (each a call on the
   worker, its arguments checked with `views.text`, a refusal raised as `ActError`), and
   `REFRESH_S` / `refresh(worker)` when the view looked again on a timer.
5. **The page** — `orkcraft/gui/static/js/buildings/<type>.js`: `panes(id, data)` returning one
   function per pane id of the contract; acts are `act(id, name, args)`. Use the design system's
   markup and classes, the roles' classes for fonts and tones, and the words of Office (no
   pictographs; `ok-ico` for what Camp may show).
6. **Tests** — the worker without an app (`tests/test_core.py`), the TUI's tests unchanged and green,
   and `detail` and every act through the host (`tests/test_gui.py`). Then look at it in the page:
   `orkcraft gui --demo --browser`.

### Next

1. A road an ork handles by a rule (Listen with a prompt: the Recruiter and the Council), the
   building wizard with the Builder, and a building's settings in its window.
2. ~~The other types' windows as their workers come (§2, 1).~~ Done: every type's window (above).
3. Camp (stage 5): the same page in `data-theme="camp"` with the sprites — `orkcraft gui --look
   camp` opens it; what only Camp adds goes in `camp.css` and in what `js/hut.js` draws.
4. A phone over the same host: glance, Orders, the Pit, the Warchief, Halt All, pushes —
   [mobile.md](mobile.md); stage 0 (`gui/mobile.py`, `GET /api/version`) stands.
