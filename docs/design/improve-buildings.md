# Design — Improve: the Mechanic and the Alchemist

Status: stages 0–6 built 2026-10-11 (the Improve group, the UX bench standing with its settings and gallery, the
road rule; a building's inputs; the Test bench's setup; environments, case sets and what is kept to spend less; the
virtual building; GitHub and pull requests; the UX bench painting pictures and laying windows out). Asked by the owner: tools inside the product that try a change to a building's logic or look, measure it
and keep it, **faster and cheaper than testing and rewriting it through Claude Code**.

| stage | what | state |
|---|---|---|
| 0 | Build's **Improve** group: *Logic* (the Test bench, a gear) and *UI/UX* (the UX bench, the flask); a type may lay roads only in its setup or none at all (`catalog.BuildingType.roads`); the UX bench stands: its settings (which building, which image tool) and its gallery, read only | built |
| 1 | Quick actions are inputs: each says the act a person's form ends in, and `core/inputs.press` ends in the same act, so a bench can press a button the way a person does (§3) | built |
| 2 | The Mechanic's setup: pick one building or drag a frame round several; the frame drawn on the map with its environment's name, a wire from the Mechanic to the scheme's start and one back from its end; the Test bench's roads are laid only by it (`roads = "setup"`) | built |
| 3 | Environments: a small code base and data written from a person's description, once, no network; case sets in them; the bare side kept, a series stopped early, a set's cost said before it runs (§5.2, §7) | built |
| 3b | Cassettes: MCP and outside calls recorded on a set's first run and played back after (§5.2) | |
| 4 | The virtual building: a change is tried on an overlay the Mechanic holds while it is connected; **Save changes** keeps the data part for good (§5.3) | built |
| 5 | GitHub: Connect GitHub in the mascot's menu (device flow); a code change goes as a pull request with its evidence (§4) | built |
| 6 | The Alchemist redraws: images through the image tool with the shipped prompts, a region marked and commented, Reset; the Work window's layout as a UI document (§6) | built |
| 7 | Cards s/m/l as UI documents, so the Alchemist redraws them too | |

## 1. Why

A person who wants a building to work better today has one way: open Claude Code on Orkcraft's source, read, edit,
run, look. Every round reads the code base again, nothing is measured against the bare AI tool, and the change lives
on one machine. The two Improve buildings do the same inside the product, with the context already gathered (one
building, its prompts, its window, its cases), every run measured, and the result kept locally or sent upstream as a
pull request that carries its own evidence.

