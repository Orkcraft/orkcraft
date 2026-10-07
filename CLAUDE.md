# Orkcraft — notes for contributors and agents

## Wording

- In everything a person reads — the interface (labels, hints, toasts, errors), the docs, the
  README — write **ork** / **orks** / **Ork** and **orkestration** / **orkestrate**, never "orc" or
  "orchestration". A level of the onboarding is **Punk ork**.
- Code keeps its names: identifiers, module and file names (`realm/orcs.py`, `Orc`, `orc_id`),
  CSS ids, dict keys, event ids and config values stay as they are, so settings and town scrolls
  written before keep loading.
- **One vocabulary** (Camp and Office are merged; there are no modes). A concept keeps its Camp word
  when it says *who* (ork, Warchief, town, building, road, Town Hall, Renown) and has a plain word
  when it says *what a thing does, costs or risks* (External listeners, Spend, Stop all, Autonomy,
  Project file). `orkcraft/realm/lexicon.py` `TERMS` is the glossary: a new concept or building type
  gets its one word there, and new code writes that word. A renamed concept keeps its old Camp
  spelling in `was`, and the interface says an old spelling in today's word: the TUI every widget's
  text (`tui/wording.py`), the GUI the literal text of every `html` template (`gui/static/js/html.js`;
  attributes and data go through `say()`). A widget that shows what people or agents wrote gets the
  `-as-written` class (TUI) so it keeps its words; Markdown, inputs, logs and terminals keep theirs.
- The voice stays the camp's: the Warchief's lines, growth news and the onboarding may joke; labels,
  settings and anything about money or safety say plainly what happens.
- Tests that check a visible string use the same wording.

## Where code goes (docs/design/gui-migration.md)

- **The TUI is deprecated** ([docs/design/calm-town.md](docs/design/calm-town.md) §9): a new feature
  goes to the GUI (`orkcraft/gui/`) only. The TUI (`tui/`, `screens/`, `widgets/`, `wm/`, `app.py`)
  gets fixes and nothing else; its tests stay green until it is removed.

- `orkcraft/core/`, `orkcraft/realm/`, `orkcraft/design/` have no face: they never import Textual,
  Rich or a face module (`tests/test_architecture.py` checks it). A service changes the town and
  publishes on the bus (`core/bus.py`). It never shows a toast or a dialog itself.
- `orkcraft/tui/<domain>.py` holds one part of `OrkcraftApp` each. A new feature goes into its domain's
  module or a new one, never into `app.py`. Split a module before it grows past ~600 lines.
- A building's window is a UI document of roles, never raw colours or font names
  ([docs/design-system.md](docs/design-system.md)). The rules a model gets are `design/ui.py` `RULES`.

## Releases (docs/updates.md)

- A release raises `__version__` in `orkcraft/__init__.py` (the only version) and adds itself at the
  top of `updates.json` in the same commit to `main`. Installed copies read that file to update.
- `"critical": true` only for a security fix or a bug that loses work: it installs on every machine
  without asking. Its `notes` say plainly what it fixes.
