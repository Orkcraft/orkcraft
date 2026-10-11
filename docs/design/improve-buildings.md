# Design — Improve: the Mechanic and the Alchemist

Status: stages 0–3 built 2026-10-11 (the Improve group, the UX bench standing with its settings and gallery, the
road rule; a building's inputs; the Test bench's setup; environments, case sets and what is kept to spend less). Asked by the owner: tools inside the product that try a change to a building's logic or look, measure it
and keep it, **faster and cheaper than testing and rewriting it through Claude Code**.

| stage | what | state |
|---|---|---|
| 0 | Build's **Improve** group: *Logic* (the Test bench, a gear) and *UI/UX* (the UX bench, the flask); a type may lay roads only in its setup or none at all (`catalog.BuildingType.roads`); the UX bench stands: its settings (which building, which image tool) and its gallery, read only | built |
| 1 | Quick actions are inputs: each says the act a person's form ends in, and `core/inputs.press` ends in the same act, so a bench can press a button the way a person does (§3) | built |
| 2 | The Mechanic's setup: pick one building or drag a frame round several; the frame drawn on the map with its environment's name, a wire from the Mechanic to the scheme's start and one back from its end; the Test bench's roads are laid only by it (`roads = "setup"`) | built |
| 3 | Environments: a small code base and data written from a person's description, once, no network; case sets in them; the bare side kept, a series stopped early, a set's cost said before it runs (§5.2, §7) | built |
| 3b | Cassettes: MCP and outside calls recorded on a set's first run and played back after (§5.2) | |
| 4 | The virtual building: a change is tried on an overlay the Mechanic holds while it is connected; **Save changes** keeps the data part for good (§5.3) | |
| 5 | GitHub: Connect GitHub in the mascot's menu (device flow); Save changes opens a pull request with its evidence (§4) | |
| 6 | The Alchemist redraws: images through the image tool with the shipped prompts, a region marked and commented, Reset; the Work window's layout as a UI document (§6) | |
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

## 4. GitHub (stage 5)

- **Where:** *Accounts → GitHub* in the mascot's menu (`js/portrait.js`); not in the onboarding (nothing to send yet).
  *Save changes* says how to connect when no account is.
- **How:** a GitHub App with the OAuth **device flow** (a code shown, the browser opened; no client secret ships).
  The token goes to the keychain as `github-<login>` (`realm/logins.py`, as Google's). Without it: the `gh` login,
  else a token pasted (`realm/quickadd.py` already reads both).
- **A pull request:** fork → branch `improve/<type>-<date>` → commit → PR into `main`, labelled `from-orkcraft`.
  Its body is the evidence: the goal, the cases (their descriptions, not the person's data), the metrics before and
  after against the bare AI tool, the changes in words. It can be sent only when the change is ahead on the goal's
  metric on most of its cases.
- **Before it goes:** a page shows exactly what leaves the machine (the diff, the case descriptions, the numbers);
  nothing from the person's project or environment's data is in it unless they tick it.
- **When the release brings it:** a kept change remembers the version it was made on. An update that carries the same
  change drops the local one; an update that changes the same place marks it *in conflict* and turns it off until
  the person looks.

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

### 5.3 The virtual building (stage 4)

A building's behaviour is data (its spec: `orders`, `chain`, `script`, `models`, prompt templates moved out of code)
and code (its worker and prompt builders in Python).

- **Data** changes live in an overlay the Mechanic holds (`.orkcraft/improve/<building>/overlay.json`); while it is
  connected the building runs with it. **Save changes** writes them into the building's spec for good (a checkpoint,
  undone as any), connected or not.
- **Code** changes are never loaded into the installed app. They run only inside a bench run (a subprocess with the
  changed modules first on its path, in the run's copy), and reach the person only through a pull request and the
  release that carries it (§4).
- The prompts the code builds today move to template files a step at a time, starting with the building tested most;
  each that moves becomes data the Mechanic can change without code.

## 6. The Alchemist

### 6.1 Settings (stage 0)

- **Which building:** picked from a list laid out as Build is (its groups, its icons), not from the map: a look is a
  type's, not one building's.
- **Image tool:** the AI tool and model that paints (default agy, with Gemini's images); any other tool the machine
  has is offered.

### 6.2 Work

- **The gallery** (stage 0, read only): every picture of the type, small enough that the list stays short and big
  enough to read — its Build icon, its house (each biome it has), its ork, then (stage 6) its window in each state
  and its cards s/m/l — each with a line saying what it is, grouped: *Icon*, *Sprite*, *Cards*, *Window*.
- **A press on one** (stage 6) opens a dialog: the picture large on the left, its changes on the right.
  - *A picture:* say what to change; it goes with the shipped prompt for its kind (`design/prompts/icon.md`,
    `sprite.md`, `ork.md`, moved out of [building-sprites.md](building-sprites.md) and [sprites.md](sprites.md)) and
    the current picture as the style to keep. Mark a region and comment it: only that region is painted again.
    **Reset** at the top brings back the first.
  - *A window or a card:* say what to change; the Alchemist rewrites its UI document
    ([design-system.md](../design-system.md), the roles and components only) and the left side draws it with the
    sample data of the state. A region marked and commented changes only that part. **Reset** too.
  - **Apply** at the bottom closes the dialog; the gallery shows the new one.
- **Kept locally:** pictures in `~/.orkcraft/assets/<type>/` served before the shipped ones (`/ds/`), layouts as the
  building's UI document (`BuildingSpec.ui`, already in the scroll). Sent upstream the same way as the Mechanic's (§4).

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
9. **The Alchemist's layouts are checked by code.** A UI document is validated against its schema before it is drawn
   (`design/ui.py`), and drawn by the page without a model; a wrong one goes back once with its problems.
10. **Pictures: draft, then final.** A low-resolution draft first; the full picture only on Apply. A region comment
    sends the region and its mask, not the whole sheet.

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
