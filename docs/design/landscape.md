# Design — landscape: what needs no ork is part of the land

Status: written 2026-10-08, agreed with the owner; stage 1 (§9) built the same night — see §11 *As built*. Part of the simplification
([simplify.md](simplify.md)). Builds on script-first buildings ([script-first.md](script-first.md)),
folded cards ([folded-cards.md](folded-cards.md)), growth ([growth.md](growth.md)) and the steward's
road rules (`realm/lexicon.py` `road_rule`).

## 1. Why

The catalog has 21 building types (`realm/catalog.py` `TYPES`). A newcomer meets 21 metaphors before the
town does anything for them. Most of the camp's charm (the Camp look, the town, the orks, sprites,
Renown, stages, classes and mascots, fire on the roofs) is not the problem and stays as it is.

The problem is that half of these buildings never think. Script-first (built) already says so: a Drop
file here, a Router, a File tree, a Metrics, a Sound alerts and an Inspector call no model; their ork
wakes only when the script fails or the person gives a 👎. Folded cards (built) already shrink the
Pit, the Signpost and the Mill to a title bar by default. Their ork and their card are decoration.

The rule this design follows: **an ork lives only where something thinks. What needs no ork is
landscape: a sprite in the land, no card, no ork.**

Half of these already have a landscape name: a lake, a crag, a forest, a pit.

## 2. The split

| | Buildings (have orks) | Landscape (no ork) |
|---|---|---|
| Types | Town Hall, External listeners (`watchtower`), Task board (`fields`), Agent pool (`barracks`), Review board (`council`), Calendar (`war_drum`), Wiki (`scrolls`), Research (`mine`), Audio briefing (`gramophone`), Branches & PRs (`forge`), Publisher (`catapult`), Review gate (`loot`), Script (`workshop`) | Router (`signpost`), Transformer (`mill`), Drop file here (`pit`), Inspector (`lake`), File tree (`forest`), Metrics (`crag`), Sound alerts (`horn`) |
| Count | 13 | 7 |
| Model calls | yes | never |
| Card on the map | yes (may fold) | none |
| Steward, orders, retro | yes | none |
| Renown, goal flag | yes | none |
| Fire on the roof | yes: an ork asks | never: land does not ask |
| Trouble | the steward wakes | smoke on the sprite, `error` mark; §4 says who looks |

`custom` (the old panes) stays loadable and leaves the catalog's list.

### 2.1 Why these stay buildings

- **Calendar** reads files and calls no model today, but it stays a building: its steward will judge
  the day (how productive it was, the limits, the load). That is future work, not this design.
- **Review gate** holds carts for the person's decision; a decision waiting on the person is fire,
  and fire belongs to a building.
- **Script** is the Builder's building made from scratch (interview, blueprint, sandbox, its own window,
  exit 3 asks its steward). It is not a Transformer's `script:` step and does not merge into one.
- **Branches & PRs** runs tests and merges; its steward names conflicts.

## 3. The Transformer loses its `agent:` step

A Transformer becomes pure landscape: regexes, conversions, templates, `script:`. Its `agent:` step and a
script's `|| agent:` fallback go away (`realm/mill.py` `MODEL_STEPS`, `FALLBACK`).

- **Where the thinking goes.** What an `agent:` step asked becomes a **Road rule** of the building the
  Transformer's road leads to: that building's steward does it with the carts of that road. Only a
  building with an ork thinks.
- **What is lost.** An agent step in the middle of a chain: `script → agent → script` becomes
  `Transformer → building → Transformer`. A failing script no longer falls back to an agent; it smokes
  and §4 applies.
- **Saved towns.** A Transformer with `agent:` steps loads as follows: its steps up to the first `agent:`
  stay; the `agent:` ask becomes a Road rule on the road's receiving building; steps after it become a
  second Transformer on that building's way out. A Transformer whose road leads nowhere that has an ork
  becomes a **Script** (`workshop`) with the ask as its steward prompt. The Warchief says it once.
  The demo's changelog Transformer (`demo/seeds.py`, `demo/dashboard.py`) is rewritten the same way.

## 4. Who looks when land breaks

Landscape has no steward, so a failure (a rule that no longer matches, a file that cannot be read, a
script that exits non-zero) and a 👎 go, in order, to:

1. the steward of the building its road leads to (the first one with an ork downstream);
2. the Warchief, when no road leads to an ork.

They wake as script-first wakes a keeper today (`core/wakes.py`): once per failure, with the object's
log. What they may change is the object's settings (rules, steps, sounds), through the same
proposal and Autonomy as their own.

