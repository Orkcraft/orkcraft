# Specs for agy: how the owner builds at home and the PM session checks

Status: 15 October 2026. The owner runs Google's official `agy` CLI at home on these specs (his own account, on his
own code: ordinary use). The PM session writes the specs, then reviews each branch, runs the tests and takes the
screenshots, and merges into `main` when it holds. (Orkline itself never wraps agy for this: decisions §5.)

## The flow

1. `git pull` on `main`.
2. Start agy in the repository with the spec's model and paste the spec's **Prompt** (below each spec).
3. agy works on the branch the spec names (`spec/NN-name`), never on `main`, runs the spec's tests, commits and
   pushes the branch.
4. Tell the PM session "spec NN pushed". It reviews the diff against the spec, runs the critical and browser tests,
   takes the screenshots, and either merges or writes a short list of fixes for a second agy run on the same branch.

## The model

- `gemini-flash-high` (cheap, good at code) by default: every spec says so unless it says otherwise.
- `gemini-pro-high` only where a spec says "pro": larger changes across several modules.
- `gemini-flash-low` for text-only changes (a release note).
Run `agy models` once to see the exact names your agy offers for these families.

## The daily rhythm (decided 16 October, the owner; decisions §34)

Three tracks, every day:
- **Product (the PM session):** priorities, specs, art cards, reviews, merges. Before each agy run it writes the
  **batch**: `docs/specs/batches/<date>-am.md` (the owner leaves for work) and `<date>-night.md` (the owner goes to
  bed): the agy tabs to open, each with its `<SPEC>` or art card, none touching another's files.
- **Art → agy, always 2–3 candidates** (agy often misses): the owner picks, the PM session cuts the pick once
  (CLAUDE.md "Art"), marks doorways, merges.
- **Code, split by difficulty:** easy specs → agy (in the batch); hard specs (caching, networking, security, data
  loss, multi-module, design-heavy) → Claude sessions the PM session starts with the batch and watches.

The owner opens the batch file, starts one agy tab per line, and goes. The PM session reviews what comes back
(light or full, as each spec says) and merges what holds; what does not gets a "Round N" list for the next batch.

## The prompt every spec uses

Start agy in the repository (`cd ~/orkcraft && git pull && agy`), pick the spec's model, paste this with `<SPEC>` =
the spec's file name without `.md` (e.g. `12-v4-remaining-screens`). Several specs at once: one terminal tab each.

```
git fetch origin. Make a worktree ../ork-<SPEC> on the branch spec/<SPEC>: if origin/spec/<SPEC> exists, start from it and merge origin/main into it; otherwise create it from origin/main. Work only in that folder.
Read CLAUDE.md, docs/specs/README.md (the rules, including "Before you commit"), then docs/specs/<SPEC>.md. A "Round N" or "Tonight's limits" section at the top comes first and wins. Do exactly what the spec says, nothing else.
Run the tests the spec lists, with --extra browser; all must pass. Do the four checks of "Before you commit". Commit with a short message in English, then git push -u origin spec/<SPEC>.
At the end print: the commits, the files changed, the tests run and their result, the four checks with their output, and anything you could not do.
```

## The art prompt (agy generates the images itself; no API key)

