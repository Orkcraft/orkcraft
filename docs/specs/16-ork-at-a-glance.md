# Spec 16 — every ork at a glance: its state, its task, what it is doing now; the details inside

Branch `spec/16-ork-at-a-glance` · model **pro** · design: ork-console.md (§5 one status, §14 the lanes), decisions
§20.7 (📖 for readers), process-lines.md, spec 14 (an ork in every bay, an ork on every seat)

## The rule: two levels, calm by default
- **In the camp, at a glance (no click):** each working ork shows **its state by its pose** (working, asking ❓,
  stuck `!`/🔥, held ⏳, idle) and **a small phase icon** over its head: 📖 reading · ✏️ writing · 🧪 testing ·
  💭 thinking · 🌐 browsing · ⌨️ running a command. One icon, 16 px, no text, never yellow or red (those stay ❓ `!`).
- **The task's name** (2–3 words, as the keeper's bubble already says) shows **on hover of the ork or its building**,
  or for every ork at the close zoom steps (×1.5, ×2); never for all orks at the default step (eight bubbles over a
  depot would be noise).
- **Opening the building** gives the details per ork (below).

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
   today; the phase icon over the head (drawn by code from a tiny pixel set in `tools/ui_kit.py`'s manner, whole
   pixels); the task name bubble on hover / close zoom only.
3. **The building's panel, per ork** (the Agent pool's Work view, `js/buildings/barracks*.js`, and the council's
   view): a row per ork — face, name, state, the task (link to its waybill), **the phase now**, **the tools it used
   in this run** (the last 20: icon · tool · target · when, newest first), tokens and time so far, ⏹ stop softly, and
   **Open console**. Readers of a Wiki show 📖 here when their last read was from it (decisions §20.7).
4. Office: the same rows in its plain list (words, no sprites); the phase as a word ("reading", "testing").

## Don't
- Never store or show tool arguments beyond a path or a command's first word; never file contents.
- No new colours for phases; no animation beyond the existing frames.

## Tests
Critical tests, plus new `tests/test_phases.py` (the mapping; `latest`; a broken line skipped), the Warder's tests
(the hook still answers the same and only appends), `tests/test_gui_camp_browser.py` (a working ork shows its phase
icon; its task bubble only on hover; the building's row lists its tools), `tests/test_pwa.py` (phase in the compact
snapshot).

## Prompt
Use the prompt in docs/specs/README.md with `<NN-name>` = `16-ork-at-a-glance`.