- **The Mechanic** (the Test bench, `lab`; its ork the Tester): the logic — prompts, chains, scripts, models, code.
- **The Alchemist** (the UX bench, `ux_lab`, the Alchemy Tower in the Camp's spelling; its ork the Designer): the
  look — the building's icon and sprite, its window's layout, its cards. Its sprite was painted with the others on
  sheet 5 and waited under `ux_lab/` ([building-sprites.md](building-sprites.md)).

The interface says what a building does (Test bench, UX bench) and what its ork is (Tester, Designer); *Mechanic* and
*Alchemist* are the Camp's spellings the lexicon turns into those (CLAUDE.md, *One vocabulary, two looks*). This
document uses them as names for the two ideas.

## 2. Build and roads (stage 0)

- **The Improve group** stands last in Build (`js/build.js` `GROUPS`): **Logic** raises the Test bench (a gear, drawn
  in `tools/intent_sprites.py`), **UI/UX** the UX bench (the flask, the Test bench's before). Its icon in Office
  is a gear and a flask (`js/icons.js`).
- **Roads only from setup.** `BuildingType.roads`: `"free"` (every type before), `"setup"` (only its setup lays them:
  no road handle, no *Connect to…*, no road planner) or `"none"`. `core/roads.choices` offers nothing to or from such
  a building unless the setup asks (`setup=True`), and `gui/builder.lay_road` lays only what `choices` offers. Roads
  of an older town keep loading: the rule is checked when a road is laid, never when a scroll is read.
  - The UX bench lays none: it picks its building from a list (§6.1).
  - The Test bench turns to `"setup"` in stage 2, when its setup can pick a building or a frame of them; until then
    it keeps its roads, so testing a chain does not stop working in between.
- **Setup and settings.** *Setup* is what a building asks while it goes up (the Warchief's line,
  [select-a-building.md](select-a-building.md) §7); *settings* is what its window changes later. A road an Improve
  building needs is setup's.

## 3. Quick actions are inputs (stage 1, built 2026-10-11)

Before, a quick action (`building.quick` → a view's `ACTS` or a worker's `quick_action`) and a cart down a road
(`core/delivery.deliver` → `worker.receive`) were two paths, and most quick actions only opened a form in the page,
so nothing but a person could give a building that input.

- A building's **inputs** (`core/inputs.py` `of`): a cart down a road when its type takes carts (`ACCEPTS`), then
  each quick action that is one. `catalog.QUICK_INPUTS` says, per quick action, the act of its view a person's form
  ends in, the argument the text they give goes to, and what the press always sends (*New task* → `add`, `text`,
  lane `todo`); `None` for one that only changes what the window shows (open a file, flip a chart).
- `inputs.press(town, building, input, value, by)` ends in that same act, so a bench gives a building an input the
  way a person does. Each press is published (`bus.INPUT`: building, input, value, by) — the runs' recordings
  (§5.2) hear it there.
- The core holds no view: the face sets `town.presser` (gui/console.py); a town without one presses nothing.
- The GUI: `building.inputs` lists them, `building.input` presses one; a quick action that takes nothing presses its
  input from the Command Card as before.
- `tests/test_inputs.py` keeps it honest: every quick action is in the table, every act named is real.
- **Next (stage 2):** the Mechanic's wire into a scheme's first building names one of its inputs; a run presses it
  with the case's text.

## 4. GitHub (stage 5, built 2026-10-11)

- **Where:** *GitHub* in the mascot's menu (`js/github.js`, `gui/github.py`); not in the onboarding (nothing to send
  yet). The Test bench's pull request dialog says to connect when no account is.
- **How:** the Orkcraft Improve GitHub App (`orkcraft-improve`) with the **device flow** (`realm/github_app.py`):
  **Connect GitHub** shows the code GitHub gave and opens github.com/login/device; a thread asks GitHub every few
  seconds until it is typed (`slow_down` respected, an expired or refused code said). No client secret ships. The
  token is kept as the login `github-improve` (`realm/logins.py`: the keychain, else the logins file). **Disconnect**
  forgets it here. When the app is not on the person's own account the menu says so, with **Install**.
- **A pull request** (*Send to Orkcraft as a pull request…* on the virtual building's code change) is made with the
  API only, no clone: the person's fork (made when missing), a branch `improve/<type>-<time>` from Orkcraft's `main`
  with the changed files — each merged three ways (`git merge-file`) onto `main` as it is now when `main` changed it
  since the installed version, refused when both change the same lines — and the pull request into `main`, labelled
  `from-orkcraft` when the app may.
- **Its body is the evidence** (`realm/lab_pr.py`): the goal, the scheme, each case set (what its cases do and in which
  environment, never their inputs), the means against the bare AI tool on the runs made after the change, the files,
  and the settings tried with it. It may go only when the building is ahead on the goal's metric in most of the cases
  run with the change.
- **Before it goes** the dialog shows exactly what leaves the machine: the title, the body and the diff.
- **When the release brings it:** the bench's copy is of the version it was made on; a pull request is merged onto
  `main` as it is when sent. (Dropping the copy when an update carries the change is next.)
- Settings and prompts saved locally are not sent: they are the person's town's.

## 5. The Mechanic

### 5.1 Setup (stage 2, built 2026-10-11)

1. Build → **Logic** raises a Test bench, and the Warchief asks *What should it test?* (`js/buildings/lab.js`
   `Setup`): one press on a standing building tests it; **Frame several on the map** lets the person drag a frame
   (`js/frame.js` `FrameSelect`, a strategy game's selection) and the buildings it touches are picked; **Test them as
   one chain**. *Change what it tests* in its window asks again.
2. The picked buildings are put in the order their own roads take a cart (`LabWorker.scheme_order`): one first,
   one last, every one on the way, else it says they are not one chain. `set_scheme` takes its old roads up and lays
   the new ones as its setup (`roads.lay(..., setup=True)`): a `lab.case` road into the first (a chain) and a road
   back from the last. These are its only roads: the Test bench is `roads = "setup"`, so no handle, no *Listen to…*,
   no road planner reaches it.
3. What it tests is framed on the map (`js/frame.js` `Schemes`): a dashed frame round the buildings, as scaffolding
   is drawn, the environment's name on it (*this project* until stage 3 gives it environments) with the bench's name;
   the two roads are its wires in and out.
4. Fixed on the way: the town file refused to save a chain (its loop check did not know a `lab.case` road closes no
   loop, `scroll_checks.closes_no_loop` now says it for both), and a building raised by a double press in Build hid
   its setup under the line's hints.

### 5.2 Work (stage 3, built 2026-10-11)

- **Environments** stand as frames in the window (`js/buildings/lab.js` `Envs`), each with its **case sets**; the
  setup's, *this project* (a copy of the town's), first. **Add an environment** takes a sentence ("a tiny shop in
  Python, standard library only, with tests"); one call writes it (`realm/lab_envs.py` `env_prompt`: at most 24 files
  and 80k characters, no network, paths kept inside it), once. Its files are kept beside the building
  (`envs/<id>.json`) and every run of its sets starts from a copy of them (`bench.Case.files`).
- **A case set** (*Add a case set* in an environment): what its cases do there and how many (1–20). One call to a
  light model writes all of them, alike, each saying its set; **Run** runs them; the set's row says the means of its
  last run against the bare AI tool (time, tokens, quality, how many ran) and what running it again will cost on the
  building's side (`lab_envs.estimate`). The cases without a set stay below as *Single cases*.
- The frame on the map names the environment of the first set.
- **What to change** stays at the bottom (today's proposals, `realm/lab_cases.py`). **Apply** puts a change on the
  virtual building, never on the building in the town (stage 4).

**Cassettes (stage 3b, not built).** An AI tool's MCP servers and outside calls are its own, inside its process:
the bench cannot catch them from Orkcraft. The way in: in a run's copy, each AI tool is started with an MCP
configuration of the bench's only (`claude --strict-mcp-config --mcp-config <file>`, and each other tool's own way),
in which every server the person has is replaced by `orkcraft mcp-cassette <server>`: a stdio proxy that, on a
set's first run, passes each call to the real server and writes the call and its answer to the set's cassette, and
on every run after answers from the cassette and never starts the server. A call not in the cassette is answered
"not recorded" and noted in the run. Outside calls the building makes itself go through the same file by its URL.
Until then a run's copy has none of the person's sources (`bench_kits.SOURCES_OUT`), as before.

### 5.3 The virtual building (stage 4, built 2026-10-11)

A building's behaviour is data (its spec: `orders`, `chain`, `script`, `models`, its settings) and code (its worker
and prompt builders in Python).

- **Try it** on a proposal (*What to change*) puts it on the virtual building, never on the town's:
  - a **settings** or **prompt** proposal goes to the building's own keeper (`core/keeper.py` `ask`, the same model
    call and checks as *Ask the steward*), on the building as the bench has it now; its answer — the whole new
    config, checked like any spec — is kept by the Test bench (`lab.json` `virtual`), with its diff. The building it
    is tried on is the one the proposal's *where* names, else the scheme's first.
  - a **code** proposal is an agent's change in the bench's own copy of the package (`realm/code_overlay.py`:
    `<state>/code/orkcraft`, the package as installed, committed and tagged; the sprites linked). Its diff and files
    are one change.
  - a **roads** proposal is not tried: roads change on the map and in the setup.
