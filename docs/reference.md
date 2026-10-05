# Orkcraft — reference

_The detailed reference. Start with the [README](../README.md). Old `MGTUI_*` / `ORCRAFT_*` environment variables (from the project's earlier names) still work as fallbacks for `ORKCRAFT_*`._

A terminal harness and orkestrator for multi-agent work in any git project, in an
RTS (Warcraft) metaphor, built to cut the operator's cognitive load: windows are
**buildings** with a resident **ork**, agents are the **clan**, the HUD shows
resources, and agents never pop dialogs — they raise a 🔥 and wait for orders.

```
┌─[ 🧌 Orkcraft v0.1 ]──[ ⚙️ Menu (F10) · 🛑 READY ]──── [🪙 $— / $20.00] [🪵 — / 128k] [🥩 0/5] ─┐
│ ·   ,   ·   .   "   ·  ↟  ·   ,   .   ·   "   ·   .   ·  ↟  ·   ,   ·   .   "   ·   .   ·   ↟   │
│ ,  ┌─ 📌 [1] ⚒️ Forge ─── [🧌 Smith 💤] ─────┐  ·  ┌─ [2] 📦 Loot Chest ────────────────────┐   │
│    │ [TASK-102] AST Parser refactor        │     │ ▾ 📁 wiki/architecture/                    │   │
│ ·  │ Status: 💤 Idle                       │  ·  │   📄 core-eventbus.md                      │   │
│    └───────────────────────────────────────┘  .  └────────────────────────────────────────────┘   │
├─────────────────────────────┬───────────────────────────────┬─────────────────────────────────────┤
│ 🗺️ WAR MAP (Orkspaces)       │ 🧌 CLAN ROSTER (Garrison)     │ ⚒️ COMMAND CARD (Context Actions)   │
│ [F1] 🏰 Main Camp (forest)  │ ▼ ⚒️ Forge (Garrison: 1)      │ [B] 🏗️ Build Window (Mason & Artisan)│
│                             │   • 🧌 Smith          💤 Idle │ [P] 📜 Window Presets Catalog       │
│                             │ ▼ ⚔️ Warband (0)              │ [S] 🧌 Summon Ork / Warband         │
│                             │ ▼ 🏛️ Council (5)              │ [T] 🌲 Toggle Terrain (Dim / Black) │
│ ─────────────────────────── │ ───────────────────────────── │ ─────────────────────────────────── │
│ [+] [N] New Orkspace        │ [Space] Fold   [1-9] Select   │ [Esc] Deselect / Neutral Mode       │
└─────────────────────────────┴───────────────────────────────┴─────────────────────────────────────┘
```

## Orkcraft core

- **HUD**: logo, 🛑 Halt All state, ❓ count, 🪙 Gold (`$— / $20.00` budget limit), 🪵 Lumber
  (`— / 128k` budget limit), 🥩 Supply (running orks / 5). The menu and Halt All share one segment at the left,
  `[ ⚙️ Menu (F10) · 🛑 READY ]`: a click opens the system menu (Halt All is its item `[1]`),
  and it shows the halt state (`HALTED — n stopped`).
- **🛑 Halt All** — `space` (in neutral state when the focused widget does not use space) or
  `ctrl+p` (always, even inside a terminal): interrupts every running Claude / agy / Codex session
  (SIGINT — the CLI cancels its turn, the session stays) and stops everything else the camp runs —
  road agents, Barracks orks and their steward, a Clan Fire review, the wiki's librarian, Mill and
  Workshop scripts, tests, a Catapult's browser and scouts, every model call (`realm/halt.py` kills
  each process with its children). Queues hold: the Barracks and the Catapult pause, a Mill and a
  Clan Fire wait for the next cart or ▶. The TUI stays open.
  Textual's command palette moved to `ctrl+k`.
- **The Console** (lower RTS console 33/33/33):
  - **War Map** (left): camp / orkspaces (F1–F8, biomes, alerts marker `❓`), creation hint `[N]`.
  - **Clan Roster** (centre): accordion roster in Neutral (`space` folds/unfolds, garrison members listed under their building with lead marked ★), building garrison in Building
    (numbered `[1]..[9]`, keys 1..9 select), ork card in Unit (name ★ if lead, status, orders, trigger, deployment state, prompt question, terminal steps).
  - **Command Card** (right): context-sensitive capital letter actions per focus state; clickable rows.
- **Focus State Machine**:
  - **Neutral**: default base state (`Esc` or click on empty canvas/terrain); Command Card: `B` Build, `P` Presets, `S` Summon, `T` Terrain.
  - **Building**: activated window or number key `1`–`9`; Command Card: `R` Recruit Ork, `L` Chronicles, `Y` 🛤 Listen to another window (road), `U` 🚧 Remove the incoming road, `P` Pin/Unpin, `M` Window Mode, `X` Demolish.
  - **Unit**: ork selected in roster; Command Card (residents): `C` Deploy / Open Session, `T` Orders & Trigger, `D` Dismiss, `H` Halt, `L` Unit Chronicles (+ `Enter` ❓ Resolve Alert); Command Card (workers/council/builders): `C` Chat/Orders, `L` Chronicles, `T` Triggers, `H` Halt.
- **Chronicles 📜 [L]**:
  - **Building Chronicles** (`L` in Building state): append-only audit log of building mutations (`.orkcraft/history/buildings/<id>.events.jsonl`), newest first with timestamp, icon, sentence and author; date separators on day changes; `Esc` / `q` closes.
  - **Unit Chronicles** (`L` in Unit state): runs on the left (40%, numbered `#001`..`#NNN` chronologically, listed newest first with metrics: duration, 🪵 Lumber context tokens, 🪙 Gold, ✅/❓/🛑 outcome), ReAct protocol on the right (60%, list of step titles; `Enter` expands detail below, `D` sends diffs to Scrying Spire 🔮, `R` resumes the run in War Tent 💬, `Esc` / `q` closes).
- **Roads 🛤**: roads are drawn on the canvas — faint in the gaps between windows, brighter for the
  selected building, and the selected road over the windows with a label. Gates sit on the frames
  (`▶◀▲▼` exit, `●` entry) and stay clickable even when the road is hidden. Click a road or a gate for
  its card (event, filter, handler, carts): `H` handler, `U` remove, `Esc` back. `Y` in Building state
  subscribes **this** building to another one: possible sources highlight, press the source's number,
  then pick the event and the handler (or plain). `U` removes the building's only incoming road.
  `preferences.roads = "off"` hides the gap roads (gates stay). Plain roads still show on the source frame as `[ 🚩 ──► <target> ]` (selection pipe) or `[ 🚩 ⏹──► <target> ]` (task-completed pipe), positioned after the title and before the garrison badge. On selection change, selected nodes or Loot files are routed to the receiver (e.g. Scrying Spire 🔮); on task completed, finished deployment sessions deliver reports to Scrying Spire or Loot Chest 📦 (`./loot/pipes/`).