An art card (interiors.md §6, a spec's "Part A") is run in agy the same way as a spec, with this prompt and
`<CARD>` = the card's name (e.g. `s1-steampunk`), `<DOC>` = the file that holds it:

```
git fetch origin. Make a worktree ../ork-art-<CARD> on a new branch art/<CARD> from origin/main. Work only in that folder.
Read CLAUDE.md ("Art"), then the art card <CARD> in <DOC>. Look at every reference image the card names (open the files) and match their style, palette, pixel size and view.
Generate the image the card describes, 3 candidates, each a separate PNG, and save them as docs/design/img/references/v3/candidates/<CARD>/1.png, 2.png, 3.png. Do not resize, crop, re-pixelate or recolour what you generate.
Commit them with a short message in English, then git push -u origin art/<CARD>. At the end print the three paths and one line per candidate on what it shows and how it differs.
```

The PM session shows the owner the candidates, cuts the chosen one once (CLAUDE.md "Art") and merges.

## Before you commit: four checks (decided 16 October, after the first agy nights)

1. **Scope.** Run `git diff --name-only origin/main`. Every file must be one the spec allows. Revert any other change,
   however useful it looks: a fix the spec did not ask for goes in the final report as a suggestion, not in the code.
2. **Every new test can fail.** For each test you added: undo your fix (`git stash` the code, keep the test), run the
   test and see it **fail**, restore the fix and see it pass. Print both outputs. A test that passes without the fix
   proves nothing: rewrite it until it fails.
3. **Old tests are untouched.** Run `git diff origin/main -- tests/`. You may add tests and files; you may not remove
   or weaken an existing assertion, skip a test, or change an existing test's timing, waits, timeouts or flags. If an
   old test fails, the code is wrong, not the test.
4. **Look at what you made.** For a spec that changes what is drawn: take the screenshots after a fresh page load,
   open each one, and write one line per shot on what it shows. If it doesn't show what the spec asks, fix and retake.
   Two shots of different screens must never be the same file.

## The rules agy must keep (from CLAUDE.md, the essentials)

1. **Words.** In everything a person reads write *ork/orks*, never "orc"; *orkestration*, never "orchestration".
   Orks are called by their orkish names (the Mechanic, a Grunt, the Workchief); buildings by what they do (Task
   board, Agent pool, Review gate, External listeners). A visible word comes from `orkcraft/realm/lexicon.py` `TERMS`.
   **Code keeps its names:** identifiers, files, CSS ids, dict keys, event ids (`orc_id`, `barracks`, `warchief`)
   never change.
2. **Layers.** `orkcraft/core/`, `orkcraft/realm/`, `orkcraft/design/` never import from `orkcraft/gui/`. A service
   publishes on the bus (`core/bus.py`); it never shows a toast itself. Nothing imports Textual or Rich.
3. **Size.** Split a module before it passes ~600 lines.
4. **Looks.** Camp and Office are two looks of one GUI: a look changes drawing, never words. Camp-only styling is
   scoped under `[data-look="camp"]`. Office stays calm and monochrome.
5. **Signals.** Yellow and red are reserved for ❓, `!` and 🔥. Never use them for decoration.
6. **Art.** Never re-pixelate generated images (CLAUDE.md "Art"): cut once from the source with despill and one
   high-quality downscale to the device pixels drawn; no grid guessing, no palette reduction, no non-integer re-cuts.
   Everything sits on whole device pixels; no fractional transforms. `pixelated` only for code-drawn pixel art.
7. **Tests.** Always run the critical tests: `tests/test_architecture.py tests/test_cli.py tests/test_updates.py`,
   plus the test files the spec lists. Never skip, disable or loosen a test to pass.
8. **Don't** bump the version or touch `updates.json` unless the spec is the release; don't rename files; don't
   reformat code you don't change; don't add dependencies.

Run tests with: `uv run --extra gui --extra dev pytest -q <files>` (browser tests need Playwright's Chromium:
`uv run --extra gui --extra dev --extra browser playwright install chromium` once).

## Who builds: agy or Claude (decided 15 October, the owner and the PM; decisions §26)

Every spec says in its header who builds it, set by the PM when the spec is written:
- **agy** (the owner's Google quota): small specs in one area, with the files named and the tests listed — UI moves,
  wording, decor items, layout tweaks, release notes.
- **Claude** (a Claude Code session): caching, networking, security, data that can be lost, and every pro or
  multi-module, design-heavy spec. A flash miss there costs more review rounds than it saves.

**The night run.** In the evening the owner starts agy on its specs and one Claude session on its spec, never two
runs on the same files. In the morning the PM session reviews every branch the same way (diff against the spec,
critical and browser tests, screenshots) and merges or writes a fix list for a second round. Claude's own branch
gets a lighter review: it runs its tests itself.

**Who reviews.** Every spec also says how the PM session reviews its branch, chosen by risk, not by size:
- **light** — a cheaper Claude model as the review agent: small one-area specs (UI moves, wording, items, layout
  tweaks, release notes). It runs the same tests and screenshots; if it finds anything beyond nits, the branch goes
  to a full review.
- **full** — the main model: caching, networking, security, data that can be lost, and every multi-module spec.
Reading is cheap and writing is dear (output costs about five times input; re-read cached context costs a
twentieth), so a review mostly reads and costs little next to writing the code.

Every spec carries two lines, for agy above all: **"Change nothing outside these files"** (the files named), and
**a browser test that proves the behaviour**, not only strings.

## The list: only the three tracks (decisions §35, §36)

Work is only on these three tracks until the testers' numbers. Anything else is a one-line hypothesis in
open-questions.md "After the testers" (§36). Within a track, P0 first.

**Track 1 — the five buildings work** (Task board, Agent pool, Review gate, External listeners, Wiki)

| # | spec | priority | who builds | review |
|---|---|---|---|---|
| 26 | [five buildings at the first start; the others hidden](26-five-buildings.md) | P0 | **Claude** | light |
| 28 | [the lean Agent pool: fewer tokens for the same parallel work](28-lean-pool.md) | P1, after 26 and 27, before 17b | **Claude** | full |
| fix lists | one short spec per building from what the owner finds testing it (`docs/specs/fix-<building>.md`) | P0, as they come | agy or Claude | light |
| gate-kinds | the Review gate by what the result is: what goes to people one by one, code as one batch a day (decisions §39); the spec after the owner's tests | P1 | **Claude** | full |
| 22 | [the Agent pool's room](22-agent-pool-room.md) (art card + code) | P1, after the art | **Claude** | light + the owner's look |
| 23 | [the Review gate's room](23-review-gate-room.md) (art card + code) | P1, after the art | **Claude** | light + the owner's look |
| 16 | [every ork at a glance: state, phase icon, task on hover](16-ork-at-a-glance.md) | Later | **Claude** | full |

**Track 2 — it reads as a game** (the five buildings, the orks, the carts, the camp)

| # | spec | priority | who builds | review |
|---|---|---|---|---|
| art | [the five buildings in steampunk, outside and inside](art-steampunk-all.md) (kit + 5 sheets × 3 candidates) | P0 | agy | the owner picks |
| 18 | [darker, richer grass](18-darker-grass.md) (round 2 at the top) | P0 | agy | light |
| 19 | [Camp's camera](19-camp-camera.md) (no far zoom-out; the wheel scrolls down) | P0 | agy | light |
| 20 | [the wilderness composed](20-composed-wilderness.md) | P1, after 18 and 19 | **Claude** | light + the owner's look |
| 14 | [the modular depot (an ork in every bay)](14-modular-depot-and-small-pieces.md) (art card + code) | Later | agy | light |

**Track 3 — the first day** (install, onboarding, Mission 1); its dated items run alongside tracks 1 and 2

| # | spec | priority | who builds | review |
|---|---|---|---|---|
| E1 | [the clean-install check](e1-clean-install.md) (the owner runs it) | P0, Wed 21 October | owner | — |
| 05 | [release 0.3.0](05-release-0.3.0.md) | P0, Thu 22 October | agy | light |
| 27 | [Mission 1 in four quests](27-mission-four-quests.md) | P0, before 17b | **Claude** | light |
| 17b | [Mission 1 as a scene](17b-mission-scene.md) | P0, after 19 and 27 | **Claude** | full |
| 02 | [Mission 1 blockers](02-mission1-blockers.md) (filled after the owner plays it) | P0 | agy | light |
| 03 | [the charter: "My project"](03-charter.md) | P1, after 17b | **Claude** | full |

**Merged:** 01 and 01b (the phone's fast load), 12, 13, 13b, 17a, 21, 24, icon-hd, s1-steampunk.

**Parked as hypotheses (decisions §36):** 10 (the phone's new UX), 04 (Halloween), 06, 07, 08, 09 (the camp's
layout), 15 (BMAD line), 11 (Mission 1b), 12b. Their files stay; nobody builds them.
