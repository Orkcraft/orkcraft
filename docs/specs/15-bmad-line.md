# Spec 15 — a process as a line: the BMAD line template

Branch `spec/15-bmad-line` · model **pro** · design: docs/design/process-lines.md (all of it) · after specs 06 and 14
**Builds:** Claude · **Review:** full (docs/specs/README.md "Who builds")

## Do
1. **Line templates as data:** `orkcraft/realm/line_templates/bmad.json` (new folder; a loader in a pure module
   `orkcraft/realm/lines.py`, tested): name, stations in order, each `{type, role, prompt_file, debate, approve,
   parallel}`, the roads between them, and the default debates (after PM and Architect only).
2. **Stations are existing types:** the early stages are Agent pools (`barracks`) set to one role and `max_orcs: 1`
   (drawn as the one-bay depot, spec 14); implementation is an Agent pool with parallel bays; QA reuses the Test bench
   or a one-role pool. **No new building type** (process-lines.md §2).
3. **"Add a line from a template"** in the Build menu: shows the stations, the default debates and approvals, and an
   estimated price per task ("Analyst → PM → UX → Architect → Scrum master → dev → QA; debates after PM and
   Architect: ~$X or ~Y % of the window per task"), then lays a new quarter line (spec 06's "Lay a new line") and
   builds the stations on it with their roads.
4. **The split:** a station with `split: true` (the Scrum master) turns one incoming cart into several outgoing ones,
   one per story in its result (one per Markdown heading or list item, as the template's prompt asks), each with its
   own id and `parent` on its waybill.
5. **Debates in place:** a station with `debate: true` runs its result past 2–3 critic roles (reuse the Review
   board's member logic, `council` in `orkcraft/realm/`) before the cart moves on; the verdict and its cost are waybill
   rows; turning it on in the station's settings shows the price first.
6. **Approvals:** a station with `approve: true` holds the cart at the line's barrier until the person lifts it or
   sends it back with a note (back to that station, its round counted as today).
7. Prompts: `orkcraft/realm/line_templates/bmad/*.md`, one per role, short; the PM session checks them against
   BMAD's current published roles before merging.

## Tests
Critical tests, plus new `tests/test_lines.py` (the template loads; a fake run: one cart in, split into 3 story
carts with parents; debate and approve flags hold and release), `tests/test_camp_layout.py`, a browser test (the
template adds a line with its stations; a cart waits at a lowered barrier).

## Prompt
Use the prompt in docs/specs/README.md with `<NN-name>` = `15-bmad-line`.