- **Passive alerts ❓ & Awaiting Orders (`!` / HUD click)**: a session showing a numbered menu or confirmation prompt (Claude's / agy's / Codex's permission and question prompts; a Codex menu is answered with the digit and Enter) and tickets with open `## Clarification Needed` for the human turn their ork ❓ and increment the HUD `[ ❓ N awaiting orders ]` badge. Nothing pops up automatically:
  - Clicking `[ ❓ N awaiting orders ]` in the HUD or pressing `!` opens the **Awaiting Orders** modal (`AwaitingOrdersModal`).
  - Displays all pending questions to the user in a list (`#orders-list`), showing the origin unit/ticket, the full question, and context lines.
  - Numbered keys `1`..`9` or `y`/`n` answer the currently selected question immediately; action buttons also support mouse clicks.
  - `T` jumps straight into the session terminal in the War Tent; `C` opens the node card.
  - Answering dispatches input back to the agent session or updates the ticket, advances to the next pending order, and cleanly closes when all questions are resolved (`Esc` cancels).
  - **Question Interception from Claude, AGY & Codex**:
    1. *Real-time Terminal PTY Screen Scraping (`detect_prompt`)*: Claude Code, AGY and Codex run in virtual pseudo-terminals (`pyte` on PTY). When output goes quiet for 1.0s (`PROMPT_IDLE_S`), Orkcraft scans recent screen lines for numbered option menus (`1.`, `1)`, `[1]`, `(1)`, `1 -`) and yes/no confirmation dialogs (`[y/N]`, `(y/n)`). This intercepts tool execution approvals, question tools, and CLI confirmations without requiring modifications to the underlying agent binaries.
    2. *Tool & Hook Interception*: AGY's `ask_question` tool invocations and Claude CLI turns record structured parameters in transcripts (`transcript.jsonl` / `sessions.jsonl`), enabling extraction of rich question metadata.
    3. *Warder Security Interceptions*: Guardrail denials from `warder.jsonl` create operator review alerts.
- **Unit Frame**: every building shows its garrison on the top-right border
  `[ 🧌 Lead+N 🔨 ❓ ]` (lead name, `+N` for other members, lead's trigger icon, status: ❓ if any alert, ⚙ if any busy, else lead status); a click on it — or the building's number key pressed again, or `T` on the lead —
  opens the unit's orders: context and trigger (🔨 On Demand, 🕒 Cron, ⚡ Webhook),
  kept in the Town Scroll. Orks act on them from stage 5.
- **📌 Pin** (`alt+b` / Command Card `P` in Building mode): the window keeps its slot — no drag,
  no keyboard moves, no tiling, kept through layout resets and restarts.
- **Move / resize** without window mode: `alt+h/j/k/l` or `alt+arrows` move,
  `alt+shift+h/j/k/l` / `alt+shift+arrows` resize.
- **Viewports**: ≥140 cols Full RTS (Console + windows) · 100–139 Compact (Console + windows) ·
  <100 Minimal (the active building fills the screen; `Tab` / `1`–`9`); `ctrl+b` toggles the Console in any mode.
- **Town Scroll** `.orkcraft.json` (workspace root, gitignored; `ORKCRAFT_LAYOUT_FILE`
  overrides): Town Scroll v3 data contract (`schemas/town-scroll.v3.json`) holding orkspaces
  (F1–F8, biomes), buildings, pins, geometry, incoming roads (source, event, source filter,
  handler), garrisons (a steward and road handlers: chain / script / agent / hybrid with a
  harness scheme) and budget limits — see `docs/design/roads-and-orcs.md`.
- **Roads** (`realm/roads.py`): events leave a building only through its outgoing roads and their
  source filters; plain roads deliver at once, chain handlers rerun on every event with the latest
  payload of each of their roads, agent handlers wait for a quiet period and restart on new data
  (Claude read-only in the repo, Codex in the repo in its read-only sandbox with web search off unless asked
  for, agy in an empty sandbox dir, within the 🪙 budget). Personal nodes
  never reach a model. Script handlers run once reviewed (`python3 -I`, the records as JSON on stdin) and are held again when the file changes. Build requests from
  `[B] Build Window` queue in `.orkcraft/build-requests.jsonl` for Mason & Artisan (stage 4).
- **⚙️ System Menu (`F10`)**: opens `⚙️ SYSTEM & CLAN OPERATIONS` (`[1-6]` action, `Esc` cancels):
  - `[1]` 🛑 Halt All Operations
  - `[2]` 📸 Capture Screenshot (SVG screenshot without menu saved to `./loot/screenshots/`)
  - `[3]` ⌨️ Keybindings Cheat Sheet (two-column scrollable reference; also opened with `?`)
  - `[4]` 🌲 Toggle Terrain (`alt+t`: toggle Dim biome terrain vs pure Black canvas)
  - `[5]` 💾 Save Town Scroll (`.orkcraft.json`)
  - `[6]` 🚪 Quit Orkcraft (graceful quit)
- **Graceful Quit (`q` / menu [6])**: saves the Town Scroll (`.orkcraft.json`); if sessions are actively running in the War Tent, prompts with `QuitConfirm` (`[Y] Quit` / `[N] Stay`), terminates running terminals on confirmation, and cleanly exits.

Buildings (keys `1`–`9`):

| # | Building | Resident | Shows |
|---|---|---|---|
| 1 | 📦 Artifacts | Quartermaster | `./loot/` artifacts and wiki notes |
| 2 | 🏰 Town Hall | Chieftain | its agents and the last audit · Sessions (live Claude / agy / Codex terminals) · Limits (claude / agy quota) |
| — | 🏛️ Systems | Engineer | multi-agent pipelines and their schemes |

Every other building is built from the catalog of typed buildings (below) or by Mason & Artisan.

## Town view (default)

Every building of the canvas is a **hut** on the map, drawn as its own silhouette: a mill with
sails, a watchtower under a roof, a forest of trees on a long hall, a pit with its pipe. Above it
stand two or three lines — its number, icon and the resident ork's state (🔥 when it waits for
orders, and the whole frame turns orange), then its name. The silhouette is the building: a frame
with live status lines in it (the big ones start with a fixed heading of what the building is for —
`WORKER POOL`, `MERGE ENGINE`, `TELEMETRY & TELEGRAPHS`…). Under it, up to two quick-action buttons.
Roads and carts run between the huts.

| Footprint | Buildings |
|---|---|
| small, 10 wide | ⚙️ Mill (sails) · 🎯 Catapult (arm) · 📯 Horn (a horn and its sound) · 🕳️ Pit (5 wide, a pipe; its status stands under it) · 🚏 Signpost (a post with two boards: the last route, the number of routes; DIS / WAY while it has none) |
| 🗼 Watchtower (12 wide) | a roof over what is new per source: `gmail    3`, `slack  99+`, `jira   ERR`; more than four → `+2 more` |
| halls, 18 wide, 7 lines | 🌾 Task Fields · 🏕️ Barracks · 🪔 Clan Fire · ⚒️ Forge · 🗑️ Scroll Dump |
| complexes, 26 wide, 9 lines | 🥁 War Drum · 🌲 File Forest · 📦 Loot Vault · 🪨 Tally Crag (and the 🏰 Town Hall) |
| panorama, 60 wide | 🌊 Lake of Insight: two panes, the diff and what it is |

A view fills the slots with `hut_lines(widths)` (else its three `mini_status` lines); the shapes
are in `realm/silhouettes.py`. New huts are laid out on shelves — rows filled left to right, each
spread over the width — and keep the spot you drag them to.

- Click a hut → it is selected: the hut lights up and the console below turns to that building,
  the map stays as it is. Click it again (or press its number) → the building opens over the map.
  One building is open at a time; a click on another hut closes it and selects that one. `esc`,
  a click on the map or a click on the open building's hut closes it. Opening never moves a hut, so the roads stay where they are.
- Drag a hut to move it; its spot is kept in the Town Scroll (`buildings[].hut`).
- **Calm console**: in the town the console floats over the map's bottom edge instead
  of taking rows from it. With nothing selected only the War Map shows (bottom left — a 🔥 on an
  orkspace tells you an ork there waits for orders) and the **🏰 Town Hall** (bottom right, on
  every canvas, never moved or demolished) with its two buttons: **📜 Preset** (pick what you need,
  name it, place it) and **🛠 New** (build from scratch with the Builder); `B` opens the whole build menu. Select a building, an ork or a road and the
  garrison and Command Card slide in; `esc` hides them. The huts live above the calm strip, so
  nothing on the map moves; the open building shrinks to stay clear of the console.
- **Garrison, Info, chat**: the garrison lists names and states only (⚙ busy, 💤 idle,
  🔥 waiting). The **Info** column next to it tells in up to three sentences what the selected
  ork, building or road does — put together from the scroll and the roster, no model call — its
  models (✻ Claude, ✦ agy, ⌬ Codex, P script, 🪧 a free chain, ● the live session's model) and what it cost
  (🪙 $ and 🪵 tokens from the handler's run log, the live session's spend from telemetry; "no data
  yet" when unknown). Picking an ork keeps the garrison and lights the ork. A burning ork opens
  its question at once; any other garrison ork or live session opens its **chat**: a tall
  column on the right (45 % of the screen, the rest stays low) with its live session mirrored —
  the line below types into it (`/` jumps there) — or its last runs and a line that starts a
  Claude session with its orders and your message; below, its earlier sessions, Enter reopens.
- **A waiting ork sets its hut on fire**: the fence flickers orange and red, 🔥 on the hut, in
  the War Map, the roster and the HUD. The question itself (`!`, `Enter`) opens with ❓.
- `alt+v` switches to **tiles** (every window open side by side, the table below) and back; the
  choice is `preferences.view`. Minimal mode (narrow terminal) shows one window full size.
- Built-in buildings say what their hut shows (`hut_lines()` / `mini_status()` of the view). A custom
  (panes) building has a plain frame of its size (XS 10×5 · S 14×7 · M 18×9 · L 26×11) and may wear
  a roof (gable, thatch, tiles, pagoda, dome, castle, tent, chimney, flag, snow); it carries a `mini`
  block — up to three templates over its own data. Templates read `{count}`, the first row's fields,
  `{last}`, `{heading}`… with an optional `where` filter. Artisan writes it with the rest of the spec;
  masonry checks it like the rest.

## Buildings: the camp

A new camp starts with the **🏰 Town Hall** alone; every other building is built from it —
`P` lists the 16 camp buildings by what you need, asks for this building's name, icon,
description and settings, and lets you place it (no model call); `B` (🏗 on the Town Hall) also
builds one **from scratch** or lets the Foreman prefill one from a description — see
[Town Hall pipeline](#town-hall-pipeline). A building is a **type** from the catalog
(`realm/catalog.py`) plus a spec in `.orkcraft/buildings/<id>.json`: its title and icon (they stand
above the hut), up to two **quick actions** (buttons under the hut, `[` / `]`), the **events** it
sends down roads and its settings. Each camp type has its own silhouette (see Town view).

```
1. INTAKE AND ROUTING      🕳️ Pit ─► ⚙️ Mill            🗼 Watchtower ─► 🚏 Signpost   📯 Horn
2. QUEUES AND WORK         🌾 Task Fields ─► 🏕️ Barracks ⇄ 🪔 Clan Fire       🥁 War Drum
3. STORAGE AND INSPECTION  🌲 File Forest   🗑️ Scroll Dump   🌊 Lake of Insight   ⚒️ Forge
4. RESULTS AND EGRESS      📦 Loot Vault    🪨 Tally Crag    🎯 Catapult
```

| Building | Resident | Takes | Sends |
|---|---|---|---|
| 🕳️ The Pit | Scavenger | drag-and-drop files, pasted links / text, 📋 the clipboard; sorted by kind, kept in `.orkcraft/pit/` | `drop.file`, `pit.link`, `pit.text` |
| 🗼 Watchtower | Lookout | IMAP mail (read-only; `host: gmail`), GitHub events (`gh`), `feeds`: comments and mentions in Slack, Jira, Confluence and Figma, a schedule (`every 15m`, `daily 05:00`), webhooks on 127.0.0.1 (optionally signed); `intent`: only what you are after; new ones marked, ✓ reads all | `mail.received`, `watch.github`, `watch.comment`, `watch.mention`, `watch.cron`, `watch.webhook` |
| 🚏 Signpost | Grot Pointa | anything; rules (`route: contains …`, `matches`, `kind`, `source`, `field == value`, `else`) pick a route, each road waits for its own; a `totem` of old (and its `totem.routed` roads and Horn lines) loads as a Signpost | `signpost.routed`, `signpost.unmatched` |
| ⚙️ The Mill | Miller | anything; a map over each cart, strictly in order — `grep`, `replace`, `csv`, `json`, `extract`, `sort` (numbers as numbers), `filter` (`gt`/`lt`… on numbers and ISO dates), `template`, `script: …` (clean environment plus the names in `env`), `agent: …` for what a script cannot do and `script: … \|\| agent: …` when it fails; what arrives while it mills waits in a queue | `mill.done` (one per cart), `mill.item` (a flat map: one cart per record), `mill.failed` |
| 📯 The Horn | Hornblower | anything; plays a sound per event (`mail.received: chime`, `gate_pit/pit.link: alarm`, `gate_pit: ding`, `*: none`): horn, chime, alarm, drum, ding, the terminal bell or an audio file of yours; Enter walks a row to the next sound, 🔇 mutes, quiet hours (`22:00-08:00`), a cooldown | `horn.sounded` |
| 🌾 Task Fields | Taskmaster | a board of cards in `TASKS.md` or a folder: tasks in To Do / In Progress / Done, sticky notes in lanes of their own (Ideas, Questions…); `mode`: `board` · `tasks` · `notes`; `n` `<` `>` `e` `c` `t` `s` `d` `N` (below); a cart becomes a card | `tasks.created`, `tasks.status_changed`, `notes.created`, `tasks.sent` |
| 🏕️ Barracks | Grunts | tasks (a cart, or one you write with ✍ New task: a title and a brief), each on its own branch: a follow-up goes to the ork who did the earlier part, a new one to an idle or newly hired ork (provider and model by record); related work resumes the ork's session. The steward keeps the rules (`orders`), answers `QUESTION:`s or asks you (🔥), reviews (`test_cmd`, then the diff; ≤`max_reworks` reworks) and pushes the branch with a pull request — for code (always) and documents that go out; an ork never posts to a service itself (Jira, Confluence, Slack…): it drafts the post under a `PUBLISH: <where>` line, and `pool.question` carries the draft, the report and the files — 🔥 Enter publishes it (or type what to change), and through a 📦 Loot the cart is always held: accept lets the ork post it (your edits included), rework sends it back; `pool.done` then brings the report, the files and the link; a local document (a War Drum meeting's prep, or what the steward marks `SCOPE: local`) gets no PR and needs no commit when it is a meeting's | `pool.assigned`, `pool.done`, `pool.failed`, `pool.question`, `pool.idle` |
| 🪔 Clan Fire | Chieftains | a document (a cart — usually a Barracks result — or ▶ with a path or text): each member reviews it from its role (`APPROVE` / `CHANGES:` / `VETO:`), reading the repo and the web; the steward decides by its brief — let it go, send it back, or 🔥 ask you (your answer outranks the brief). The document is data, never orders. A veto from a `veto` role blocks approval; after `max_cycles` reworks of one title the operator decides. Briefs are files: `steward.md` and `roles/<role>.md` in `.orkcraft/council/<id>/`; documents that come mid-review queue | `team.approved`, `team.rework`, `team.artifact_ready` |
| 🥁 War Drum | Drummer | an `.ics` file or URL: now, next, the day and the week; + adds an event. `lead` (2h) before a meeting it sends `event_upcoming` once, tagged `[meet:<id>]` (📄 sends it at once); a cart back with the tag (Barracks' `pool.done`) is the meeting's document: 📄 at the meeting, Enter shows it in a Lake of Insight | `calendar.event_due`, `.day_schedule`, `.event_added/removed`, `.event_upcoming`, `.doc_opened` |
| 🌲 File Forest | Woodcutter | a folder as a tree with previews; Enter picks a target; ↗ opens it in the OS | `files.changed`, `files.selected` |
| 🗑️ Scroll Dump | Scroll Scrapper | one LLM wiki per topic (`codebase`, `team`, `design`, `general`) from read-only `sources` (folders of notes, `code:` folders, `git:<rev>[:<folder>]`, `confluence:<SPACE>`); ingests by itself, a module at a time, commits, keeps people's pages theirs, has a Clan Fire spot-check; `i` ingests now, `l` lints, `x` stops; a cart is a task and goes on with the wiki's map | `knowledge.changed`, `knowledge.chunks`, `wiki.updated`, `wiki.linted`, `wiki.review` |
| 🌊 Lake of Insight | Seer | a diff (side by side), Markdown, a file, a URL (as text), a branch (its diff); ↗ browser. A text file on disk (Markdown, code, a patch) is edited in place: `e` or ✎ opens the editor — fix the text, leave your notes in it; it saves by itself every `autosave` seconds (default 5) while there are changes and whenever the editor loses focus (another window, another building); `ctrl+s` saves at once, `Esc` saves and goes back to the view. A file changed on disk meanwhile is never overwritten by an autosave: the head says ⚠ and `ctrl+s` writes your text over it. Line endings and the file's mode stay as they were | `lake.viewed`, `lake.saved` (the edited file, once you leave the editor) |
| ⚒️ The Forge | Smith | branches with PRs and +/−; ⚒ (or a cart naming a branch) tests it in a throw-away worktree and squash-merges it into the base | `git.commit`, `git.pr_*`, `forge.merged`, `forge.conflict` |
| 📦 Loot Vault | Quartermaster | the review checkpoint on a road: by its rules a cart passes or is held; accept, send back for rework (≤ 3 rounds, then 🔥 needs you), restore rejected files; the chain's tokens and cost | `loot.passed/rework/needs_you`, `generator.accepted/rejected`, `loot.stored` |
| 🪨 Tally Crag | Crag Carver | spend, tokens, runs (`.orkcraft/ledger.jsonl`), quotas used, busy orks, tasks, CPU, numbers by road — vertical or horizontal Unicode bars | `charts.threshold` |
| 🎯 The Catapult | Loader | waits for every road in `wait_for` (fan-in), checks a JSON Schema, sends over HTTP(S) with a token from the environment — shots queue one at a time — or, in browser mode, its ork finds the intent's forms, fills them in turn and repairs a script the site broke; 🧪 dry run | `catapult.sent`, `catapult.failed`, `catapult.repaired` |

- **🌾 Task Fields is a board of cards** — tasks and sticky notes on one board
  ([design](design/fields-board.md)). A **lane** is a column: the three status lanes (To Do, In
  Progress, Done) hold **tasks**, every other lane (Ideas, Notes, Questions…) holds **notes**. What a
  card is follows its lane: a note moved into a status lane becomes a task (`tasks.created`), a task
  moved out becomes a note. A card has a title, a text (its indented lines in the file) and a colour
  — the square its title starts with: 🟨 🟩 🟦 🟥 🟪.
  - **`mode`** — `board` (default) shows every lane; with no lanes of notes it looks as it always
    did. `tasks` shows only the kanban; `notes` only the wall of stickers (a cart that arrives
    becomes a note there). **`lanes`** names lanes of notes that are always on the board
    (`["Ideas", "Questions"]`); any other `##` section of the file is one too.
  - **Keys** in the open building: `n` a new card in the focused lane · `<` `>` move it to the next
    lane · `e` or Enter open it (the first line is the title, the rest its text; ctrl+s keeps it) ·
    `c` the next colour · `t` a note ⇄ a task · `s` send it down the building's roads (`tasks.sent`,
    its title and text — a Barracks takes it as a task, a Clan Fire reviews it) · `d` delete it ·
    `N` a new lane of notes. The quick actions are + New task and 🗒 New note.
  - **The file** stays plain Markdown in git, one `##` section per lane:

    ```markdown
    # My tasks

    ## To Do
    - [ ] Plan the v0.2 release
      freeze on Monday, tag on Thursday
    - [ ] 🟥 Renew the domain

    ## Done
    - [x] Town Hall audit

    ## Ideas
    - 🟨 A calendar roof
      the War Drum's hut shows the next meeting
    ```

    What comes before the first `##` is kept, and so is every lane — the board never drops a
    section it does not know. In a folder (`path: tasks`), `todo/`, `in-progress/` and `done/` hold
    the tasks and any other subfolder (`ideas/`) is a lane of notes, a card a file whose text
    follows its `# title`.
  - **Events**: a task added, or a note that became one → `tasks.created`; a task moved between
    statuses → `tasks.status_changed` (its id); a note added → `notes.created` (its title and text);
    `s` → `tasks.sent`. Cards edited in the file by hand are seen on the next look (10 s).
  - The hut counts the status lanes and the notes (`🗒 3 notes`), `*` for what is new.
- The Forge and the Catapult act without asking; `c` in the open building turns a confirmation
  on (the `confirm` setting). The Town Hall's 🔍 Audit flags a Forge without tests and a
  Catapult without a schema.
- **The Catapult's queue.** A shot is one group of carts: with `key` (a body path such as
  `version.tag`) carts naming the same value share a group, so two releases never mix; a cart
  without it joins the newest group still missing its source. `ttl` (minutes) drops carts that
  waited too long. A group that has everything `wait_for` names becomes a shot and joins the queue;
  shots fire one at a time, in order, and a cart loaded meanwhile is never lost. A failed shot
  takes its group with it: 🎯 fires it again.
- **The Catapult's browser mode** closes a whole intent on a site with no API (a new event in the
  Google Play Console: the event, then its images, …). Install it with
  `pip install 'orkcraft[browser]'` and `playwright install chromium`, then set `mode: browser`
  and `forms`, in the order they are filled — `name = start address | what to open | button`
  (the last two optional): `event = https://play.google.com/console/… | the form for a new event`.
  - **`s` Scout**: the building's ork walks the site to each form itself, headless, with the
    building's own browser profile. Each step it sees the page (fields, buttons, links) and clicks
    one numbered element; it never types, never submits and refuses what looks like it changes data
    (delete, publish, send…). When the form is open it names its submit button. The form's map
    (fields with label, kind, options and a stable selector; the clicks since the last page load;
    the button) and its `fill.py` go to `.orkcraft/scripts/<id>/forms/<name>/` — in the camp's git,
    so every scout, mapping and repair is a commit `Z` can revert. One model call a step, at most 12.
  - **`l` Log in** opens a visible browser with that profile: log in once (the login stays in
    `.orkcraft/catapult/<id>/profile`; the Catapult adds `.orkcraft/` to the project's
    `.git/info/exclude` so it never reaches your git). If the ork cannot find a form, open it in
    that window yourself before closing it: a form with no map yet keeps the way you showed.
  - **A login page** (a password field, or another host) met by a scout, a shot or a repair sets
    the hut on fire 🔥: the lead ork waits for orders ("log in again"), the shot goes back to the
    front of the queue and the queue holds. Answer 1 (or `l`), log in, close the window: the queue
    goes on.
  - **Which field gets what**: `fields` first (`Event name = title`, `Category = "Major update"`;
    `images/Banner = banner` for one form only), then a model's mapping (`m`, every form: one call
    to your Claude Code, for labels in another language; its cost is in the ledger), then plain
    name matching. 🧪 Dry run shows each form's plan with the values, the required fields left empty
    and the keys nothing took.
  - **Files**: a file field takes a project file (`loot/banner.png`, or `loot:loot/banner.png`),
    or an http(s) URL (downloaded first, 50 MB at most). A file a Loot Vault still waits for you to
    review is refused until you accept it (`a` in the Vault).
  - **A shot** runs each form's `fill.py` in turn: it opens the form by its address, or the start
    page and the remembered clicks; fills it; then presses the button (`finish: press`) or hands the
    form to you (`finish: leave`, `f`: you check it, press and close the window, and the next form
    opens). `fill.py` runs by hand too (`python fill.py --profile … < cart.json`); edit it freely —
    a script edited by hand is kept, a rescout writes `fill.new.py` beside it.
  - **When the site changes** and a script breaks (a field or a button not found, the clicks no
    longer open the form), it reports where it broke with a snapshot of that page. The ork repairs
    the map from it: at most two model calls, never in the sandbox or past the 🪙 budget; only data
    comes back (a path on the same site, labels, selectors, known field kinds) and a renamed field
    keeps its old name for `fields`. `fill.py` is rewritten, checked headless (the form reached,
    every field found) and committed, and the shot resumes at that form — the forms already filled
    are not filled twice. A failed repair restores the old script and sends `catapult.failed`; a good
    one sends `catapult.repaired` with what changed. `repair: false` turns it off.
  - 🛑 Halt All stops the running browser; the queue waits for 🎯. The hut's line starts with 🌐 in
    browser mode. Fields inside iframes are not marked yet. The 🔍 Audit flags a Catapult that
    presses submit with no schema and no confirmation.