- **The bench's runs stand the virtual building**: `flow_spec` / `chain_spec` give a run each building's config with
  every change tried on it (`LabWorker.virtual_spec`, the last ruling), and a run with a code change starts
  `orkcraft bench` with the copy first on `PYTHONPATH` — the installed app is never changed.
- **The virtual building** section lists the changes: what and why, *What changes* (the diff), **Take back** (a data
  change takes the later ones on the same building with it; the code change drops the copy).
- **Save changes** gives each building its data changes for good through its keeper (`keeper.apply`: checked again on
  the spec as it stands, saved, a checkpoint that undo takes back). Code changes stay with the bench: they reach the
  person only through a pull request (§4) and the release that carries it.
- The prompts the code builds today move to template files a step at a time (§9); each that moves becomes data the
  keeper can change without code.

## 6. The Alchemist

### 6.1 Settings (stage 0)

- **Which building:** picked from a list laid out as Build is (its groups, its icons), not from the map: a look is a
  type's, not one building's.
- **Image tool:** the AI tool and model that paints (default agy, with Gemini's images); any other tool the machine
  has is offered.

### 6.2 Work (stage 6, built 2026-10-11)

- **The gallery**: every picture of the type, small enough that the list stays short and big enough to read, each
  with a line saying what it is, grouped: *Icon* (its Build icon; its Office icon, a line drawing, shown only),
  *Sprite* (its house on each ground it is drawn for, its ork) and *Window* (its Work window as boxes). Cards come
  with stage 7.
- **A press on a picture** opens a dialog: the picture large on the left, what to change on the right.
  - Say what to change; **Paint it** asks the image tool once (`realm/painter.py`) in an empty folder holding the
    picture as it is (`reference.png`), with the shipped prompt for its kind (`design/prompts/icon.md`, `sprite.md`,
    `ork.md`: the style, the palette, the canvas, a transparent background) and the person's words; the tool writes
    `out.png`, checked to be a PNG of a sane size. The new picture shows on the left (a draft beside the building).
  - **Drag on the picture** to mark a region: the words then say what changes there, and the prompt asks for that
    region only, every other pixel kept.
  - **Reset** at the top: the left shows the shipped picture again.
  - **Apply** at the bottom: the draft becomes this machine's own picture (`design/tokens.py` `assets_dir`,
    `~/.config/orkcraft/assets/<path>`, its `@2x` too), which `/ds/` serves before the design system's — every town
    on this machine shows it; after Reset, Apply takes this machine's away.
  - A tool that makes no picture says so (*does agy make pictures here? Pick another in its settings*).
