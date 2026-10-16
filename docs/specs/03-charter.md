# Spec 03 — the charter, "My project" path

Branch `spec/03-charter` · model **pro** · design: first-mission.md §11, §11.1; decisions §21
**Builds:** Claude · **Review:** full (docs/specs/README.md "Who builds")

## Why
Mission 1's quests 1–3 are drills. Before quest 4 (the first real work) the camp is given its purpose. This spec
builds only the "My project" answer and "Just looking"; the routine path is later.

## Do
1. **The moment.** In the mission engine (`orkcraft/realm/mission.py` the quests' data; `orkcraft/core/mission.py`
   the flow; `orkcraft/gui/static/js/mission.js` the quest log), when quest 4 starts and no charter is set, the quest
   log shows the charter step first. Workchief's line: "Boss, the drills are done and the Grunts are restless. What
   are we building here?" Two choices: **My project** · **Just looking** (a small "Later" link keeps today's quest 4).
2. **My project:** one text field "The goal, in one line" (placeholder: "a co-op roguelike, a playable demo by
   December"), an optional date field "By when". Save in `.orkcraft/charter.json` under the town's root:
   `{goal, by, set_at, cards: []}` (a new module `orkcraft/realm/charter.py`: `load(root)`, `save(root, data)`, pure,
   no GUI). Record an event `charter_set` on the local event log (as `core/mission.py` `_record` does).
3. **The survey, free, no model** (`realm/charter.py` `survey(repo_root)`): languages by file extension counts, the
   number of files, README's first 40 lines, the test command if found (reuse whatever finds it; else `pytest` /
   `npm test` / `go test ./...` / `cargo test` / `make test` from the project's files), the `docs/` folder's Markdown
   files list, open issues via `orkcraft/realm/mission_work.py` `found()` (it already reads GitHub or TODOs).
4. **The first cards, one model call, price said first.** Button "Propose the first cards" with its price shown
   before the press (use the same price wording quest 4 uses). The steward of the Town Hall (the Workchief's tool, as
   quest 4's calls do) gets the goal + the survey and returns 3–5 cards: title (≤ 8 words) + one-line why. The person
   sees them as a list with a checkbox each (all checked), can edit a title, and presses **Put on the board**: each
   becomes a task card on the first Task board through the existing add act (`fields.add`, as the phone's + Task
   does). Store their ids in `charter.json` `cards`.
5. **The docs become the Wiki (free):** if the survey found Markdown docs (`docs/` with ≥ 3 `.md`, or ADRs), offer one
   line "Your project's docs can be the camp's library — free, no model. Open the Wiki on docs/?" Yes builds a Wiki
   building (type `scrolls`) whose source is that folder, through the same code the Build menu uses (find it from
   `orkcraft/gui/static/js/build.js` → its command), with no ingest run.
6. **The banner:** a `charter` item drawn on the wall band beside the lookout in Camp (`js/camp/town.js`, a simple
   stand-in: a teal pennant on a pole from the v4 kit's colours; `stand_in: true`), its tooltip the goal line; a
   click opens the charter (edit goal and date; the cards listed with their state). In Office, the goal line shows in
   the town's header instead. A card whose id is in `cards` shows a small pennant mark on its waybill.
7. **Just looking:** sets `{goal: "", looking: true}`; quest 4 runs as today; the Town Hall's menu gets "Give the camp
   its charter…" to come back later.

## Don't
- No points, levels or progress bars on the goal (milestones only, not built here).
- Don't change quests 1–3 or 5. Don't ingest code into the Wiki.
- Words: "goal", "charter", "cards", "the camp's library" — plain; the Workchief's line may joke.

## Tests
Critical tests, plus `tests/test_mission.py tests/test_gui_mission_browser.py`, and new
`tests/test_charter.py`: `survey()` on a small temp repo (languages, README, docs list, test command); `save/load`
round trip; the cards land on the board through the act; "Just looking" leaves quest 4 unchanged. A browser test:
the charter step appears before quest 4, the goal is saved, the banner shows its tooltip.

## Done when
Tests pass; screenshots by the PM session: the charter step, the proposed cards, the banner in Camp.

## Prompt
Use the prompt in docs/specs/README.md with `<NN-name>` = `03-charter`.
