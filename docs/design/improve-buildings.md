# Design — Improve: the Mechanic and the Alchemist

Status: stage 0 built 2026-10-11 (the Improve group, the UX bench standing with its settings and gallery, the
road rule). Asked by the owner: tools inside the product that try a change to a building's logic or look, measure it
and keep it, **faster and cheaper than testing and rewriting it through Claude Code**.

| stage | what | state |
|---|---|---|
| 0 | Build's **Improve** group: *Logic* (the Test bench, a gear) and *UI/UX* (the UX bench, the flask); a type may lay roads only in its setup or none at all (`catalog.BuildingType.roads`); the UX bench stands: its settings (which building, which image tool) and its gallery, read only | built |
| 1 | Quick actions are inputs: a press is a cart with `kind: "quick.<id>"` through `core/delivery`, so a bench can press a button the way a person does (§3) | |
| 2 | The Mechanic's setup: pick one building or drag a frame round several; the frame drawn on the map with its environment's name, a wire from the Mechanic to the scheme's start and one back from its end; the Test bench's roads are laid only by it (`roads = "setup"`) | |
| 3 | Environments: a small code base and data written from a person's description, once, no network; cassettes for MCP and outside calls (§5.2) | |
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

## 3. Quick actions are inputs (stage 1)

Today a quick action (`building.quick` → a view's `ACTS` or a worker's `quick_action`) and a cart down a road
(`core/delivery.deliver` → `worker.receive`) are two paths. Stage 1 makes one:

- A building's **inputs** are its roads' events (`ACCEPTS`), its quick actions and the text a person gives it.
- A press of a quick action is delivered as a cart `{"kind": "quick.<action id>", ...}`; a worker's
  `quick_action(id)` becomes its `receive` for that kind (the Mill's *Run on the last input* already is one).
- So a bench gives a building a press the way a person does, and a run can be recorded and played again (§5.2).

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

### 5.1 Setup (stage 2)

1. Pick one building, or drag a frame round several (a strategy game's selection of units): the selected ones are
   the scheme, its first building is where the input goes, its last where the result is read.
2. Describe the environment in plain words ("a small Python service, no network, three failing tests"). It is
   written once (§7.4) and named; the scheme is drawn framed on the map — like the scaffolding — with the
   environment's short name on the frame, a wire from the Mechanic into the scheme's first building and one from its
   last back to the Mechanic. These two are the only roads it has.

### 5.2 Work

- **Environments** stand as frames in the window, each with its **case sets**; the setup's is the first.
- **A case set** (a dialog like today's *Add a case*): what the cases do in this environment, how many (the Tester
  writes that many alike, the more the steadier the comparison), **Run**; after a run, the mean of each metric over
  its cases against the bare AI tool.
- **Cassettes:** in a run every MCP call and outside call goes through a recorder. The first run records the answers
  (as the Catapult's `route.json` does, [catapult-mcp.md](catapult-mcp.md) §4); later runs play them back, so the
  two sides see the same world and nothing outside is touched or paid for twice.
- **What to change** stays at the bottom (today's proposals, `realm/lab_cases.py`). **Apply** puts a change on the
  virtual building, never on the building in the town.

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

1. **The bare side once.** The bare AI tool's answer to a case does not change when the building does: it is kept by
   (case, tool, model, environment) and run again only when one of those changes. A second run of a set costs half.
2. **Cassettes** (§5.2): MCP and outside calls recorded once, played back after; no tokens spent reading the same
   page twice.
3. **Only what changed runs again.** A run keeps each step's input and output by the hash of its input
   (`realm/steward_metrics.py` `replay` already plays a chain on recorded inputs). After a prompt change only that
   step and the ones after it run; the steps before are read back.
4. **Cases in one call.** N alike cases are one call to a light model that writes N, kept and reused; never N calls.
5. **Stop early.** Cases run in turn; when the building is clearly behind (or clearly ahead) after k of N, the rest
   wait. Before a run the window says what it will cost (N × the last run's mean).
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