- **A press on the window** (a type whose window has more than one pane): its UI document as boxes on the left, what
  to change on the right; **Lay it out** is its steward's redesign (`realm/steward.py` `redesign`: one call, the
  contract, the components, the font and tone roles, `design/ui.py` `RULES`; checked, sent back once with its problems
  when wrong) on a building of the type. **Reset** drops the draft; **Apply** gives the layout to every building of
  the type (`core/buildings.py` `set_ui`, a checkpoint each). A type whose window is one pane today says so: its
  window is laid out when its view is split into panes.

## 7. Tokens: cheaper than Claude Code

The rule: **code does the loop, a model only writes what code cannot.** Every item below is measured in the run's
ledger (`.orkcraft/spend/calls.jsonl`, by `purpose`) so the saving is a number, not a claim.

1. **The bare side once** (built). The bare AI tool's answer to a case does not change when the building does: it is kept by
   (case, tool, model, environment) and run again only when one of those changes. A second run of a set costs half.
   `realm/bench.py` `bare_key` (the case's task, input, files and check, the tool and the tier — never the goal or
   the judge, which the bare tool does not see), `.orkcraft/bench/bare/`; a run that failed or was cut is asked again;
   `orkcraft bench --fresh` asks anyway. The report says *kept from run …*.
2. **Cassettes** (§5.2): MCP and outside calls recorded once, played back after; no tokens spent reading the same
   page twice.
3. **Only what changed runs again.** A run keeps each step's input and output by the hash of its input
   (`realm/steward_metrics.py` `replay` already plays a chain on recorded inputs). After a prompt change only that
   step and the ones after it run; the steps before are read back.
4. **Cases in one call** (built). N alike cases are one call to a light model that writes N, kept and reused; never N calls.
5. **Stop early** (built). Cases run in turn; when the building is clearly behind (or clearly ahead) after k of N, the rest
   wait. Before a run the window says what it will cost (N × the last run's mean). A series of 6 cases or more runs
   with `--stop-behind 3`: behind the bare tool on each of the first three, the rest wait.
6. **Checks before the judge.** A case's own check decides first; the blind judge, on a light model, only when the
   checks tie or there are none.
7. **Prompt caching on purpose.** The parts every call of a run shares (rules, the building's documents, the
   environment) go first and are marked for the cache; today caching is only priced.
8. **Patches, not rewrites; context gathered, not searched.** A proposal is a patch to one building's files, written
   from those files only — the step where Claude Code spends most, reading the repository to find them, is skipped.
9. **The Alchemist's layouts are checked by code** (built). A UI document is validated against its schema before it is drawn
   (`design/ui.py`), and drawn by the page without a model; a wrong one goes back once with its problems.
10. **Pictures: one picture, in an empty folder.** Each Paint is one call with the picture and its kind's prompt only —
    never the sheet, never the source to read; a region is said in words (its shares of the picture). A draft at a
    lower resolution first, the full one on Apply, comes when the image tool takes a size.

## 8. Decided

- The Mechanic is the Test bench grown, not a second building (asked 2026-10-11).
- Data changes are kept locally; code changes only through a pull request (asked 2026-10-11).
- The Alchemist paints with agy by default (asked 2026-10-11).
- The Alchemist starts with pictures and the Work window; cards follow once they are UI documents (asked 2026-10-11).
- GitHub through a GitHub App with the device flow, in the mascot's menu (asked 2026-10-11). The app is `orkcraft-improve`
  (github.com/apps/orkcraft-improve), its client id `Iv23ligmdXetPjrWsh4J` (not a secret: the device flow needs no client secret, and none ships). It asks for
  Contents, Pull requests and Administration (to fork) on the repositories it is installed on, has no webhook and no
  callback URL; a person installs it on their own account (for their fork) after signing in
  (github.com/apps/orkcraft-improve/installations/new), and Orkcraft finds the
  installation through the API.

## 9. Open

1. Which building's prompts move to templates first (stage 4): the Agent pool's, the most tested.
2. Does agy paint here, or does the image tool need its own key (stage 6)?
