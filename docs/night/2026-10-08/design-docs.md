# Night 2026-10-08 — designed, not built (P1, product manager)

First version, pushed at the start of P1; P1 refines it during the night (checks each item against the
code). Format and rules of taking an item: `plan.md` → Queues. P2, P3, P4 take the **highest open build
item**, build it to its design doc, update that doc's status line and *As built*, merge.

How it is ordered: what a newcomer meets first and what the owner already agreed, then what makes later
cuts decidable by numbers, then small finishing steps of half-built designs. Everything that needs a
real outside service, a phone app or a live AI tool to check is *not now*: a night session cannot prove
it works, and an unproven integration costs more than it gives.

## Build — take from the top

- [ ] B01 Landscape stage 1: the flag and the catalog — `landscape` on the seven types (Router, Transformer, Drop file here, Inspector, File tree, Metrics, Sound alerts), the Wizard/Build menu's two groups, `custom` out of the list, the term in `TERMS` — `realm/catalog.py`, `realm/lexicon.py`, `gui/static/js/build.js`, tests of the catalog and wording — S/M — [landscape.md](../../design/landscape.md) §2, §6, §9.1; agreed with the owner today; a newcomer meets 13 buildings and 7 things of the land instead of 21 metaphors
- [ ] B02 Simplify stage 0a: a `purpose` on every charge — `telemetry.charge(..., purpose=)` from the closed list, transcript runs carry it in their env, `.orkcraft/spend/calls.jsonl` one line per call kept by the housekeeping's log limit — `sources/telemetry.py`, the callers of `charge`, `realm/halt.py`/`jobs.py` env — M — [simplify.md](../../design/simplify.md) §2; nothing in simplify can be cut until the week's numbers exist, so every day without the ledger delays the whole design
- [ ] B03 Simplify stage 0b: *By purpose* in the Spend window — the last 7 days, $ and tokens per purpose, per building inside — `gui/views/` Spend view + its JS — S — simplify.md §2; after B02
- [ ] B04 Landscape stage 2: who looks when land breaks — failures and 👎 of landscape wake the downstream steward or the Warchief; the land's own keeper never runs — `core/workers/*` of the seven types, `realm/steward.py` — M — landscape.md §4, §9.2; after B01
- [ ] B05 Landscape stage 3: the look — land as sprites without cards on the map, hover, a small window, smoke on failure; Camp and Office checked in the demo with Playwright — `gui/static/js/town.js`, CSS — M — landscape.md §5, §9.3; after B01 (stage 4, the Transformer without `agent:`, rewrites saved specs: see N01)
- [ ] B06 Mine next §2.2: the mind is the model that answered — confirm a finding by two different *models* (as each tool reports the model), not two harness names — `core/workers/mine.py`, `realm/` mine helpers, `tests/test_mine.py` — S — [mine-next.md](../../design/mine-next.md) §2.2; the Mine's whole promise is "two different minds", and today two harnesses on one model count twice
- [ ] B07 Steward at work §4: a road rule's own tier as `own` — above the tier picked for `listen` and above the goal's — `realm/steward.py` `pick`, the rule's settings, `tests/test_steward_work.py` — S — [steward-at-work.md](../../design/steward-at-work.md) §3, §4.4; finishes a half-built design
- [ ] B08 Simplify stage 1: the Review board leaves `council` — the words of §3 in `TERMS`, the GUI and the docs (code names stay) — `realm/lexicon.py`, GUI text, docs — S/M — [simplify.md](../../design/simplify.md) §3, §5; one concept, one word
- [ ] B09 Simplify stage 4a: the watchers that need no model — Pacer, Treasurer, Peon from records the town already keeps; `realm/council.py` → `realm/watchers/` with a thin import — M — simplify.md §6; the Alchemist waits for a week of B02's ledger
- [ ] B10 Agent pool stage 4a: the Lookout names the kind (§6.1) — M — [barracks-flows.md](../../design/barracks-flows.md) §6.1, §12.4; the roadmap's next item for the pool
- [ ] B11 Agent pool stage 4b: the `doc` path with `debate` and `doc_to` — M — barracks-flows.md §6, §12.4; after B10
- [ ] B12 Road sound §3: a sound on each event of a road (the 🔊 picker on the row, kept in this machine's settings, not in the scroll) — built-in sounds and the person's own file only; the voice pack (§4, §5) is N05 — M — [road-sound.md](../../design/road-sound.md) §3; check first that its branch did not already land it

## Not now — with the reason

- [-] N01 Landscape stage 4: the Transformer loses its `agent:` step — rewrites saved specs (the only stage that does); last by the design itself; needs the owner awake for the migration's first real town
- [-] N02 Watchtower automation (all 7 stages: IMAP IDLE, Slack Socket Mode, `orkcraft watch`, tunnels, webhook registration) — each needs a live mail / Slack / GitHub account to prove; the quick-add and polling cover today's need
- [-] N03 Mobile stages 3–4 (relay, APNs/FCM, daemon) and Phone places stages 2–3 (the app's geofence, Wi-Fi/car signs) — need the native app and infrastructure; the host side of stages 0–2 is done and waits for the app
- [-] N04 Catapult MCP phase 4 (carriers beyond Claude Code) — waits for each tool's headless check, by the design itself
- [-] N05 Road sound §4–§5, the voice pack — generated audio assets (TTS, Stable Audio): a person must listen to them
- [-] N06 Mine next §2.1 (agy searches the web), §2.3 (a live smoke test), §4 (usage proxy) — need live AI tools and spend real quota; §3.1–§3.6 are ordered by what the smoke test shows, so they wait for it
- [-] N07 Simplify stages 2–3 (the Elders into the steward; the cuts of §7) — stage 3 waits for a week of B02's numbers by the design; stage 2 changes who decides at night, an owner's call
- [-] N08 agy guard (research note): its live check needs agy installed and signed in
- [-] N09 Watchtower MCP paths stages 1–3 — set aside by the owner on 2026-10-08 (§11)

## Already built (status lines to check)

- codex-limits.md §5.1–§5.2: `quota/codex_quota.py`, `pricing.codex_usage_cost` exist — P1 checks and fixes the status line
- yards.md: its branch `claude/great-cray-5i993w` is merged into `main` (#131) — P1 checks and fixes the status line
