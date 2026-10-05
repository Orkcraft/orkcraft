# Design — toward a GUI: one core, two faces

Orkcraft draws everything as terminal cells: one monospace font, one grid. A town where a
building's name, its status lines and its code each wear their own font needs a real GUI. The
town itself must change, not just a full-screen view. Rewriting ~20k lines of Textual at once
would stop all other work, so the move goes in stages. The TUI keeps working the whole way.

| stage | what | state |
|---|---|---|
| 0 | where the core lives | decided (§1) |
| 1 | the logic apart from the interface | in progress (§2) |
| 2 | no file everybody has to touch | in progress (§3) |
| 3 | the design system and the building's UI as JSON | in progress (§4) |
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
- **The bus** (`core/bus.py`): topics such as `toast`, `roads`, `roster`, `hall`, `spec` and
  `hud`. A service never shows anything. It publishes, and each face decides how to show it.
- **Runner seams** (`core/runners.py`): the model calls tests replace (`BUILD_RUNNER`,
  `ELDERS_RUNNER`, …), in one place for every face.

What stays in the face: dialogs and their flow, focus, keys, layout, windows, huts, carts,
terminals. A dialog's *decision* calls a service, and the dialog itself is the face's.

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
orks that rebuild buildings). The short version:

- **Tokens, not values.** Font roles (`title`, `body`, `mono`, `status`, `label`), colour roles
  (`ok`, `wait`, `fire`, `muted`, `accent`, the harness colours), spacing steps. Camp and Office
  are two themes over the same roles. The TUI maps a font role to a text style (bold, dim, …),
  and the GUI maps it to a real font.
- **One building, one UI document.** Every building has a UI document (`building-ui.v1`):
  panes of components bound to the building's data, laid out in rows and columns by ratio. The
  built-in buildings ship theirs (`orkcraft/design/buildings/*.json`). A custom building's
  layout is its spec's panes. A steward that rebuilds a building's UI edits that document, and
  the validator checks it.
- **Components are a closed list** (`list`, `table`, `counter`, `markdown`, `editor`, `board`,
  `diff`, `tree`, `terminal`, `chart`, `form`, `log`). Each face renders each component in its
  own way. Nothing in the document is code, a raw colour or a font name.
- **The graph stays simple** (the invariant Office and Camp must keep): one kind of edge, the
  road. No ports or parameters on the canvas. A building shows its name and up to three status
  lines, and all its settings live inside its window. Positions are the person's, never an
  automatic layout.
