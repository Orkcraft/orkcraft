# A building three ways — closed, command, full

What every building shows in the GUI, agreed type by type, and how the work is split so that several
sessions can build it at once. The TUI's typed views (`screens/typed/*`) are where the behaviour comes
from; this is what the GUI makes of it. Camp words here; the Office says them in its own
(`realm/lexicon.py`).

## 1. The three views

| View | Where | What |
|---|---|---|
| **closed** | the hut on the town | The name and number hang **above** the card and take no room in it (with `?` when an ork waits and `pinned`). Inside: only the type's live status — a few words, a counter, a control (Horn) or a thumbnail (Tally Crag). No buttons but the road handle `+`. |
| **command** | the Command Card window (a square half the window high, bottom right) | A cut-down main screen of the type (its queue, its list, its chart) and its main buttons: the type's quick actions and one or two of its most used acts. Below a line the commands every building has (Recruit, Pin, Revert, Redesign). |
| **full** | over the whole town (a click on the selected hut, or Open) | Everything the type does, laid out by its UI document. |

Info (what every building and ork shares) and the garrison stay as they are (`js/console.js`).

## 2. Rules for every type

- **Lake is a window, not a building.** One Lake for the whole town, half the window by default, made
  full by a click; documents in tabs. It shows PDF, images, web pages, code and Markdown; code and
  Markdown are edited in place and save by themselves (as the TUI's Lake). Any building that has a
  document or a file opens it there with a click on the document's mark — whether a Lake ever stood
  on the map or not. Saving writes the file.
- **Ask the keeper on a selection.** In Lake a part of the content is selected (lines, a paragraph, an
  area of an image) and a task written for the keeper: the selection is marked in its colour, the
  keeper's mark stands beside it, its answer comes in a dialog. The keeper is the one of the building
  the document came from; through it the work can go on (a Barracks reworks a picture, rewrites a
  part).
- **No rule editors: the keeper writes them.** Where a building has rules or settings in its own
  language (Signpost's rules, Clan Fire's briefs, Tally Crag's charts and thresholds, Catapult's schema,
  Loot Vault's rules, Workshop's script and schedule), the person says what they want in plain words
  and the building's keeper writes it. The views show the result, test it and keep its history.
- **Old scrolls.** A Lake building in a Town Scroll leaves the map when the scroll loads; a road into it
  becomes "open in Lake" on its source.
- **Custom (panes)** leaves the catalog.
- The status bar keeps Halt All, Answers and the project path; Build, Add agent and Sessions go to the
  Town Hall.

## 3. Type by type

| Type (Office) | closed | command | full |
|---|---|---|---|
| **The Pit** (Inbox) | only "drag & drop" — the card is the drop zone | the history of what was dropped | the history with what each processing chain cost and the artifacts it left in other buildings |
| **Watchtower** (External listeners) | per source: `gmail 3`, `slack 99+`, `jira ERR`, more than four → `+2 more`; mentions are not singled out | the newest per source (3–5: source, from, title); a failing source marked with "why"; Open new, Read all, Check now | sources with counters and state · the chosen source's feed · the item in full; a tab for sources and the intent |
| **Signpost** (Router) | a counter per outgoing road, each in its road's colour; the start of each road at the post wears the same colour | the rules one per line, the last carts (unmatched marked), Test (paste a text, see its route); rules asked of the keeper | no editor: the keeper writes the rules from plain words; testing the rules on an example and the history filtered by route |
| **The Mill** (Transformer) | the last run's status and time | the steps as a chain (the failing one marked), the last 3–5 runs, Run, Edit steps | the steps; for a chosen run input → output **for every step**; the history with costs (when a step is an agent); the queue |
| **The Horn** (Sound alerts) | a mute toggle and a volume slider | road or event → sound (a click moves to the next sound and plays it), the last calls (heard or kept quiet and why), Test, Mute | the table, an audio file per row, quiet hours, cooldown, the whole log. The page plays the sounds |
| **Task Fields** (Task board) | counters per lane, `*` on a lane with unseen cards; in notes mode the note folders | a small board: the status lanes with their top cards, **drag between lanes works here**; note lanes folded to counters; New task, New note | the board as it is. **New:** the person adds note folders |
| **Barracks** (Agent pool) | two lines: `active 2/4 · queue 3` and `✓5 ✗1 · $1.20`; `<keeper> asks` first when it asks | the orks (tier, task, state) — a click opens the ork's terminal; the queue's top; New task, Pause / resume, Answer | lanes by task state (queue → work → review → done / failed) with branch, ork, reworks, cost, PR; the chosen task (brief, diff, review notes, questions); **a tab per ork with its terminal**; rules and settings |
| **Clan Fire** (Review board) | only the review's state: `cycle 2/3 · 3 ✓ 1 ✗ · $0.40`, else the last outcome, `N queued` | members (role, tier, veto, verdict now), the document under review and the last turns; Review, Add member, Answer | members, the review turn by turn and by cycle, the document with its comments, the report, past reviews. Briefs and rules through the keeper |
| **War Drum** (Calendar) | the day's first three meetings | the day (time, title, a document mark), now highlighted; New event, Prepare doc | today by the hour and the week; the chosen meeting; settings. A meeting's document opens in Lake |
| **File Forest** (File tree) | `./<folder>`, `changed: N files`, `🎯 <name>` when picked | the top of the tree (folders open), changed files marked, a click picks the target; Open in OS, **Send** (the picked file down its road) | only the tree: folders open in place, small previews of images and video. Files open in Lake |
| **Scroll Dump** (Wiki) | pages and pending only | the librarian's state, the last changed pages; Ingest, Lint, Add base | the window as it is (tree, page, state, acts). Pages open in Lake |
| **The Forge** (Branches & PRs) | `branches 4 · PRs 2` and the last merge (`✓` / `✗ conflict`), `merging …` meanwhile | branches with PR, tests and changes; Merge (always confirmed), Open PR, Run tests | branches; the chosen one's commits, diff (in Lake), test output, conflicts and how they were settled, the PR **with its comments**; settings |
| **Loot Vault** (Review gate) | `N to review` (or `all reviewed ✓`), `passed: N` and **what the waiting carts cost** | the queue (what, from where, cost), Accept / Rework per item, Accept all, Accept files; a cart opens in Lake | the queue and what passed; the chosen cart and the chain it came through with each step's cost; a cart is **edited in Lake** before it is accepted; rules through the keeper |
| **Tally Crag** (Metrics) | thumbnails of the charts set to *all states* | the charts set to *all states* or *command only*, Flip, Next | a dashboard: every chart. **Each chart says where it shows: all states / command only / full only.** Charts are made from sources by the keeper; thresholds too |
| **The Catapult** (Publisher) | one line: `wait 2/3`, `3 loaded`, `firing…` / `fill 2/5`, `log in`, else `✓ 201` / `✗ 422` | what is loaded and what it waits for, the schema check, the last 3 shots, the browser's current step; Fire, Dry run, Scout. **Confirm before Fire is a setting changed here and in full** | the load (JSON with schema errors marked), the shots (request, answer, code), for the browser the forms and fields with a small screenshot per step (large in Lake). Schema and URL through the keeper |
| **Town Hall** (Control panel) | the town's way in: **Build** (presets and new from scratch in one) and **Ask me anything** | **a chat with the Warchief**; the live sessions, the audit, spend and quotas (Limits) | Hall (its orks, the audit, proposals), Sessions (the War Tent), Limits |
| **Workshop** (Script) | the last run (`✓` / `✗` / `→ keeper`) and its schedule | the last runs (time, code, what went out) and the last result cut down (log / table / card); Run, Test | the runs; the chosen one's input, output and result. The script is edited **in Lake**. Test's log shows in a dialog and in the full window |

The Town Hall's ork becomes the **Warchief** (Office: *Lead agent*).

## 4. The contract a type keeps

So that every type can be done on its own branch, a type is one set of files and a few named hooks;
the shell never has a list of types to edit.

| Side | File | Hooks |
|---|---|---|
| core | `core/workers/<type>.py` | the worker: state and acts, no face (a `Worker` with its `TYPE` registers itself) |
| host | `gui/views/<type>.py` | `card(worker)` → small JSON for **closed** (in every snapshot, keep it tiny); `detail(worker)` → what **command** and **full** draw (sent while the building is selected or open); `ACTS`; `REFRESH_S` / `refresh` |
| page | `gui/static/js/buildings/<type>.js` | `card(b)` → the inside of the hut card from `b.card`; `preview(id, data)` → the top of the Command Card; `panes(id, data)` → the full window's panes by its UI document |

A hook a type does not export falls back: `card` → the status lines (`status_plain`), `preview` → no
preview (the buttons only), `panes` → the window's old body. Shared helpers a type calls but never
redefines:

- `openInLake({path | url | text, title, from})` — `js/lake.js`: the document in a tab of the town's Lake
  window (the host's `lake.open`, `gui/views/lake.py`); resolves with the tab's id.
- `askKeeper(buildingId, request, selection?)` — `js/keeper.js`, over the host's `keeper.ask`
  (`core/keeper.py`): the keeper's proposal comes back as a job (the change line by line, its answer —
  about the selection when there is one — then Apply, or Drop; Revert takes it back). `KeeperAsk` is the
  request field a type puts in its views, `KeeperDialog` the same in a dialog. What a type's keeper writes
  is its whole `config` unless the type registers a part of it (`keeper.register`; the Signpost's `rules`).

## 5. Parallel work

One branch and one PR per track; a track touches only its own files plus, at most, one line of
registration. Order: **F** first (it lands the contract); then everything else at once.

| Track | What | Owns |
|---|---|---|
| **F — foundation** | the title above the card, the `card` / `preview` hooks, the Command Card's preview slot, the `openInLake` and `askKeeper` stubs, this document | `js/hut.js`, `js/console.js`, `js/windows.js`, `js/types.js`, `js/lake.js`, `js/keeper.js`, `gui/state.py`, `layout.css` |
| **L — Lake window** | Lake as one window (tabs, half / full), PDF, images, web, code and Markdown with autosave; the selection and its task for the keeper; old Lake buildings leave the map | `core/workers/lake.py`, `gui/views/lake.py`, `js/lake.js`, `js/buildings/lake.js`, `realm/` migration of the scroll |
| **K — keeper** | `keeper.ask`: a request in plain words → the keeper changes the building's rules or settings (a job like Redesign: proposal, take it, Revert takes it back) | `gui/console.py` (its own section), `core/keeper.py`, `js/keeper.js` |
| **H — Town Hall** | Build in one, Ask me anything, the Warchief's chat in the Command Card, Limits; the status bar without Build / Add agent / Sessions; Chieftain → Warchief (with its Office word); Custom leaves the catalog | `js/tent.js`, `js/chrome.js`, `gui/views/town_hall.py`, `js/buildings/town_hall.js`, `realm/lexicon.py`, `realm/catalog.py` |
| **B1** | The Pit, Signpost (road colours with **F**'s roads), The Mill | their worker, view and page files |
| **B2** | Watchtower, The Horn, War Drum | ″ |
| **B3** | Task Fields (preview with drag, note folders), File Forest, Scroll Dump | ″ |
| **B4** | Barracks (the ork tabs with terminals), Clan Fire | ″ |
| **B5** | The Forge, Loot Vault, The Catapult | ″ |
| **B6** | Tally Crag (the dashboard and its per-chart visibility), Workshop | ″ |

A type without a worker yet gets one first, ported from its TUI view (`screens/typed/<type>_view.py`)
as Lake, Task Fields and Scroll Dump were; the TUI view then reads the worker (`docs/design/gui-migration.md`
§2). Each track's PR: `pytest -n auto` green, the type checked in `orkcraft gui --demo --browser`.
