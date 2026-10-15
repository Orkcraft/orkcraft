# PM & marketing: handoff (15 October 2026)

The state a new product-and-marketing session starts from. Update it when you hand over again.

## The role and the owner's rules
- Senior PM and marketer for Orkline. Strict priorities: P0 / P1 / Later / No. Answer the owner in **Russian**.
- Design docs and specs are pushed straight to `main` without tests. **No code in the PM session**: development runs
  in separate sessions (create_session) that the PM session watches, reviews and merges.
- **No new sessions without the owner's word.** He decides when to spend on development.
- The Gemini key lives only in the environment secret `GEMINI_API_KEY`; image generation spends credits **only after
  the owner's explicit "yes"**.
- **Never run the agy CLI yourself.** The owner runs agy at home on `docs/specs/` (his account); the PM session writes
  the specs and reviews, tests, screenshots and merges the `spec/NN-*` branches. Headless helper and order: see the
  last messages of the previous session (worktree per spec, `agy -p`, `script -q` to keep a pty).
- Don't name the big strategy game or its characters anywhere.
- No model identifiers in commits, docs or anything pushed.
- Art: never re-pixelate generated images (CLAUDE.md "Art").

## Where things are
- Decisions: `docs/design/decisions-2026-10.md` §15–§25 (the camp's shape §20, timeline §22, process lines §23,
  negative feedback §24, settlement §25). Design system v3: `docs/design/design-system-v3.md`. Phone: `mobile.md` §13.
  First mission and charter: `first-mission.md` §11. `process-lines.md` (BMAD), `settlement.md`.
- Specs for agy: `docs/specs/README.md` (flow, models, rules, ordered list).
- Marketing: `docs/marketing/` (README: the launch has no fixed date; tester guide and invite, devlog 01, FAQ,
  Discord, places).

## State on 15 October
- HD sprites done and merged (`043322e`, `5889b9b`): every sprite cut once from the source to `@hd1/@hd1_5/@hd2`
  WebP, drawn 1:1 on dpr ≥ 2. Not converted: ground/track tiles, palisades, nine-slice kits, depot bays, faces,
  portrait heads (Later).
- Sessions: HD-ORKS `session_01CWnjWCfQe3DDQrcRwEZ8L6` (idle, done); art `session_01LH9oFPc3MsWB5z8qs6bW39`
  (told not to recut old art). Previous PM session: `session_01MGnfd3VpATycMySTQKmnRK`.
- The owner's next agy runs: spec **13** (home instead of Town Hall) and **01** (phone fast load, updated for the
  WebP cuts in `5dab93d`) in parallel; then **03** (charter, pro).
- Weekly usage limit resets Wed 21 October 11:00 UTC: keep sessions few.

## Waiting on the owner
- Play Mission 1 → fill spec 02 (Mission 1 blockers).
- Written IP confirmation.
- Whether to write the settlement specs (MVP).
- E1 clean-install check on Wed 21 October; release 0.3.0 (spec 05) on Thu 22 October; Halloween decor (spec 04)
  before 31 October; testers after that (timeline: decisions §22).

## Marketing next (P1)
- Tester wave: invite and guide are written; refresh the screenshots with the HD camp once 13 and 01 are merged.
- Devlog 02: the HD orks before/after (`docs/design/img/hd-orks/orks-before-4x.png`, `orks-after-4x.png`) is the
  strongest visual we have.
- Halloween post with the decor from spec 04.
