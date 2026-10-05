# Orkcraft — notes for contributors and agents

## Wording

- In everything a person reads — the interface (labels, hints, toasts, errors), the docs, the
  README — write **ork** / **orks** / **Ork** and **orkestration** / **orkestrate**, never "orc" or
  "orchestration". A level of the onboarding is **Punk ork**.
- Code keeps its names: identifiers, module and file names (`realm/orcs.py`, `Orc`, `orc_id`),
  CSS ids, dict keys, event ids and config values stay as they are, so settings and town scrolls
  written before keep loading.
- Tests that check a visible string use the same wording.

## Where code goes (docs/design/gui-migration.md)

- `orkcraft/core/`, `orkcraft/realm/`, `orkcraft/design/` have no face: they never import Textual,
  Rich or a face module (`tests/test_architecture.py` checks it). A service changes the town and
  publishes on the bus (`core/bus.py`). It never shows a toast or a dialog itself.
- `orkcraft/tui/<domain>.py` holds one part of `OrkcraftApp` each. A new feature goes into its domain's
  module or a new one, never into `app.py`. Split a module before it grows past ~600 lines.
- A building's window is a UI document of roles, never raw colours or font names
  ([docs/design-system.md](docs/design-system.md)). The rules a model gets are `design/ui.py` `RULES`.
