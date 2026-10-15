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

## The prompt every spec uses

```
Read CLAUDE.md, then docs/specs/README.md (the rules), then docs/specs/<NN-name>.md.
Work only on the branch spec/<NN-name> (create it from main). Do exactly what the spec says, nothing else.
Run the tests the spec lists; all must pass. Commit with a short message in English, then push the branch.
At the end, print: the commits, the tests run and their result, anything you could not do.
```

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
6. **Pixel art.** Sprites drawn with `image-rendering: pixelated`, on whole device pixels; no fractional transforms.
7. **Tests.** Always run the critical tests: `tests/test_architecture.py tests/test_cli.py tests/test_updates.py`,
   plus the test files the spec lists. Never skip, disable or loosen a test to pass.
8. **Don't** bump the version or touch `updates.json` unless the spec is the release; don't rename files; don't
   reformat code you don't change; don't add dependencies.

Run tests with: `uv run --extra gui --extra dev pytest -q <files>` (browser tests need Playwright's Chromium:
`uv run --extra gui --extra dev --extra browser playwright install chromium` once).

## The list, in the order of decisions §22

| # | spec | when | model |
|---|---|---|---|
| 01 | [the phone's fast first load](01-phone-fast-load.md) | before the testers | flash |
| 10 | [the phone's new UX](10-phone-v4.md) (four parts: cards, motion, full view, v4 look) | right after 01 (the owner) | pro / flash |
| 02 | [Mission 1 blockers](02-mission1-blockers.md) (filled after the owner plays it) | before the testers | flash |
| 03 | [the charter: "My project"](03-charter.md) | before the testers | pro |
| 04 | [Halloween decor](04-halloween-decor.md) (art card + items) | before 31 October | flash |
| 12 | [the v4 kit on the remaining screens](12-v4-remaining-screens.md) (audit, then move) | before the testers | flash |
| 05 | [release 0.3.0](05-release-0.3.0.md) | Thu 22 October | flash-low |
| E1 | [the clean-install check](e1-clean-install.md) (the owner runs it, no agy) | Wed 21 October | — |
| 13 | [no Town Hall in the camp; the home's menu](13-home-instead-of-town-hall.md) | before the testers | flash |
| 06 | [three bands: the camp lays itself out](06-three-bands.md) | after Halloween | pro |
| 07 | [the person's quarter: drag in Camp](07-quarter-drag.md) | after 06 | flash |
| 08 | [the Wiki on the grass](08-wiki-on-grass.md) | after 06 | flash |
| 09 | [plots](09-plots.md) | after 07 | flash |
| 14 | [the modular depot (an ork in every bay), the small campfire and barrier](14-modular-depot-and-small-pieces.md) (art card + code) | after Halloween | flash |
| 15 | [the BMAD line template](15-bmad-line.md) | after 06 and 14 (medium priority) | pro |
| 11 | [Mission 1b](11-mission-1b.md) (three parts) | after the testers' feedback | pro |