- The Watchtower's `feeds` are asked every two minutes over HTTPS, read-only (those services send
  webhooks only to a public URL). One line a feed; options name environment variables, never the
  token itself:

  ```yaml
  host: gmail                  # imap.gmail.com: an app password, IMAP on (also yandex, icloud)
  user_env: GMAIL_USER
  password_env: GMAIL_APP_PASSWORD
  feeds:
    - "slack: token=SLACK_TOKEN channels=C0123,D0456"     # a user token: search:read, *:history, users:read
    - "jira: site=acme.atlassian.net user=ATL_EMAIL token=ATL_TOKEN"            # jql=… takes the rest
    - "confluence: site=acme.atlassian.net user=ATL_EMAIL token=ATL_TOKEN spaces=DOC"   # cql=… too
    - "figma: token=FIGMA_TOKEN files=AbC123,XyZ789"
  ```

  A mention, a direct message, a Jira or Confluence @-mention, a reply to your Figma comment →
  `watch.mention`; any other new comment or message → `watch.comment` (its title starts with the
  service). Your own messages are skipped; each feed's first look only marks what is there as seen.
- The same services can **push** instead (no two-minute wait): the Watchtower's webhook listens on
  127.0.0.1 only, so give it a public address with a tunnel (`cloudflared tunnel --url
  http://127.0.0.1:8787`, ngrok, tailscale funnel; `smee.io` for GitHub) and point each service at
  its path. `secret=` on the service's `feeds` line names the variable that holds its secret (a
  line with only `secret=` listens and never asks); without it, `webhook_secret_env`:

  | Path | Where to set it | How it is checked |
  |---|---|---|
  | `/slack` | Slack app → Event Subscriptions (user events `message.channels`, `message.im`; `app_mention`) | the signing secret: `X-Slack-Signature`, five minutes at most; `url_verification` answered |
  | `/jira` | Jira → System → Webhooks, event *comment created*, with a secret | `X-Hub-Signature` (HMAC-SHA256) |
  | `/figma` | Figma Webhooks v2, `FILE_COMMENT`, with a passcode | the passcode in the body |
  | `/confluence` | an Automation rule → *Send web request*, header `X-Orkcraft-Token` | the token |

  A delivery becomes the same item a feed would find (sent once, however it came): Slack messages
  and Jira comments, Figma comments; your own are skipped, and a mention is told by who you are
  there — learnt by that service's polled feed, or from Slack's delivery itself. An Automation
  rule sends the simple form `{"id", "title", "text", "url", "author", "mention"}`; other paths stay
  a raw `watch.webhook`.
