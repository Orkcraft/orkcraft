# Spec 16 — every ork at a glance: working or not, and its tool on its apron; every task inside the building

Branch `spec/16-ork-at-a-glance` · model **pro** · design: ork-console.md (§5 one status, §14 the lanes), decisions
§20.7 (📖 for readers), process-lines.md, spec 14 (an ork in every bay, an ork on every seat)

## The rule: two levels, calm by default (the owner, 15 October)
- **On the map:** only **whether an ork works or not**, by its pose (working / idle), plus the signals that already
  exist (❓ asking, `!`/🔥 stuck, ⏳ held). **No phase icon, no task bubble at the default step** (the task's name on
  hover of the ork or its building stays, as the keeper's bubble does today).
- **The harness on its apron:** every ork wears a small **patch on its apron** saying which tool runs it (Claude
  Code, agy, Codex, Hermes, pi, Cursor), so a mixed camp reads at a glance. The patch is **the harness's own mark**
  (`orkcraft/realm/harnesses.py` `mark`: ✻ ✦ ⌬ ☤ π ◆) **on a muted colour of its own** — not the vendors' logos (they
  are trademarks), and never a signal colour: the harnesses' UI colours that are yellow or red (Claude's amber, pi's
  red) get a muted map tone instead (e.g. Claude a dark terracotta, pi a plum), checked by `tests/test_design.py`'s
  signal check. At the default step the patch is a coloured square of 4×4 art px; at the close steps (×1.5, ×2) the
  mark shows in it. A legend of the patches sits in the building's panel and in the Agent pool's settings.
- **Opening the building shows everything per ork and per task** (below).

## Do
1. **The phase, from the tools the session calls** (core, no face):
   - The Security reviewer's `PreToolUse` hook already sees every tool call of a Claude Code session
     (`orkcraft/hooks/warder.py`, installed by `hooks/install.py`). After its own decision, append one line to
     `<repo>/.orkcraft/phases.jsonl`: `{ts, session, tool, target}` (target: the file path or the command's first word;
     never the command's arguments, never file contents). Never fail the hook; never slow it beyond a file append.
   - A new pure module `orkcraft/realm/phases.py`: `phase_of(tool, target)` → `read | write | test | think | web |
     run` (Read/Grep/Glob → read; Edit/Write/NotebookEdit → write; Bash whose first word is a test runner (`pytest`,
     `npm test`, `go test`, `cargo test`, the project's test command) → test; other Bash → run; WebFetch/WebSearch →
     web; no tool call for > 20 s while running → think); `latest(root, session)` → the newest phase and the last 20
     tool lines.
   - The host puts each working ork's `phase` into the snapshot (where its status already is), published on the bus;
     the phone's compact snapshot gets it too.
2. **The camp** (`js/camp/orks.js`, the depot's bays and the council's seats from spec 14): the pose by state as
   today; **the apron patch** drawn by code over the ork sprite at an `apron` anchor added to each ork sprite's
   manifest row (measured once, like the doorways: the middle of the apron), whole pixels, under the signals' layer;
   no phase icon on the map; the task name bubble on hover only.
3. **The building's panel, per ork and per task** (every task the building holds, running or queued, as a row) (the Agent pool's Work view, `js/buildings/barracks*.js`, and the council's
   view): a row per ork — face with its apron patch, name, its harness and model, state, the task (link to its waybill), **the phase now**, **the tools it used
   in this run** (the last 20: icon · tool · target · when, newest first), tokens and time so far, ⏹ stop softly, and
   **Open console**. Readers of a Wiki show 📖 here when their last read was from it (decisions §20.7).
4. Office: the same rows in its plain list (words, no sprites); the phase as a word ("reading", "testing").

## Don't
- Never store or show tool arguments beyond a path or a command's first word; never file contents.
- No new colours for phases; no animation beyond the existing frames.

## Tests
Critical tests, plus new `tests/test_phases.py` (the mapping; `latest`; a broken line skipped), the Warder's tests
(the hook still answers the same and only appends), `tests/test_gui_camp_browser.py` (a working ork shows its apron patch and no
phase icon on the map; its task bubble only on hover; the building's row lists its tools), `tests/test_pwa.py` (phase in the compact
snapshot).

## Prompt
Use the prompt in docs/specs/README.md with `<NN-name>` = `16-ork-at-a-glance`.