## 5. How it looks (GUI; the TUI is deprecated and gets no new feature)

- **Camp.** A sprite in the land, no card and no title bar. Where it stands:
  - Router: a signpost at a road's fork (it is drawn on the road, not beside it);
  - Transformer: a mill on the road;
  - Sound alerts: a horn on the roof of the building it sounds for;
  - Drop file here, Inspector, File tree, Metrics: a pit, a lake, a forest, a crag in the land.
- **Hover**: a tooltip with what a folded card's mark says today (`js/types.js` `mark`): "12 dropped",
  "3 routed".
- **Click**: a small window: its settings and its log. No steward pane, no orders, no retro.
- **Trouble**: smoke or sparks on the sprite and the `error` mark. The rule reads at a glance:
  **fire is a question, smoke is a breakdown.**
- **Drop**: a file dragged onto the pit still lands in it.
- **Office**: a small monochrome glyph on the road's line or in the land; no sprite.
- **Growth**: landscape earns no Renown. Renown is the orks' changes that passed probation
  (`realm/growth.py`); land has no orks to learn. A landscape object never shows a level or a flag.

## 6. Wording

- `TERMS` gets one word: **landscape** (`_t("landscape", "landscape")`): the things in the land that
  need no ork. Each type keeps its word (Router, Transformer, Drop file here…); nothing is renamed.
- The onboarding says it in one line: *orks work in the buildings; between them is the land.*
- The Wizard's list shows buildings first and landscape as its own group.

## 7. Saved towns

The data does not change: ids, specs, roads and event ids stay. The change is a flag on the type,
`BuildingType.landscape: bool` (as `folded` is), and what the face draws and wakes from it.

- A saved landscape object's garrison (its resident ork and orders) is kept in the file but not shown or
  run; turning it back into a building would find it.
- Only §3 (a Transformer's `agent:` step) rewrites a spec, in `catalog.py`'s spec migration, at load:
  the file on disk changes on the next save. The old steps are kept in the object's History.
- Data folders (`.orkcraft/<type>/<id>`) stay where they are.

## 8. Not in this design (discussed, rejected)

- **Script into Transformer**: loses the Builder's made-for-you building (§2.1).
- **Review gate into Review board**: one is models arguing over a document, the other is the person's
  decision by rules, per file, with reworks. If it moves, it moves to a road setting (*wait for my
  decision*, as `confirm` already is on Branches & PRs and Publisher), in a design of its own.
- **Research into Wiki**: Research's promise is the check by two minds on two sites
  ([mine-next.md](mine-next.md)); the Wiki keeps the report. Two jobs, two buildings.
- **Calendar's steward judging the day** (§2.1): future work.

## 9. Stages

1. **The flag and the catalog**: `landscape` on the seven types, the Wizard's groups, `custom` out of the
   list, the term in `TERMS`. Tests: the catalog's checks, the architecture test.
2. **Who looks** (§4): failures and 👎 of landscape wake the downstream steward or the Warchief; the
   landscape object's own keeper never runs. Test: a runner that fails if a landscape object's ork is
   called.
3. **The look** (§5): sprites without cards, hover, the small window, smoke. Checked in the demo with
   Playwright, Camp and Office.
4. **The Transformer without `agent:`** (§3): the migration, the demo rewritten, `MODEL_STEPS` gone.
   Last, because it is the only stage that rewrites saved specs.

## 10. Open questions

- Does a Sound alerts with sounds for several buildings become one horn on each roof, or stay one horn
  in the land?
- Is a landscape object's old garrison dropped from the file after some releases, or kept for good?

## 11. As built

**Stage 1** (night audit 2026-10-08, P1):
- `BuildingType.landscape` (`realm/catalog.py`), set on the seven types of §2; `catalog.LANDSCAPE` is their set.
  File tree and Inspector are retired (`RETIRED_TYPES`: never built anew) but keep the flag, so an old
  town's carry it.
- `custom` was already out of the wizard's list (`RETIRED_TYPES`, `gui/builder.py`); nothing to do.
- The GUI's Build list (`gui/builder.py` `catalog_types`) puts buildings first, by their intent, then the
  landscape as one group, *Landscape: works by itself, needs no ork* (`LANDSCAPE_GROUP`); each item carries
  `landscape` for the face. The TUI's preset picker is unchanged (the TUI is deprecated).
- `TERMS` has `landscape`. The onboarding's one line (§6) is not said yet: it waits for the stage that
  draws the land (stage 3), so the line names something the person can see.
- Test: `tests/test_catalog.py` `test_the_landscape_is_the_seven_types_that_need_no_ork`.