- **One tower, an intent.** Rather than a tower per source, give one tower every source and say what
  you listen for: `intent: user feedback about the app`. The Lookout puts each new signal (the
  schedule's aside) to the Fast Path's light model, twenty at a time, fenced as data it must not
  obey; what matches goes down the roads with its reason (`🎯 a user complains about login`), the
  rest stays in the list, dimmed and read. With the Fast Path off everything passes, and the head
  says so.
- **New and read.** A signal is new (• in the list, counted on the hut) until Enter reads it, ✓
  *Read all* clears them, ✉ opens the newest new one. What was there at the first look is listed,
  not new; an intent's misses are never new.
- **Later** — open questions, not built yet:
  1. *A tower that never sleeps.* It hears only while orkcraft runs; a background `orkcraft watch`
     (a service) would poll, take webhooks and write `signals.jsonl`, the TUI only reading it. Today
     a webhook's 202 also goes out before the signal is written.
  2. *Prompt injection.* Signals are strangers' text and travel on to Barracks and the Clan Fire.
     The intent's judge fences it, but the agents downstream do not yet: mark carts from outside as
     untrusted, let agents act on them only for allow-listed people, or ask before acting.
  3. *A secret required* for `/slack`, `/jira`, `/figma`, `/confluence` (today: optional).
  4. *OAuth* for Gmail's API and Microsoft 365 (Outlook has no password IMAP; Workspaces often
     forbid app passwords) — with tokens refreshed and kept safe.
  5. *Fully automatic.* The tower runs its own tunnel, registers its webhooks, logs in through the
     browser and heals itself — the plan, in stages: [design/watchtower-automation.md](design/watchtower-automation.md).
  6. *Checked against the live services.* Proven on recorded answers only: Slack's `search.messages`
     for `<@id>`, Confluence's CQL `mention`, Jira's `search/jql` comments and its webhook signature,
     Figma's `FILE_COMMENT` fields, Slack's 2025 history limits for apps outside the Marketplace.
- The Horn plays its sounds through the system's player (`afplay`, `paplay`, `pw-play`, `aplay`,
  `ffplay`; `winsound` on Windows); with none of them the terminal bell rings. The built-in sounds
  are synthesized once into `.orkcraft/horn/sounds/`; every call (heard or kept quiet, and why)
  is in `.orkcraft/horn/<id>/calls.jsonl`.
- The Scroll Dump is an **LLM wiki**: no retrieval of its own (Claude Code and agy search files
  well) — its librarian ork turns the sources into a wiki once and keeps it current, so knowledge
  accumulates instead of being searched for from scratch. **A wiki is a topic, not a building**:
  `topic` picks the sections and rules it starts with — `codebase` (architecture, modules, flows,
  decisions, how-to, glossary), `team` (teams, process, product, decisions, onboarding, glossary),
  `design` (components, screens, decisions, tokens) or `general` — and `wiki` its folder (default
  `llm-wiki/<topic>/`). A project may keep several, one Scroll Dump each; a wiki is never another
  wiki's source.
- **Built for thousands of pages and fast search.** `WIKI.md` holds the rules (edit them);
  `index.md` maps the sections, each `pages/<section>/` has its own `index.md` and `CLAUDE.md`
  (the section's rules — Claude Code loads them when it works there), and a section past ~40
  pages splits into subfolders with their own maps, so an agent walks index → section → page.
  Every page has front matter (`kind`, `aliases` — every name the thing goes by, `sources`,
  `updated`, `owner`) and an answering first paragraph: what grep hits. `CLAUDE.md` and
  `AGENTS.md` at the wiki's root point agents in. Ingest takes a module at a time (sources
  grouped by folder, ≤60 per run) and goes on by itself until all are in.
- **Ingest runs by itself** once the sources have stayed unchanged for a while (`auto_ingest`,
  default on; `ORKCRAFT_WIKI_AUTO=0` turns it off everywhere). What is new is judged by content
  (a hash, a git blob, a page version), not by mtime; a source that fails to answer (Confluence
  down, a revision gone) never makes its pages "gone"; a source unreadable right now waits for the
  next run, and you are told. `x` stops the librarian; the manifest moves on only on success.
- **Pages are shared.** A page with `owner: human` in its front matter (or `<!-- manual -->`) is
  the people's: the librarian reads it and writes suggestions in `proposals.md`; if it touches the
  page anyway the harness puts it back and says so. A page with edits not yet committed is
  protected the same way for that run. Files outside the wiki that change while it works are
  reported.
- **Every change is committed** (`commit`, default on) — the wiki's folder alone, authored by
  `Scroll Scrapper (orkcraft)`, so the Barracks' worktrees see it and `git log` tells the ork's
  edits from people's. Snapshots in `raw/` stay out of git (`raw/.gitignore`); `raw/manifest.json`
  goes in.
- **The Clan Fire spot-checks.** After each ingest `review_sample` pages it wrote (default 2) go to
  the 🪔 Clan Fire named in `council` as one document: its members review it from their roles and
  its steward approves it or sends it back (a spot-check never waits for you); the review shows in
  the Clan Fire, its report lands in `reviews.md`, which the next ingest reads. Without `council` the
  sample goes out as `wiki.review` (roads cannot loop, so a verdict cannot come back on one).
- **The steward closes the loop.** When a building's agents go into a wiki by themselves (tool
  calls naming its folder, ≥3 in a week) and no road brings it, the steward of that building
  proposes, without a model: the wiki's `knowledge.chunks` into the building, and the building's
  own sources routed through the wiki — then each task arrives with the wiki's map.
- The librarian runs on `harness` (`claude`, default, `codex`, or `agy` — agy's sandbox sees only the
  wiki's folder, so give it snapshot sources) with `model`. Nothing is written before the first
  ingest.
- The sources are strings: `docs` (or `fs:docs`) a folder of Markdown notes, `code:src` a folder of
  code, `git:main` or `git:v2.0:docs` a revision read through git, `confluence:ENG` a Confluence
  space (the site in `ORKCRAFT_CONFLUENCE_URL`, or `confluence:ENG@https://acme.atlassian.net/wiki`;
  signed in with `ORKCRAFT_CONFLUENCE_EMAIL` + `ORKCRAFT_CONFLUENCE_TOKEN`, or
  `ORKCRAFT_CONFLUENCE_PAT`). Remote pages are cached in `~/.cache/orkcraft/scrolls/` and
  refetched in the background every 15 minutes; a failed fetch keeps the cache. The older `paths`
  setting still works. The sources are only read.
- Specs of the earlier building types load as their camp buildings (`mail` → Watchtower, `tasks` → Task
  Fields, `git` → Forge…; an Agent / Script becomes a Mill step or a one-ork Barracks); event ids
  are unchanged, so old roads keep working.
- `orkcraft --demo --demo-set dashboard` opens all of them on four canvases (My Day, Agent Yard,
  Gates, Library — three LLM wikis, code, team and design, that tasks pass through) in a real git
  repository; agents never run there and the Catapult only dry-runs.

## Windows (tiles view)

| Action | Mouse | Keyboard |
|---|---|---|
| Focus a window | click it / its taskbar tab | `1`–`9`, `alt+1..9`, `F9` / `shift+F9` |
| Switch orkspace | click row in War Map | `F1`–`F8` |
| New orkspace | click `[+] [N]` in War Map | `N` |
| Move | drag the title bar | `ctrl+w`, then `←↑↓→` |
| Resize | drag the `◢` corner, bottom or right edge | `ctrl+w`, then `shift+←↑↓→` |
| Snap to a half | — | `ctrl+w`, then `h` `l` `k` `j` (left/right/top/bottom) |
| Snap to a quarter | — | `ctrl+w`, then `y` `u` `b` `n` |
| Maximize / restore | double-click the title | `ctrl+w`, then `f` |
| Center / tile all visible | — | `ctrl+w`, then `c` / `t` |
| Hide / show | click the active window's taskbar tab | `ctrl+w`, then `x`; any focus key shows it again |
| Link / pin Preview | — | `ctrl+w`, then `p` |
| Road into this building | — | `Y` in Building state, then `1`–`9` source |
| Select a road | click | a road cell or a gate; `H` handler, `U` remove, `Esc` back |
| Remove the only incoming road | — | `U` in Building state |
| Chronicles | — | `L` in Building or Unit state |
| Save / reset layout | — | `ctrl+w`, then `s` / `r` |
| System menu | click `[ ⚙️ Menu (F10) · 🛑 … ]` in HUD | `F10` |
| Awaiting orders (Questions) | click `[ ❓ N awaiting orders ]` in HUD | `!` |
| Console height | drag the console's top edge (`⇕`) | `alt+-` / `alt+=` (10–60 %, remembered) |
| Keybindings cheat sheet | — | `?` or `F10` → `3` |
| Graceful quit | — | `q` or `F10` → `6` |

`ctrl+w` enters **window mode** (desktop tinted, footer lists the keys); `esc` or
`enter` leaves it. Outside window mode all keys go to the views as before.

The **Preview** window is linked to the selection: highlighting a goal, task or
process in the tree, kanban, processes table or calendar shows it there; `enter` in Preview opens
the full node card. Pin it (`ctrl+w p`) to keep the current node while browsing.

Snapped and tiled windows keep their fractional slot and follow terminal resizes;
windows moved or resized by hand stay where they are (clamped to the screen).

The layout is stored in `.orkcraft.json` (Town Scroll v3, workspace root; override with
`$ORKCRAFT_LAYOUT_FILE` or `--layout FILE`); v2 scrolls (a rally point becomes a plain road of its
target, the garrison lead the steward) and legacy v1 layouts (`.orcraft.json` / `.orkcraft.json`)
are migrated automatically. It is saved
on exit, after every mouse drag, on leaving window mode and on orkspace switch. `orkcraft --reset-layout`
starts from a fresh default scroll.

## Town Hall pipeline

Everything that changes the camp goes through the Town Hall and its own git:

```
🏰 Town Hall: [📜 Preset] [🛠 New]
📜 preset: what you need → name, icon, settings ───────────────────────────┐
🛠 new: talk with the Builder (questions, three views, carts, events, timer) │
        → a script-first blueprint → 🏛 Council + 🧪 sandbox + 🖼 preview /   ▼
        ▶ emulation → approve, or reject back into the talk   👻 a grey ghost in the middle follows
                                                               the mouse; a click builds, Esc cancels
👍 K / 👎 F on a building ─► references · incidents · penalties (upstream for broken inputs)
🔧 Building retro · 🗓 Town retro ─► apply with one click ─► checkpoint in .orkcraft/.git ─► Z reverts
```

- **Checkpoints.** `.orkcraft/` is a git repository of its own (branch `camp`) that tracks only
  what defines the camp — `buildings/*.json`, `scripts/`, `blueprints/` and a snapshot of the Town
  Scroll. Every build, road, settings change, revert and improvement is a commit named after its
  building (`update(crag): settings: window`). **`Z`** puts one building back as it was before its
  last checkpoint — its spec, scripts, incoming roads and garrison — and leaves the rest alone.
- **The Council's Fast Path** reviews every new building, agent and road made from scratch (presets
  skip it): 👑 Chief (budget), 🧱 Mason (schemas), 🎨 Artisan (the TUI), 🛡 Warder (bash
  security: sudo, `curl | sh`, `rm -rf /`, secrets, the network), ⛏ Peon (worktrees, permissions,
  cache). Rules first — a rule's block stops it and says why; then one `claude -p --model haiku`
  call whose objections you may override. Reviews: `.orkcraft/council/reviews.jsonl`, the Town Hall.
- **The Town Hall's hut** has two buttons — 📜 Preset and 🛠 New (also `[` / `]`); the audit, the
  clean-up and the settings live in F10. Two towers, a pediment over the round window of the Elders,
  columns between; in the corner of its heading row burns the Elders' lamp: 🌙 on watch (quiet
  hours), 📜 advice waits for you, ⏳ tonight's questions are used up, 💤 at rest by day, nothing at
  ⛓️ Ask me. The Hall tab lists what the Elders judged lately: ↪ answered, 📜 advised, · left to
  you, ⚠ flagged by the Warder.
- **From scratch** is a conversation: the Builder asks until it knows what the building does, offers
  three views, the carts it takes, the events it sends and an optional timer; a rejected blueprint
  goes back into the conversation. The blueprint's window shows a 🖼 preview of the building on the
  mock results, ▶ emulates the carts arriving one by one, and runs any cart you type in the sandbox.
  It makes a 🛠 **Workshop**: its logic is a script (`python3 -I` or `bash`, stdin the
  cart as JSON; exit 0 done · 4 alert · 3 hand the cart to the steward prompt · else failed). A
  steward prompt is written only when a script cannot do the job, with the reason. The blueprint's
  mock carts run in a sandbox (an empty folder, a bare environment, a timeout) before you approve;
  the open Workshop shows its runs as a log, a table or a card, `e` edits the script, 🧪 reruns
  the mocks.
- **Roads with a prompt.** `Y`, then click the source building (or press its number); "✨ Listen
  with a prompt…" takes one or several of its events and says how to handle them. The Recruiter
  makes the handler — a chain or a script whenever the rule needs no judgement — then the Council
  reviews it; a rejection comes back to the dialog with the prompt emptied. Script handlers run once
  approved (`python3 -I`, records on stdin) and are held again if the file changes; a hybrid's
  exit 3 hands over to its agent.
- **👍 / 👎** sit beside the steward in the console (or `K` / `F`). 👍 keeps a building's last
  result as a reference — up to three are shown to its agents and steward prompt. `F` asks what went wrong:
  broken inputs penalise its suppliers along the roads that delivered this session (1, ½, ¼ by
  hop); its own logic penalises only it. Either way an incident is kept (`.orkcraft/feedback/`).
- **The Council's duties** also cover prompts (🛡 injections, leaks, secret files, "ignore previous
  instructions", writers asked to push or delete), the load on you (🎨 too many events, settings,
  roads, buildings on a canvas) and housekeeping (⛏ F10 → 🧹 rotates big logs, removes the state of
  gone buildings and stale worktrees, stops webhooks of demolished buildings — never the camp's git).
- **Retros** never apply themselves (design: `docs/design/retros-and-goals.md`). The daily
  🔧 **Building retro** (`optimize_at`, 06:20) ranks buildings by their share of the camp's tokens in
  24 h — or, with a subscription quota read, by the share of what is left of the binding quota they
  will eat before it resets (`realm/pressure.py`) — takes the first that got no 👍 since its last
  change, or a 👎 today, reads its recent runs and proposes one checked change towards the building's
  **goal** — 🪙 thrift · ⚖️ balance · 💎 quality, a click on the goal button beside 👍 / 👎 in the Info
  panel cycles it (`buildings[].goal` in the Town Scroll; missing = balance). 💎 buildings the operator
  👎-d this week come first, failing or never-rated ones last; for them the Council may **enrich** a
  prompt (longer, at most twice as long) instead of shrinking it, and a camp whose forecast passes
  what is left of the limit treats its three heaviest 💎 buildings as ⚖️. The changes: a shorter
  prompt, chain ops instead of an agent, a script instead of a steward prompt, or a richer prompt. The weekly
  🗓 **Town retro** (`weekly_at`, Sunday 05:00) has `claude -p --model opus` audit the whole camp. When you rated
  nothing that week it first shows up to four results of the week to rate (👍 / 👎 inputs / 👎 logic /
  skip — one per building: a changed one, a 💎 one, a failed run, the heaviest; `realm/retro.py`). Its
  report lists items with checkboxes — it may also remove an unused building or add a camp building — and Apply
  makes each one a `weekly(<id>)` checkpoint, saves the Town Scroll, restarts the touched daemons
  and, when buildings changed or the report asks, offers to restart orkcraft. Both: F10 →
  Building retro / Town retro; F10 → ⚙ Retro settings sets the models and the schedules.
- Settings live in `.orkcraft/council/settings.json`: `fast_llm`, `fast_model`, `optimize_at`,
  `weekly_model`, `weekly_at`, and the Elders' `elders_per_night` (40; 0–200) and `elders_context`
  (lines of the agent's screen they read, 14; 4–60). `--demo --demo-set dashboard` shows the pipeline seeded (F3 Gates
  has a Workshop; the Town Hall lists reviews, ratings, an incident, a proposal and a report).

## Showcase sandbox (`orkcraft --demo`)

`orkcraft --demo [DIR]` builds (once) and opens a separate sandbox project with eight showcase
orkspaces F1–F8 — Feat-OAuth, QA-Regression, Architecture-Core, Design-Review, Design-Tokens,
Strategy-Sprint, Delivery-Control, Solo-SaaS — each a closed workflow of four custom buildings
wired by labelled roads (default folder `~/.orkcraft-demo`; your `.orkcraft.json` is never
touched). Data is simulated; chains run for real, agents show a prepared last result and never
call a model. `--demo-reset` rebuilds it; `--demo-screens OUT` walks F1–F8 headless and saves
SVG + PNG screenshots. `--demo-set managers` opens a second sandbox (default
`~/.orkcraft-demo-managers`) with the engineering-manager 1on1-Prep canvas; `--demo-set dashboard`
one with the 15 camp buildings (My Day, Agent Yard, Gates, Library) in a real git repository.

## Orks: steward, handlers, Recruiter

- **Looks**: the icon is the kind — 🪧 chain / script, 🧌 agent, 🪧🧌 hybrid; the marks are the
  harness scheme — `✻` Claude (orange), `✦` agy / Gemini (blue), `⌬` Codex (green), `P` a pipeline (magenta), e.g. `✦→✻` (agy
  writes, Claude reviews); long schemes read `✻→✻·4`. The frame badge shows the steward.
- **Tiers** (`realm/tiers.py`): how heavy a model a handler thinks with — 🔮 **elder** (opus,
  gemini pro, gpt-6-astra), ⚔ **warrior** (sonnet, gemini flash high, gpt-6.1-sol), ⛏ **laborer** (haiku,
  gemini flash low, gpt-6-luna).
  A harness step takes a `tier` and the model follows from its harness
  (`{"role": "run", "harness": "claude", "tier": "elder"}` runs `claude --model opus`); a step's own
  `model` wins and its tier is read from it. An ork shows its heaviest step's icon before its name
  (roster, unit card, orders); stewards show none. Pick the tier when recruiting by hand (warrior by
  default) or later in the ork's orders; the Recruiter proposes one per step. Barracks providers
  and Clan Fire members take a tier in place of a model: `claude:laborer`, `Critic:claude:elder`.
- **Console of a selected building**: left to right the War Map (36 columns, each orkspace's biome as an icon after its name), the Info
  panel (the rest), the garrison (22) and the Command Card. Info: the building's icon and name with 👍 / 👎 / 🗑 (demolish), why it
  is here, one quiet line of spend, the week's runs and 👍 / 👎 with *📜 History*, and who it
  listens to (source, signal → the ork or a plain road) with *➕ Listen*. The garrison lists its
  orks one per line — number, tier, name, its models as marks (`✻` Claude orange, `✦` Gemini blue), state. An ork with a question
  shows ❓: picking it opens the question and the building stays selected; the ❓ goes once
  seen. The Command Card keeps only the building's own commands (and hides when it has none);
  the common ones stay on their keys.
- **Console of a selected ork**: Info shows its icon, tier and name with 👍 / 👎 (its own
  scores, under `<building>/<orc>`) and 🗑 (dismiss; never a steward), why it is here, and one
  quiet line of spend, 👍 / 👎 and whether it is deployed with *📜 History*. The garrison turns
  into its **🎒 Inventory**: the model and tier first (Enter or a click changes harness and tier
  per step), then the tools of its latest runs, most recent first — one opens the Unit
  Chronicles with only the runs and calls of that tool. The ork is commanded in its chat (45 %
  of the screen, right), so the Command Card steps aside and the console ends where the chat
  begins. Esc goes back to the building.
- **Roster** (Building state): the ★ steward first, then each handler with its incoming roads
  (`◂ ⚒️ Forge · selection`); `1`–`9` pick orks, not rows. The unit card shows the kind, the
  scheme, the roads, the rerun policy and why this kind was chosen.
- **`R` Recruit**: describe what the ork should do and press *Ask the Recruiter* — Claude picks the
  cheapest kind (chain → script → agent → hybrid), explains why, proposes its roads; the preview
  shows it all with attempts and cost, Enter recruits (handler + roads). Scripts are saved as drafts
  under `.orkcraft/scripts/` and do not run yet. The name / role / orders fields below still recruit
  an agent by hand.
- **`W` Steward** (Unit state on a ★ steward): watch now — free metrics (errors, jams, noisy filters,
  🪙, an agent repeating itself); a model is asked only when something was found. Proposals
  (demote an agent to a chain — replayed on its recorded runs first —, rerun policy, filter, new
  road) open in a list; Enter applies a ready one. A steward whose trigger is `cron` watches on its
  schedule in the background (`* * * * *` or `daily 05:00`).

## Custom buildings (Mason & Artisan)

- **Build Flow (`B` in Neutral)**: Opens `BuildModal` to prompt Mason (data sourcing) and Artisan (panes, widgets, actions). While `builders.build(...)` runs in a background worker thread, `BuildProgress` shows progress with a spinner (`Esc` hides the modal while generation proceeds).
- **Preview & Raise**:
  - Artisan also writes the hut (`mini`: up to three status templates), see Town view.
  - Valid specifications display in `BuildPreview`: inspecting title, icon, resident ork, data queries, widget panes, custom actions, attempts used, and API cost.
  - Pressing `Enter` / "Raise" saves the spec to `.orkcraft/buildings/<id>.json`, registers the building in the Town Scroll (`.orkcraft.json`), mounts and focuses the new window in the active orkspace, and logs `building_raised` to the Chronicles.
  - Invalids or build errors show in `BuildFailed` with failure details and a "Try again" shortcut (retaining the prompt).
  - All build requests are recorded in `.orkcraft/build-requests.jsonl` (timestamp, prompt, ok status, attempts, cost, id/error).
- **Custom Building Views (`screens/custom_view.py`)**:
  - Flexible layout panes in `Vertical` or `Horizontal` orientations with proportional fr ratios (`1fr`–`4fr`).
  - Whitelisted widgets: `table` (`DataTable`), `list` (`OptionList`), `counter` (large metric display), `markdown` (`Markdown`), `log` (tailing `TextArea`), and `tree` (`DirectoryTree`).
  - Strict security boundary: data is only acquired through `masonry.fetch(...)` with whitelisted sources. Auto-refreshes every 30 seconds or on `building:refresh`, preserving active selections across reloads.
- **Command Card & Presets**:
  - Focused custom buildings show their `spec["actions"]` on the Command Card bound to free shortcut keys (`A`, `E`, `F`, `G`, `I`, `J`, `K`, `O`, `Q`, `V`, `W`, `Z`). Supported actions include `node:open`, `node:chat`, `node:preview`, and `building:refresh`.
  - The Presets modal (`P`) includes a `[ Custom (Mason & Artisan) ]` section to view, move, or resurrect custom buildings.

## Calendars and limits

Subscribe to Google Calendar with each calendar's *Secret address in iCal format*
(Google Calendar → Settings → the calendar → Integrate calendar). List the feeds in
`~/.config/orkcraft/calendars.json` (`$ORKCRAFT_CALENDARS_FILE`):

```json
[
  {"name": "Personal", "url": "https://calendar.google.com/calendar/ical/…/basic.ics"},
  {"name": "Exported", "path": "~/Downloads/work.ics"}
]
```

Feeds are cached in `~/.cache/orkcraft/ics/` for 15 minutes; offline, the cached copy
is used. Limits are read by the bundled `orkcraft.quota` (`claude -p /usage`, `agy -p /usage`:
answered locally, no quota spent), refreshed every 10 minutes; `ORKCRAFT_LIMITS=0` turns them off.

## Sessions (Town Hall)

`o` (anywhere) opens the selected node's latest Claude Code / agy / Codex session in the
Town Hall's **Sessions** tab (the War Tent of old), or starts a new Claude session for it. There: `enter` resumes
the highlighted session (`claude --resume <id>`, `agy --conversation <id>`, `codex resume <id>`), `n` /
`a` / `c` start a new Claude / agy / Codex session, `A` switches between the node's sessions and
all sessions, `x` stops the shown one. The terminal is the real CLI on a PTY, so
its interface — polls, option lists, permission prompts, `/model`, `/goal` —
works as usual; every key goes to it except `F1`–`F8` (orkspaces), `F9` / `shift+F9` (cycle window), `F10` (menu) and `F12` (back to
the session list). `ctrl+q` and `ctrl+p` stay with orkcraft. Started sessions keep
running when you switch.

Where sessions come from:
- `.orkcraft/sessions.jsonl` (gitignored), written by the session hook (`orkcraft hooks install`,
  module `orkcraft.hooks.session`, into the project the session works in): Claude Code —
  `.claude/settings.json` (SessionStart, UserPromptSubmit); Codex — `.codex/hooks.json` (the same events,
  run once trusted with `/hooks`; the only source of Codex sessions, whose own store keeps no project folder);
  agy — `.agents/hooks.json` (PreInvocation, Stop; agy 1.1.x reads only
  `~/.gemini/config/hooks.json`, copy the entries there). Tickets come from
  `$ORKCRAFT_TICKET` (set when orkcraft opens a session for a node) and `[[T…]]` in prompts.
- Local Claude transcripts `~/.claude/projects/<repo>/*.jsonl`, agy conversations
  `~/.gemini/antigravity-cli/brain/<id>/`.
- Cloud sessions from `Claude-Session:` commit trailers (shown as links; open in
  the browser).

The node card lists its sessions (links are clickable in terminals with OSC 8);
Preview shows how many there are. `ORKCRAFT_CLAUDE_BIN` / `ORKCRAFT_AGY_BIN` / `ORKCRAFT_CODEX_BIN` override
the CLI paths.

## Gold 🪙 and Lumber 🪵

- **🪙 Gold** — what the Claude sessions started by *this* orkcraft run cost, against
  `budget.gold_session_limit_usd` in `.orkcraft.json` (default $20). Every War Tent terminal is
  tagged with `ORKCRAFT_RUN` / `ORKCRAFT_TERMINAL`; the session hook writes them next to the
  transcript path, and orkcraft prices each assistant message of those transcripts (read
  incrementally every 5 s). A resumed session counts only the turns after orkcraft started.
  Model calls that leave no transcript of this run count too, as they answer
  (`telemetry.charge`): the Council's Fast Path, the 🏛 Elders, the Builder, the Recruiter, the
  Town Builder, the Building retro and the Town retro (`claude -p`), the Barracks orks and the
  Clan Fire's members. A road's agent carries `ORKCRAFT_RUN`, so its transcript already counts.
- **🪵 Lumber** — the context of the active War Tent session's last turn (input + cache reads +
  cache writes), against `budget.lumber_context_limit_tokens` (default 128k; k = 1024 tokens).
- Colours: yellow from 80 %, red from 100 %. At 100 % of 🪙 new sessions (`+`, `S`, deploy `C`,
  resume `R`) are held until the limit is raised; over 🪵 you get a one-time hint to `/compact`.
- Prices are the published first-party Claude API rates (`orkcraft/sources/pricing.py`, with the
  source URL and date), including cache-write TTLs, fast mode and `inference_geo: "us"`. They are
  **API-equivalent estimates**, not a bill: Claude Pro / Max plans don't charge per token, and
  Bedrock / Vertex price separately. A `+` after the amount means some usage had no published
  price (agy and Codex sessions, unknown models) — it is never counted as $0.
- Unit Chronicles show the same 🪙 and 🪵 per run.
- **⏳ Limits** — with subscriptions chosen at onboarding (`tools` in the machine settings), the HUD
  shows the used share of each one's tightest window (`[⏳ claude 38% · agy 71%]`, read by the
  Town Hall's Limits tab every few minutes), and 🪙 only while some tool runs on an API key.

## Worktrees and the Council

- **`G`** (Neutral) opens the ⎇ worktree of the active orkspace: create one on a branch (an existing
  branch is reused, a new one starts from `HEAD` or the base you give) in
  `.orkcraft/worktrees/<orkspace>`; later unlink it or remove it (refused while it has uncommitted
  or untracked work unless you confirm; the branch always stays). Main Camp works in the
  repository itself. New War Tent sessions of an orkspace with a worktree run in that checkout;
  the War Map shows `⎇ branch` (`*` = uncommitted work, `?` = folder missing).
- **🛡️ Warder** is live: `orkcraft.hooks.warder` is a Claude Code `PreToolUse` hook
  (`orkcraft hooks install` adds it to `.claude/settings.json`) on Bash / Read / Edit / Write / MultiEdit / NotebookEdit / Grep / Glob.
  It **denies** `rm -rf` of /, ~, the repository or `.git`, `curl … | sh`, mkfs / dd onto a device /
  fork bombs, `git push --force` (`--force-with-lease` is fine) and reading, writing or staging
  secrets (`.env*` except examples, private keys, `.ssh`, `.gnupg`, `.aws/credentials`, `.netrc`, …);
  it **asks** before `git reset --hard`, `git clean -f`, discarding all changes, `git branch -D`,
  dropping stashes, `sudo`, dumping the environment, and any edit of Warder itself (also from a
  shell). Here-document bodies are data and are not judged. Every deny / ask lands in
  `.orkcraft/warder.jsonl` (tokens redacted) and puts ❓ on Warder in the Council — `1`
  acknowledges it. Sessions in a worktree log to the main repository. Warder guards Claude Code
  and Codex (agy has no documented pre-tool hook); hooks load when a session starts. For Codex it is
  in `.codex/hooks.json` with `apply_patch` among its tools (the files are read from the patch), runs
  once trusted with `/hooks`, and turns an ask into a deny that says why — Codex cannot ask yet.
- The other Council orks (Drummer, Taskmaster, Alchemist, Keeper) are still draft agents in
  `watchers/`; the 🪙 / 🪵 limits cover Taskmaster's budget duty.

## Onboarding

Opening orkcraft in a project with no `.orkcraft.json` starts 🧭 onboarding
(design: [design/onboarding.md](design/onboarding.md)); `ORKCRAFT_ONBOARDING=0` turns it off.

1. **Tools** — `claude`, `agy` and `codex` are looked up on `PATH`; each found one is checked, with its
   version, whether it is logged in and its billing (subscription, or API when `ANTHROPIC_API_KEY` /
   `GEMINI_API_KEY` / `OPENAI_API_KEY` is set) — you can change both. No key is stored or read: Codex's
   login is told only by its `~/.codex/auth.json` being there.
2. **Autonomy** — a slider of four stops: ⛓️ *Ask me* · 📜 *Morning advice* (default) · 🧭 *Routine on
   their own* · ⛓️‍💥 *Free orks* (see *Ork autonomy* below).
3. **Mode and your day** — 🧌 Camp, 👔 Office or 🧌/👔 Shift (cards of the same building), and the
   day bar with 🌙 quiet hours and, for Shift, 👔 office hours (see *Modes and your day* below).
4. **Town** — an empty town, or a preset by domain (⚔️ Engineering · 🧝 Design · 🛡 Management ·
   💀 Indie, four each; for now every preset opens the empty town), or *Didn't find it?*: your words
   become an order for the 📜 Town Builder (below). The 🛡 Warder is installed here when `claude`
   is in use and the box stays checked.
5. **Raising** — the camp's git, the Warder, the buildings and the order, with a progress bar along
   the bottom of the town.

Steps 1–3 are kept per machine in `~/.config/orkcraft/settings.json` and asked once;
F10 → 🧭 Onboarding asks them again. Skip anywhere: an empty town, defaults, no Warder.

### 🏛 Ork autonomy

How much the orks do on their own (`autonomy` in the machine settings, F10 → 🏛 Ork autonomy).
Autonomy comes from three places:

- **The Elders' advice** (from *Morning advice* up): in 🌙 quiet hours the Elders of the Town Hall
  read each permission question of a claude / agy session and leave advice. The Warder's rules come
  first — what they block (secrets, sudo, `curl | sh`, `rm -rf /`…) gets no advice and no model call;
  what they only warn about (the network, a push, a backtick) goes to the model with the Warder's note,
  and that advice carries a ⚠. Then the Council's light model (`haiku`) may advise a **one-time** yes
  or a no, never an option that widens permissions ("don't ask again", "allow all edits"); options are
  read from their words, cursor and number aside. In the morning *Orders* (`!`) shows the advice: `a`
  follows it, `A` follows it on every advised question but the ⚠ ones; the rest wait as before. At
  most `elders_per_night` questions a night (40), never past the 🪙 budget — their own calls count in
  it; every judgement is in `.orkcraft/council/elders.jsonl`, and a restart brings back the advice of
  the last day and tonight's count from it. The Town Hall lists them.
- **The Elders' answers** (*Free orks* only): in quiet hours the Elders send that one-time yes or no
  to the agent themselves — only if the very same question still waits and it is still quiet, and
  never a ⚠ advice. What the rules stop, or the model would not advise, waits for you. The log marks each answer `sent`,
  and the morning toast counts them.
- **The agents' own permission settings** (from *Routine on their own* up): the step shows what to
  paste into Claude Code's `.claude/settings.local.json` (this project) or `~/.claude/settings.json`
  (every project) — an allow list for reading, editing the project, its tests and read-only git; at
  *Free orks* also `acceptEdits` and the usual project commands, with `git push` asked and
  `rm -rf`, force pushes, `sudo` and `.env` denied — how to start agy
  (`agy --mode accept-edits --sandbox` at *Free orks*) and Codex (`codex --sandbox workspace-write
  --ask-for-approval on-request` from *Routine on their own*). 📋 (or `c` / `g` / `o`) puts the Claude
  snippet, the agy or the Codex command on the clipboard. The 🛡 Warder hook still denies the dangerous whatever the settings allow.

#### 🔧 Self-improvement by the orks

The Building retro, the Town retro and the stewards keep proposing as before; up to *Morning
advice* every proposal waits for your click. From *Routine on their own*, in 🌙 quiet hours, the orks
apply what their level allows themselves (`realm/evolution.py`), one change at a time, at most 10 a
night, never past the 🪙 budget:

| Level | The orks apply |
|---|---|
| 🧭 Routine on their own | what makes a building cheaper or simpler: a shorter prompt, an agent made a chain, a steward's demotion (proved on recorded runs), a run policy, a road filter |
| ⛓️‍💥 Free orks | also a script instead of an agent (sandbox-proved), a richer prompt for a ⚖️ / 💎 building, a new plain road, a building's setting, a building from the catalog |
| never | removing a road or a building, notes — those stay proposals |

Every change still passes its own checks, then the Council's review with no block, objection or
Warder warning (else it stays a proposal); it gets its own checkpoint, so `Z` takes it back, and **24
hours of probation**: a 👎 on the building, or more failed runs than before, takes it back by itself
— only while it is still the building's last checkpoint (else it is marked ⚠ stuck and `Z` is yours)
— and a toast says so. **🧾 The list of the orks' changes** opens when quiet hours end, after a
probation revert, and from F10 → 🧾 What the orks changed: 🧪 on probation, ✓ kept, ↩ taken back,
⚠ stuck; `z` takes one back. Every applied change, yours too, is in `.orkcraft/evolution/changes.jsonl`.
Stewards' changes now get their own checkpoint as well.

### 📜 The Town Builder

An order in words (*Didn't find it?* at onboarding) becomes a plan of a whole town: one
`claude -p` call in an empty folder, like the Foreman, that sees only the order and the building
catalog. The plan is 2–8 typed buildings from the catalog (never the Town Hall or the Builder's
scratch type) and up to 12 **plain** roads, each waiting for an event its source sends — every
building passes `masonry.validate_spec`, and a plan with problems goes back with them (up to 3
attempts). The checks also refuse a road into a building that does nothing with a cart (Pit,
Watchtower, Task Fields, War Drum, File Forest), a road from a 🚏 Signpost that does not name one of
its routes (it is raised as a road waiting for that route), and a 🎯 Catapult whose `wait_for` names
a building that has no road into it. Settings that name buildings (`wait_for`, a Horn's sounds, a
Signpost's `source` rule) are written with the plan's keys and follow the buildings' ids. Nothing is
raised before you approve it:

- **Raise the town** (`ctrl+s`) — the buildings go up one by one, then the roads, with the bar along
  the bottom; one checkpoint for the whole town; the order is closed.
- **Ask again** — with a note on what to change.
- **Later** — the order waits in the 🏰 Town Hall, whose hut burns 🔥 until you open it (opening it
  offers to plan it); F10 → 📜 Town Builder plans it any time.

What the planner knows of the buildings is `catalog.catalog_text()`: per type what it does with a
cart (`catalog.TAKES`), the payload kind of each event, what it does outside the camp
(`catalog.EFFECTS`) and how each setting is written (`catalog.CONFIG_HELP`).
The first attempt lists only the settings' names; a retry spells out the settings of the types the
plan chose. `tests/test_catalog_docs.py` keeps these tables in step with the views and the config.

The order lives in `.orkcraft/town/order.json`; every plan request is logged in
`.orkcraft/build-requests.jsonl`.

## CLI

- `orkcraft` — open the town in the current git project (the root is found by `.orkcraft.json`
  or `.git`); `--repo PATH` for another one.
- `orkcraft hooks install` / `uninstall` — add (or remove) the session log and the Warder guard
  to the project's `.claude/settings.json`; other hooks and settings stay as they are.
- `orkcraft --demo` — the showcase sandbox (simulated data).

## Installation

```bash
pipx install ./orkcraft        # or: python3 -m venv .venv && .venv/bin/pip install -e ./orkcraft
cd your-project && orkcraft hooks install && orkcraft
```

## Modes and your day: 🧌 Camp · 👔 Office · 🧌/👔 Shift

F10 → *Camp* (default), *Office* or *Shift*, kept per machine as `mode` in
`~/.config/orkcraft/settings.json` (`$ORKCRAFT_SETTINGS_FILE` overrides the path; the old names
`immersion` / `hidden` / `plain` still load as camp / office). A project may override it with
`preferences.mode` in `.orkcraft.json`; choosing a mode in F10 sets the machine's and drops the project's
override. The data is the same in every mode; only the look changes (`orkcraft/realm/modes.py`): Camp
wears the immersion look, Office the hidden one.

| | 🧌 Camp (immersion) | 👔 Office (hidden) |
|---|---|---|
| Buildings | ASCII silhouettes (roofs, sails, trees, waves) on the orkspace's biome | only a grey frame with the same live rows on a black canvas (no biome, no terrain) |
| Agents | orks 🧌 / 🪧 in the frame | nothing, or `busy` while one works |
| A question | fire 🔥 | `?` |
| Waiting for an answer | the building flickers orange (its ground too), after 30 s it turns red, from 60 s its roof turns to 🔥 bit by bit, all fire at 5 min | only the frame and the name turn red |
| Roads | rocks 🪨 roll from building to building | small squares ■ |
| HUD (top right) | 🪙 gold, 🪵 lumber, 🥩 meat | Spend, Context, Agents |
| Emoji | everywhere | as few as possible: building names, status lines, buttons, window titles, the War Map and the roster, the F10 menu, the key footer (`Stop all`, `Add agent`, `Answers`) and the toasts lose theirs |

The opened building's own view keeps what its data says.

**Questions on another orkspace.** Its War Map row takes the question's colour (fire orange in
immersion, red when hidden) and ends with 🔥 / `?`. Switching to it (F1–F8 or a click on the row) opens
its questions at once, the one waiting longest first (↑↓ for the rest); behind the dialog the building
of that question is selected and the ork who asked it is picked in the garrison.
- **🧌 Camp** — the immersion look all day.
- **👔 Office** — the hidden look all day.
- **🧌/👔 Shift** — Office in office hours on office days (default 09:00–18:00, Mon–Fri; a span past
  midnight belongs to the day it started), Camp the rest of the time. The town switches by itself
  (checked every 30 s) and the HUD says `[👔 office till 18:00]`.

The Lake, the Crag and custom frames grow with their content in every mode, and a hut that changes
size or mode keeps off its neighbours.

**🌙 Do not disturb** — quiet hours (default 23:00–08:00 when switched on, off otherwise). In quiet
hours no fence burns or flickers: a waiting ork shows ❓ on its label instead of 🔥, and the HUD says
`[🌙 quiet till 08:00]`. Where quiet overlaps office hours both hold — the town in frames and no
fires — the bar shows half purple, half grey and the HUD names both. Later quiet will also mute sound,
push notifications and the bot.

**F10 → 🕰 Your day** (and onboarding step 2) shows the day bar: 00:00 → 24:00, one cell per half
hour, amber for the day, dark purple for quiet, grey for office hours (Shift only), half purple /
half grey where they overlap, ▼ for now. Drag
across it to set the selected span, or Tab to an edge (quiet start / end, office start / end) and
move it with ←/→ by half an hour, shift+←/→ for the whole span; Delete turns the quiet hours off.
Office days are `office_days` in the settings file (0 = Monday).
