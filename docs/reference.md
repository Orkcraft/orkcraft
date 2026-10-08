# Orkcraft — reference

_The detailed reference. Start with the [README](../README.md). Old `MGTUI_*` / `ORCRAFT_*` environment variables (from the project's earlier names) still work as fallbacks for `ORKCRAFT_*`._

> [!NOTE]
> The screens, keys and console below are the **terminal UI's**, which is deprecated (`orkcraft tui`). The
> window (`orkcraft`) is a calm town: the map, one panel on the right, the Warchief's line —
> [design/calm-town.md](design/calm-town.md). The buildings, roads, orks, files and settings below are the same in both.

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
│ [F1] 🏰 Main Camp (forest)  │ ▼ ⚒️ Forge (Garrison: 1)      │ [B] 🏗️ Build                        │
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
  `[B] Build` are kept in `.orkcraft/build-requests.jsonl`.
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
| 2 | 🏰 Town Hall | Warchief | its agents and the last audit · Sessions (live terminals of every AI tool) · Limits (each tool's quota) |
| — | 🏛️ Systems | Engineer | multi-agent pipelines and their schemes |

Every other building is built from the catalog of typed buildings (below) or from scratch by the Builder (a Workshop).

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
are in `tui/silhouettes.py`. New huts are laid out on shelves — rows filled left to right, each
spread over the width — and keep the spot you drag them to.

- Click a hut → it is selected: the hut lights up and the console below turns to that building,
  the map stays as it is. Click it again (or press its number) → the building opens over the map.
  One building is open at a time; a click on another hut closes it and selects that one. `esc`,
  a click on the map or a click on the open building's hut closes it. Opening never moves a hut, so the roads stay where they are.
- Drag a hut to move it; its spot is kept in the Town Scroll (`buildings[].hut`).
- **Calm console**: in the town the console floats over the map's bottom edge instead
  of taking rows from it. With nothing selected only the War Map shows (bottom left — a 🔥 on an
  orkspace tells you an ork there waits for orders) and the **🏰 Town Hall** (bottom right, on
  every canvas, never moved or demolished) with its two buttons: **🏗 Build**, one way in — a 📜 preset
  (pick what you need, name it, place it) or 🛠 new from scratch with the Builder — and **🔍 Audit**;
  `B` opens the same build menu. Select a building, an ork or a road and the
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
3. STORAGE AND INSPECTION  🗑️ Scroll Dump   ⚒️ Forge
4. RESULTS AND EGRESS      📦 Loot Vault    🪨 Tally Crag    🎯 Catapult
```

| Building | Resident | Takes | Sends |
|---|---|---|---|
| 🕳️ The Pit | Scavenger | drag-and-drop files, pasted links / text, 📋 the clipboard; sorted by kind, kept in `.orkcraft/pit/` | `drop.file`, `pit.link`, `pit.text` |
| 🗼 Watchtower | Lookout | IMAP mail (read-only; `host: gmail`), GitHub events (`gh`), `feeds`: comments and mentions in Slack, Jira, Confluence, Figma, GitHub (many repos, notifications), GitLab and Discord, a schedule (`every 15m`, `daily 05:00`), webhooks on 127.0.0.1 (optionally signed); `intent`: only what you are after; new ones marked, ✓ reads all | `mail.received`, `watch.github`, `watch.comment`, `watch.mention`, `watch.cron`, `watch.webhook` |
| 🚏 Signpost | Grot Pointa | anything; rules (`route: contains …`, `matches`, `kind`, `source`, `field == value`, `else`) pick a route, each road waits for its own (a route no road takes is a dashed stub off the post on the map: pull a road from it to a building); a `totem` of old (and its `totem.routed` roads and Horn lines) loads as a Signpost | `signpost.routed`, `signpost.unmatched` |
| ⚙️ The Mill | Miller | anything; a map over each cart, strictly in order — `grep`, `replace`, `csv`, `json`, `extract`, `sort` (numbers as numbers), `filter` (`gt`/`lt`… on numbers and ISO dates), `template`, `script: …` (clean environment plus the names in `env`), `agent: …` for what a script cannot do and `script: … \|\| agent: …` when it fails; what arrives while it mills waits in a queue | `mill.done` (one per cart), `mill.item` (a flat map: one cart per record), `mill.failed` |
| 📯 The Horn | Hornblower | anything; plays a sound per event (`mail.received: chime`, `gate_pit/pit.link: alarm`, `gate_pit: ding`, `*: none`): horn, chime, alarm, drum, ding, the terminal bell or an audio file of yours; Enter walks a row to the next sound, 🔇 mutes, quiet hours (`22:00-08:00`), a cooldown | `horn.sounded` |
| 🌾 Task Fields | Taskmaster | a board of cards in `TASKS.md` or a folder: tasks in To Do / In Progress / Done, sticky notes in lanes of their own (Ideas, Questions…); `mode`: `board` · `tasks` · `notes`; `n` `<` `>` `e` `c` `t` `s` `d` `N` (below); a cart becomes a card | `tasks.created`, `tasks.status_changed`, `notes.created`, `tasks.sent` |
| 🏕️ Barracks | Grunts | tasks (a cart, or one you write with ✍ New task: a title and a brief), each on its own branch. The steward judges a task first (docs/design/barracks-planning.md): a simple one goes whole to one ork of the light tier the building's goal names (🪙/⚖️ a laborer, 💎 a warrior); a hard one is planned (an elder plans) into parts — each with its tier, its persona, the files it touches and the parts it waits for — that run in parallel, are merged into the task's branch and reviewed as a whole against your request, with one pull request; the plan is estimated in $ and tokens and trimmed to the budget and to what is left of the quota (a tight quota makes the barracks thrifty). Nobody hires by hand: a follow-up goes to the ork who did the earlier part, a new task to an idle ork of its tier and persona or a newly hired one; a try sent back goes up one tier (laborer → warrior → elder); a new persona the steward writes waits as your autonomy says; related work resumes the ork's session. The steward keeps the rules (`orders`), answers `QUESTION:`s or asks you (🔥), reviews (`test_cmd`, then the diff; ≤`max_reworks` reworks) and pushes the branch with a pull request — for code (always) and documents that go out; an ork never posts to a service itself (Jira, Confluence, Slack…): it drafts the post under a `PUBLISH: <where>` line, and `pool.question` carries the draft, the report and the files — 🔥 Enter publishes it (or type what to change), and through a 📦 Loot the cart is always held: accept lets the ork post it (your edits included), rework sends it back; `pool.done` then brings the report, the files and the link; a local document (a War Drum meeting's prep, or what the steward marks `SCOPE: local`) gets no PR and needs no commit when it is a meeting's | `pool.assigned`, `pool.done`, `pool.failed`, `pool.question`, `pool.idle` |
| 🪔 Clan Fire | Chieftains | a document (a cart — usually a Barracks result — or ▶ with a path or text): each member reviews it from its role (`APPROVE` / `CHANGES:` / `VETO:`), reading the repo and the web; the steward decides by its brief — let it go, send it back, or 🔥 ask you (your answer outranks the brief). The document is data, never orders. A veto from a `veto` role blocks approval; after `max_cycles` reworks of one title the operator decides. Briefs are files: `steward.md` and `roles/<role>.md` in `.orkcraft/council/<id>/`; documents that come mid-review, or while the 🪙 budget is out, queue (Review now, Drop). **Set up in its panel** (design/review-board.md): a `purpose`, the clan the keeper proposes for it (roles, what each checks, tier, veto; the briefs written from it), and named `exits` (`Name: when`), each a route a road out waits for. A board with `exits` puts the verdict (`## Review notes — <exit>`: the steward's or your words, each member's remarks) on top of the document on every exit, never takes an exit no road takes (on the map such an exit is a dashed stub off the board, named: pull a road from it to a building; a connected exit's road is signed with its name), and when it asks, burns and offers its exits as buttons (in the panel and in Answers), with a note as the verdict's words; Back to the author is always there, a veto leaves only it. Budget spent → Raise the budget and go on; failed → Try again; stopped → Go on — each from the turn it stopped at (shown beside the button): the members already heard are not asked again, and a Claude member or steward cut off mid-turn goes on in its own session instead of reading again. A review is kept turn by turn, so one the app was closed in reads as stopped and goes on too | `team.approved`, `team.rework`, `team.artifact_ready`, `team.routed` |
| 🥁 War Drum | Drummer | an `.ics` file or URL: now, next, the day and the week; + adds an event. `lead` (2h) before a meeting it sends `event_upcoming` once, tagged `[meet:<id>]` (📄 sends it at once); a cart back with the tag (Barracks' `pool.done`) is the meeting's document: 📄 at the meeting, Enter shows it in a Lake of Insight | `calendar.event_due`, `.day_schedule`, `.event_added/removed`, `.event_upcoming`, `.doc_opened` |
| 🌲 File tree (retired) | Woodcutter | nothing builds one anew (`catalog.RETIRED_TYPES`): a project file that has one still loads it — a folder as a tree with previews; Enter picks a target; ↗ opens it in the OS | `files.changed`, `files.selected` |
| 🗑️ Scroll Dump | Scroll Scrapper | one LLM wiki per topic (`codebase`, `team`, `design`, `general`) from read-only `sources` (folders of notes, `code:` folders, `git:<rev>[:<folder>]`, `confluence:<SPACE>`); ingests by itself, a module at a time, commits, keeps people's pages theirs, has a Clan Fire spot-check; `i` ingests now, `l` lints, `x` stops; a cart is a task and goes on with the wiki's map | `knowledge.changed`, `knowledge.chunks`, `wiki.updated`, `wiki.linted`, `wiki.review` |
| 🌊 Lake of Insight (the town's window, not a building: none is built anew, a road into an old one opens in Lake) | Seer | a diff (side by side), Markdown, a file, a URL (as text), a branch (its diff); ↗ browser. A text file on disk (Markdown, code, a patch) is edited in place: `e` or ✎ opens the editor — fix the text, leave your notes in it; it saves by itself every `autosave` seconds (default 5) while there are changes and whenever the editor loses focus (another window, another building); `ctrl+s` saves at once, `Esc` saves and goes back to the view. A file changed on disk meanwhile is never overwritten by an autosave: the head says ⚠ and `ctrl+s` writes your text over it. Line endings and the file's mode stay as they were | `lake.viewed`, `lake.saved` (the edited file, once you leave the editor) |
| ⚒️ The Forge | Smith | the repository's state — what comes in and what goes out: branches with PRs and +/−; ⚒ (or a cart naming a branch) tests it in a throw-away worktree and squash-merges it into the base | `git.commit`, `git.pr_*`, `forge.merged`, `forge.conflict` |
| 📦 Loot Vault | Quartermaster | the review checkpoint on a road: by its rules a cart passes or is held; under a waiting cart, the files its task committed on its branch (diff or content; a picture shows its type, size and dimensions, and in the GUI the picture itself). In the GUI a text cart is edited in its window (Edit: Save, or Accept this version) or in Lake, and one file of a held cart's branch is rejected on its own — put back on the branch as the base has it by a commit there, its content kept under `rejected/carts/`, Bring it back undoes it — while the rest of the cart goes on (a rework tells the ork which files were rejected). TUI keys `a` accept · `e` edit and accept · `r` reject / send back for rework with a reason (≤ 3 rounds, then 🔥 needs you) · `d` drop · `u` restore a rejected file · `o` open the highlighted file in the system viewer (a branch's file is copied out first); the chain's tokens and cost; every decision teaches the building that made the cart | `loot.passed/rework/needs_you`, `generator.accepted/rejected`, `loot.stored` |
| 🪨 Tally Crag | Crag Carver | complex data made visual: spend, tokens, runs (`.orkcraft/ledger.jsonl`), quotas used, busy orks, tasks, CPU, numbers by road — vertical or horizontal Unicode bars | `charts.threshold` |
| 🎯 The Catapult | Loader | waits for every road in `wait_for` (fan-in), checks a JSON Schema, sends over HTTP(S) with a token from the environment — shots queue one at a time — or through an MCP server (carried by the tool that has it, then a direct path the ork learns), or, in browser mode, its ork finds the intent's forms, fills them in turn and repairs a script the site broke; 🧪 dry run | `catapult.sent`, `catapult.failed`, `catapult.repaired` |

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
  takes its group with it: 🎯 fires it again, **Drop it** lets it go (**Drop the load** lets go of
  what is loaded and not yet a shot). With `confirm`, a shot waits for your yes: **Fire**, **Later**
  (it waits at the front of the queue and holds it until **Resume**, which asks again, or **Drop**)
  or **Drop**. A 🧪 dry run that fails the check is kept as a dry run: it sends no `catapult.failed`.
- **The Catapult's mode mcp** sends through an MCP server your AI tools already have — Slack, Jira,
  Confluence, email, Notion, Discord (docs/design/catapult-mcp.md). Set `mode: mcp`, `to` (the server,
  as your tools name it), and optionally `tool`, `args` (`channel = "C0123"`, `text = notes`), `via`
  and `goal`. A shot takes the most deterministic track there is:
  - **direct** — a learned route to the service's own API (or SMTP) with a token of yours from the
    environment: no model;
  - **local** — with `local: true` (Start the local server itself) the Catapult starts a local (stdio)
    server as your tool's config says and calls the tool: no model;
  - **carrier** — the AI tool that has the server (chosen by the server, not by the ork: Slack in Codex
    and the Loader on Claude still works) runs headless, allowed exactly that one MCP tool, with the
    arguments as JSON; its events are the proof — exactly one call, that tool, those arguments, else the
    shot failed. One call of the light model, in the ledger and under the 🪙 budget. Only Claude Code
    carries for now; a server whose tools are all off or cannot carry makes the shot wait (Resume).
  - **Learning.** The first carried shot (it asks, even with `confirm` off) may let the carrier pick
    the tool; the Loader turns the call into a template over the cart and — where a recipe
    (`realm/catapult_mcp/recipes/`) knows the service — into a direct route, kept in
    `.orkcraft/scripts/<id>/route.json` (a commit). The window offers it: **Use it** (its first shot
    asks; 🧪 shows the carried call beside the direct request for the same cart) or **Keep the carrier**.
  - **Breaks.** A refused token (401/403, Slack's `invalid_auth`…) burns the hut and holds the queue
    until you fix it and press **Resume**; a refused call on a direct or local path is carried once and
    learned again (`catapult.repaired`), unless `repair: false`.
  - Environment variables the recipes read: `SLACK_BOT_TOKEN` or `SLACK_WEBHOOK_URL`;
    `DISCORD_WEBHOOK_URL` or `DISCORD_BOT_TOKEN`; `JIRA_URL`, `JIRA_EMAIL`, `JIRA_API_TOKEN`;
    `CONFLUENCE_URL`, `CONFLUENCE_EMAIL`, `CONFLUENCE_API_TOKEN`; `NOTION_TOKEN`; `SMTP_HOST`,
    `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD` (an app password), `SMTP_FROM`, or `RESEND_API_KEY` and
    `EMAIL_FROM`. Tokens are read when a shot fires and never written anywhere.
  - The 🔍 Audit flags a Catapult in mode mcp that sends without asking.
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
  - 🛑 Stop all stops the running browser; the queue waits for **Resume** (which fires nothing loaded)
    or the next 🎯. The hut's line starts with 🌐 in
    browser mode. Fields inside iframes are not marked yet. The 🔍 Audit flags a Catapult that
    presses submit with no schema and no confirmation.
- **Add a source** (the GUI; design/watchtower-quick-add.md). A tower with no source opens its panel on
  it, and its card says **+ Add a source**; later the **+** chip and Sources & intent open it. It stays
  in the panel, over the feed — never a dialog. Paste a link (a GitHub repo, a GitLab project — on
  gitlab.com or a host this machine has a GitLab login for —, a Slack channel, a Discord channel, a
  Jira issue, a Confluence space, a Figma file, a Gmail address) or pick GitHub, GitLab, Gmail, Slack,
  Jira, Confluence, Figma or Discord, then three steps: **Log in** (gh's own login for GitHub and
  glab's for GitLab, nothing to paste — else a token; else one paste — an app password, a token — with
  the link to the page that makes it; Slack's app comes from a ready manifest; Discord's bot is made
  in its developer portal and invited by the link the next step gives), **What** (repos, projects,
  channels, spaces or files, this project's repo ticked; *about me* on — GitHub's notifications,
  GitLab's to-dos, mentions; Discord asks who **Me** is, by user id or a link to a message you wrote),
  **Check** (the first look, made now: as whom, what it hears, how many are there — marked seen, not
  sent) and **Add**. A source's row in Sources & intent says what it hears and whether it fails, with
  **Edit** (step 2, its picks ticked), **Log in again** when its login fails (step 1, what it hears
  kept; the new line takes the old one's place) and Remove (confirmed). A failing source says which
  way, and offers that one fix in the panel's head too: *the token was refused* → Log in again; *a
  channel, repo, project or file is gone or out of reach* → Edit; *could not reach* the service → no
  button, it tries again by itself. **Everything** (step 2, off by default) hears a whole service at
  once — GitHub's every notification (`notifications=all`), every Slack message the login can see
  (`everything=on`), every channel of the servers a Discord bot is in (`guilds=`), every issue of a
  Jira site (`jql=updated >= -1d`), every Confluence page and comment, the whole Gmail mailbox (All
  Mail); a tower with no intent asks for one there (empty keeps everything). Figma's whole team waits
  for push.
- **Through Claude** (design/watchtower-quick-add.md §7): a `feeds` line `agent: tool=claude
  server=atlassian tools=searchJiraIssuesUsingJql,getJiraIssue every=30m ceiling=0.50 ask=new comments
  and mentions in Jira` hears a service through the person's own connector in Claude Code, no token
  on this machine: a headless `claude -p` on the light model, allowed only the tools listed (name
  read-only ones), the answer by schema. Every 30 min by default (10 at the fastest); each look's cost
  goes to Spend and to the source's line (`≈ $0.12 today`); past its `ceiling=` dollars a day it
  waits until tomorrow. A server that needs a login says *run /mcp in Claude Code*. The picker does
  not offer it yet: write the line, or ask the steward.
- **Logins** keep the tokens on this machine, out of the project (`realm/logins.py`): the OS keychain
  when `keyring` is installed, else `~/.config/orkcraft/logins.json` (mode 0600; `$ORKCRAFT_LOGINS_FILE`
  moves it). A spec names a login wherever it named a variable — `token=keychain:slack-acme`,
  `password_env: keychain:gmail-ann@gmail.com` (and `user:` holds a mailbox's address as written) — and
  no model, toast or project file sees the token. A login that is gone reads `log in again`.
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
    - "github: repos=acme/app,acme/api notifications=on"   # gh's login; or token=GH_TOKEN (classic, for notifications)
    - "gitlab: host=gitlab.com token=GITLAB_TOKEN projects=group/app todos=on"   # read_api; no token: glab's login
    - "discord: token=DISCORD_BOT_TOKEN channels=123,456 me=789"   # a bot with Message Content Intent
  ```

  A mention, a direct message, a Jira or Confluence @-mention, a reply to your Figma comment, a
  GitHub notification (a review asked, a mention, an assignment, a thread you are in), a GitLab
  to-do, a Discord message that mentions you (`me=`) or the bot or answers you → `watch.mention`; any
  other new comment or message → `watch.comment` (its title starts with the service); a GitHub repo's
  events → `watch.github`, as the `github:` setting's. Your own messages are skipped; each feed's
  first look only marks what is there as seen.
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
  schedule's aside) to its steward (*Judge what it caught*: the tier picked for it, else the goal's,
  light under ⚖️), twenty at a time, fenced as data it must not
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
- **Quick note** (docs/design/wiki-librarian.md): *+ Quick note* in the window, the quick action, `/note`
  to the Warchief, or *→ Wiki* on a note of the Task board. As the note is typed the wiki suggests,
  without a model, the pages to link (the ones that share its words, in any script and inflection),
  their section and, as tags, the names of those pages the note says; each is dropped with one click.
  The note is a Markdown file in `inbox` (default `notes/inbox`, made a source of the wiki by the
  first note) with that front matter, and the librarian keeps it at take-in (*Take in now*, on by
  default, starts one at once). Saving sends `wiki.noted`. When rules find nothing, the light model
  (the Council's `fast_model`) is asked once per note for a section and tags (`suggest_model`).
  `/note <text>` in the Warchief's line shows those suggestions over the line as the text is typed —
  the meeting it is for, the section, the tags, the pages to link — and saves only on Enter; Tab
  picks another coming meeting (the next 14 days) or *Not for a meeting*, Shift+Tab goes back, and
  `@Wiki` names the wiki when the town has several.
- **Meetings.** A note that names a meeting of a Calendar (War Drum) — by its day, a person, its
  words — or that names only a person, lands under **To discuss** on the meeting's page
  (`pages/meetings/`, written at once and committed alone); a person ticks items off there. When the
  Calendar asks for the meeting's brief (`meeting soon`, `[meet:<id>]`), the Wiki hands over that
  page first; after the meeting what was not ticked moves on to the next meeting with the same
  person. The window lists what the coming meetings should cover; the card counts the next one's.
  The Calendar says it too, beside each meeting the Wiki keeps items for: *from the Wiki: 2 to
  discuss* in its window (and *· 3 pages*, the pages the notes link, once the brief is back), *✎ 2*
  on its card.
- **Quality check** (`check`: `weekly` by default, `daily`, `ingest`, `off`): the librarian's lint on a
  schedule, one line per problem with its kind; rules look at every refresh, no model, for links to
  nowhere, pages missing from their section's index and pages without front matter. The window shows
  what was found, *Fix links and indexes*, the next check and the last cost; the card the count.
- **Search** over the window's lists: the pages and the sources' notes, by name first, then by the
  words they share, in any script.
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
- `orkcraft --demo --demo-set dashboard` opens all of them on six canvases (My Day, Agent Yard,
  Gates, Library — three LLM wikis, code, team and design, that tasks pass through — Front Desk:
  mail and Slack triaged by a Clan Fire that routes, to your to-dos or to an ork that does the task by
  itself — and Meetings: a mail that asks to meet becomes an event in the War Drum, which asks for its
  brief at once; an ork writes it from the Scroll Dump's notes and it comes back to the event) in a real
  git repository; agents never run there and the Catapult only dry-runs.
  `python tools/landing_flow.py [--flow desk|meeting|all]` films the Front Desk's flow or the Meetings'
  one, frame by frame and as a video.

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
🏰 Town Hall: [🏗 Build: 📜 preset · 🛠 new] [🔍 Audit]
📜 preset: what you need → name, icon, settings ───────────────────────────┐
🛠 new: talk with the Builder (questions, three views, carts, events, timer) │
        → a script-first blueprint → 🏛 Council + 🧪 sandbox + 🖼 preview /   ▼
        ▶ emulation → approve, or reject back into the talk   👻 a grey ghost in the middle follows
                                                               the mouse; a click builds, Esc cancels
👍 K / 👎 F on a building ─► references · incidents · penalties (upstream for broken inputs)
what you do with results ─► the same, weighted: Loot ✓ ✎ ↩ ✗ · a Lake's reshaped file · PR merged / closed · Z · unopened
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
- **The Town Hall's hut** has two buttons — 🏗 Build (a preset or new from scratch) and 🔍 Audit
  (also `[` / `]`); the clean-up and the settings live in F10. Its steward is the **Warchief**
  (a scroll of old names it the Chieftain and keeps its id). In the GUI the hut
  is the town's way in: Build and **Ask me anything** — a question to the Warchief, whose chat is the
  Town Hall's Command Card (it names a building of the catalog when one fits, and builds it on a click). Two towers, a pediment over the round window of the Elders,
  columns between; in the corner of its heading row burns the Elders' lamp: 🌙 on watch (quiet
  hours, or by day from 🕰 On the clock), 📜 advice waits for you, 🔚 today's questions are used up, 💤 at
  rest by day in ⛓️ chains. The Hall tab lists what the Elders judged lately: ↪ answered, 📜 advised, · left to
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
- **Roads in words.** *➕ Listen* in the GUI (or an arrow drawn from a building's + to another) asks
  what it should listen to and what should happen to it — *"unread messages become to-dos"*. The
  receiver's steward offers up to three roads (an event, a filter, or a rule an ork handles); picking
  the event or the building by hand is folded below. In the TUI: `Y`, the source, *💬 Say it in words…*
  (docs/design/roads-and-orcs.md §5b).
- **Roads with a prompt.** `Y`, then click the source building (or press its number); "✨ Listen
  with a prompt…" takes one or several of its events and says how to handle them. The Recruiter
  makes the handler — a chain or a script whenever the rule needs no judgement — then the Council
  reviews it; a rejection comes back to the dialog with the prompt emptied. Script handlers run once
  approved (`python3 -I`, records on stdin) and are held again if the file changes; a hybrid's
  exit 3 hands over to its agent.
- **👍 / 👎** sit beside the steward in the console (or `K` / `F`). 👍 keeps a building's last
  result as a reference — up to three are shown to its agents and steward prompt. `F` asks what went wrong:
  broken inputs penalise its suppliers along the roads that delivered this session (1, ½, ¼ by
  hop) and weighs on them, not on it, in the retros and probation; its own logic penalises only it.
  Either way an incident is kept (`.orkcraft/feedback/`).
- **What you do with results counts too** (`feedback.signal`; design: `docs/design/native-feedback.md`).
  Each thing you do is a 👍 or 👎 with a weight — a button weighs 1, a quiet signal less, and the
  retros and probation act only once they add up to 1: in a 📦 Loot Vault ✓ accepted as it was
  (0.34; ✓ Accept all 0.1), ✎ edited and accepted — only added to 👍 0.34, fixed 👎 0.34, the format
  changed 👎 0.5, rewritten 👎 0.75, your version kept as an example — ↩ sent back (👎 0.5, with
  the reason's chip; "what came in was wrong" blames the hops before the maker along the cart's
  trail), past the rework limit or dropped (👎 0.5), one file of its branch rejected (👎 0.34); in a 🌊 Lake an ork's file you fixed (0.2),
  reformatted or rewritten (0.5) — filling it in (a daily note you write into) says nothing, and a
  personal note's text is never kept; a Barracks pull request merged 👍 1 or closed 👎 0.5 (a duplicate: nothing); `Z` on a
  retro's change 👎 1. The ork that wrote a cart is the one judged (a Clan Fire or a chain after it
  is not). A result left in a Lake or a Loot and not opened for a day counts as unused (0.1, for the
  Town retro), never as a dislike; nor does "too expensive" make a 💎 building richer. Only a 👍 or a
  merged pull request spares a building its thrift turn. The Town
  Hall shows the weight of what you did beside the buttons; incidents say how they were told.
- **🎨 `D` on a building**: say what should change in its window; its steward rewrites the
  building's UI document (panes, sizes, font and colour roles — never raw values), checked against
  the type's contract. `Enter` keeps it as a checkpoint `ui(<id>)`, `Z` takes it back, and `default`
  restores the type's own layout. See [docs/design-system.md](design-system.md).
- **The Council's duties** also cover prompts (🛡 injections, leaks, secret files, "ignore previous
  instructions", writers asked to push or delete), the load on you (🎨 too many events, settings,
  roads, buildings on a canvas) and housekeeping (⛏ F10 → 🧹 rotates big logs, removes the state of
  gone buildings and stale worktrees, stops webhooks of demolished buildings — never the camp's git).
- **Retros** never apply themselves (design: `docs/design/retros-and-goals.md`). The daily
  🔧 **Building retro** (`optimize_at`, 06:20) ranks buildings by their share of the camp's tokens in
  24 h — or, with a subscription quota read, by the share of what is left of the binding quota they
  will eat before it resets (`realm/pressure.py`). What is left comes from the quota's tokens per
  1 %, measured from a 🪨 Tally Crag's samples once the quota climbed 10 points under sampling in a
  week (the ledger's tokens over the points climbed, stretches cut at a reset or a gap), else
  estimated from the camp's own spend. It takes the first that got no 👍 since its last
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
one with every building type the catalog builds (My Day, Agent Yard, Gates, Library, Front Desk, Meetings) in a real git
repository, each with a few days of state: tasks, a calendar around the hour it was built, signals
(the Watchtower asks no server: one feed fails on purpose), routes, mill runs, PRs as `gh` would
list them, a conflict, orks with questions on their screens. `orkcraft gui --demo` opens this set
by default (`~/.orkcraft-demo-dashboard`). A sandbox of an older demo is built again by itself.

## AI tools and the main tool

Orkcraft leads Claude Code, Antigravity (agy), Codex, Hermes Agent, pi and Cursor (`cursor-agent`),
all through one registry (`orkcraft/realm/harnesses.py`, docs/design/harnesses.md): how each answers
once, reads, works in a worktree, resumes and opens a terminal, what it prints and costs.

- **Main tool** — Settings → *AI tools* turns each tool on or off and picks the main one (empty: the
  first one on). Every decision runs on it: the Warchief, the Town Builder, the Foreman, the road
  planner, the Recruiter, the Council's fast path, stewards and keepers, retros. With no tool on it
  is Claude Code.
- **Steps** name a tool or `main` (the main tool, read when the step runs). New orks, Barracks
  providers, Council members and the Mill's agent start on `main`; an ork or a steward that names its
  own tool keeps it. A tier (Elder, Warrior, Laborer) names each tool's own model; a tool without a
  tier table (Hermes, pi, Cursor) runs its default.
- **Guards** — the 🛡 Warder judges every tool with the same rules: Cursor in `.cursor/hooks.json`,
  pi through orkcraft's extension (`-e`, and `.pi/extensions/orkcraft.ts`), Hermes in a marked block
  of `~/.hermes/config.yaml`, written only after asking (`--hermes-global` / `--no-hermes-global`).
  pi has no approvals or sandbox of its own: reading orks get only its reading tools.
- **🪙 and ⏳** — pi and Hermes say what they cost (their session files, `state.db`); Codex is priced
  from its model and token counts once OpenAI's table in `sources/pricing.py` has that model (it is
  empty until a person reads OpenAI's page, so Codex runs are unpriced for now); agy and Cursor print
  no price (unpriced, never $0). ⏳ Limits read Hermes' `hermes usage --json` and Cursor's plan
  month (its stored login); pi keeps no windows.

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

## Custom buildings (Mason & Artisan, retired)

Custom (panes) left the catalog: neither the build wizard nor the presets offer it, and nothing builds one
anew (`builders.propose` refuses the type). A Town Scroll of old that holds one still loads and draws it:
its spec stays in `.orkcraft/buildings/<id>.json`, its building in the Town Scroll (`custom:<id>`).

- **Custom Building Views (`screens/custom_view.py`)**:
  - Flexible layout panes in `Vertical` or `Horizontal` orientations with proportional fr ratios (`1fr`–`4fr`).
  - Whitelisted widgets: `table` (`DataTable`), `list` (`OptionList`), `counter` (large metric display), `markdown` (`Markdown`), `log` (tailing `TextArea`), and `tree` (`DirectoryTree`).
  - Strict security boundary: data is only acquired through `masonry.fetch(...)` with whitelisted sources. Auto-refreshes every 30 seconds or on `building:refresh`, preserving active selections across reloads.
- **Command Card & Presets**:
  - Focused custom buildings show their `spec["actions"]` on the Command Card bound to free shortcut keys (`A`, `E`, `F`, `G`, `I`, `J`, `K`, `O`, `Q`, `V`, `W`, `Z`). Supported actions include `node:open`, `node:chat`, `node:preview`, and `building:refresh`.
  - The Presets modal (`P`) lists every building raised from a spec (custom ones of old among them) under `[ Your buildings ]`, to view, move or resurrect it.

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
Codex's 5-hour and weekly windows come from `codex app-server` (`account/rateLimits/read`, Codex
0.53.0 and later; no model turn), with the plan and its credits; when that fails they are taken from
the newest `token_count` in `~/.codex/sessions/` (`$CODEX_HOME`) and marked `as of` that session's
time. A Codex that is not installed, not logged in or logged in with an API key gets one plain row
saying so (an API key has no plan windows). Design: [design/codex-limits.md](design/codex-limits.md).

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
  agy — `.agents/hooks.json` (PreInvocation, Stop; agy reads it once the folder is trusted, since
  1.1.1, and also the global `~/.gemini/config/hooks.json`). Tickets come from
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
  Town Builder (`claude -p`, or Codex or agy, which print no price — Codex is priced from its tokens), the Building retro and the Town retro (`claude -p`), the Barracks orks and the
  Clan Fire's members. A road's agent carries `ORKCRAFT_RUN`, so its transcript already counts.
- **🪵 Lumber** — the context of the active War Tent session's last turn (input + cache reads +
  cache writes), against `budget.lumber_context_limit_tokens` (default 128k; k = 1024 tokens).
- Colours: yellow from 80 %, red from 100 %. At 100 % of 🪙 new sessions (`+`, `S`, deploy `C`,
  resume `R`) are held until the limit is raised; over 🪵 you get a one-time hint to `/compact`.
- Prices are the published first-party Claude API rates (`orkcraft/sources/pricing.py`, with the
  source URL and date), including cache-write TTLs, fast mode and `inference_geo: "us"`. They are
  **API-equivalent estimates**, not a bill: Claude Pro / Max plans don't charge per token, and
  Bedrock / Vertex price separately. Codex (`codex exec` runs and War Tent sessions, read from the
  session's rollout file) is priced from its model and tokens with a second table, OpenAI's rates,
  with its own source and date. The model is the one orkcraft passed with `--model`, or `model` in
  `$CODEX_HOME/config.toml`. For a ChatGPT login this is an API-equivalent estimate too. That
  table is still empty, so Codex runs show `+` for now. A `+` after the amount means some usage had
  no published price (agy and Cursor sessions, Codex until its table is filled, unknown models). It
  is never counted as $0.
- Unit Chronicles show the same 🪙 and 🪵 per run.
- **⏳ Limits** — with subscriptions chosen at onboarding (`tools` in the machine settings), the HUD
  shows the used share of each one's tightest window (`[⏳ claude 38% · agy 71% · codex 12%]`, read by the
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
  acknowledges it. Sessions in a worktree log to the main repository. Warder guards Claude Code,
  Codex, agy, Hermes, pi and Cursor with the same rules (*AI tools* above); hooks load when a session starts. For Codex it is
  in `.codex/hooks.json` with `apply_patch` among its tools (the files are read from the patch), runs
  once trusted with `/hooks`, and turns an ask into a deny that says why — Codex cannot ask yet.
  For agy (1.1.12 or later) it is the `orkcraft` entry of `.agents/hooks.json` on `run_command` and the
  file tools, read once agy trusts the folder; it answers only deny or ask, never allow (agy ignores
  a hook's allow in headless runs). agy's headless steps run in a temp folder and read only
  `~/.gemini/config/hooks.json`, which `orkcraft hooks install` writes only after asking
  (`--agy-global` / `--no-agy-global` answer for it). Onboarding (in the window and in the terminal)
  says the Warder guards agy only once its hook was checked on a live agy (`agy_warder_checked` in
  the machine settings, [agy-guard](design/agy-guard.md) §8). Until then, when agy is chosen, the
  guard step says agy is unguarded, and a raised town gets no agy hook.
- The other Council orks (Drummer, Taskmaster, Alchemist, Keeper) are still draft agents in
  `watchers/`; the 🪙 / 🪵 limits cover Taskmaster's budget duty.

## Onboarding

Opening orkcraft in a project with no `.orkcraft.json` starts 🧭 onboarding
(design: [design/onboarding.md](design/onboarding.md)); `ORKCRAFT_ONBOARDING=0` turns it off.

1. **Tools** — `claude`, `agy` and `codex` are looked up on `PATH`; each found one is checked, with its
   version, whether it is logged in and its billing (subscription, or API when `ANTHROPIC_API_KEY` /
   `GEMINI_API_KEY` / `CODEX_API_KEY` is set) — you can change both. No key is stored: Codex's login is
   told by which kind its `~/.codex/auth.json` holds (a ChatGPT login or an API key; the key itself is
   never used), or else by `codex login status`. `OPENAI_API_KEY` does not count: `codex exec` ignores it.
2. **Autonomy** — a slider of three stops: ⛓️ *In chains* · 🕰 *On the clock* (default) · ⛓️‍💥 *Unchained*
   (see *Ork autonomy* below).
3. **Your day** — the day bar with 🌙 quiet hours (see *Words and the look* below).
4. **Town** — an empty town, or a preset by domain (⚔️ Engineering · 🧝 Design · 🛡 Management ·
   💀 Indie, four each; for now every preset opens the empty town), or *Didn't find it?*: your words
   become an order for the 📜 Town Builder (below). The 🛡 Warder is installed here when `claude`
   is in use and the box stays checked.
5. **Raising** — the camp's git, the Warder, the buildings and the order, with a progress bar along
   the bottom of the town.

Steps 1–3 are kept per machine in `~/.config/orkcraft/settings.json` and asked once;
F10 → 🧭 Onboarding asks them again. Skip anywhere: an empty town, defaults, no Warder.

### 🏛 Ork autonomy

How much the orks do on their own (`autonomy` in the machine settings, F10 → 🏛 Ork autonomy; a
building may have its own under its steward, else it follows the town's — one rule for both). Two kinds
of decision, each with its own wait:

| Level | A question (an agent's, a steward's 🔥, a new persona) | A rebuild (a change of a building or the town) |
|---|---|---|
| ⛓️ In chains | waits for you | waits for your click |
| 🕰 On the clock (default) | waits `autonomy_wait` minutes (7; 5, 7, 15 or 30 under the slider), then the orks decide; in 🌙 quiet hours no wait | waits `rebuild_wait` hours you are around (12; 6, 12 or 24) — the camp open, outside quiet hours — then a change that makes it cheaper is applied in the next quiet hours |
| ⛓️‍💥 Unchained | the orks decide at once | any change, in the next quiet hours |

When the orks decide a question: the Elders send their one-time yes, a new persona is approved, a
Barracks' steward answers the question itself by its rules, and a task sent back too often is closed as
failed with its last notes. A draft to post outside the camp always waits for you; a crashed run is
tried once more by itself. The level is kept as a word (`chains` / `clock` / `free`); older values load
never bolder than they were: *Ask me* and *Morning advice* → In chains, *Routine* and `timer` → On the
clock, *Free orks* → Unchained. Autonomy comes from three places:

- **The Elders' advice** (*In chains*, in 🌙 quiet hours; *On the clock*, once a question has waited its
  minutes): the Elders of the Town Hall read each permission question of a claude / agy session and
  leave advice. The Warder's rules come
  first — what they block (secrets, sudo, `curl | sh`, `rm -rf /`…) gets no advice and no model call;
  what they only warn about (the network, a push, a backtick) goes to the model with the Warder's note,
  and that advice carries a ⚠. Then the Council's light model (`haiku`) may advise a **one-time** yes
  or a no, never an option that widens permissions ("don't ask again", "allow all edits"); options are
  read from their words, cursor and number aside. In the morning *Orders* (`!`) shows the advice: `a`
  follows it, `A` follows it on every advised question but the ⚠ ones; the rest wait as before. At
  most `elders_per_night` questions a day (40, counted from the end of quiet hours), never past the 🪙 budget — their own calls count in
  it; every judgement is in `.orkcraft/council/elders.jsonl`, and a restart brings back the advice of
  the last day and tonight's count from it. The Town Hall lists them.
- **The Elders' answers** (from *On the clock*): the Elders send that one-time yes or no to the agent
  themselves — only if the very same question still waits, and never a ⚠ advice. What the rules stop, or the model would not advise, waits for you. The log marks each answer `sent`,
  and the morning toast counts them.
- **The agents' own permission settings** (from *On the clock* up): the step shows what to
  paste into Claude Code's `.claude/settings.local.json` (this project) or `~/.claude/settings.json`
  (every project) — an allow list for reading, editing the project, its tests and read-only git; at
  *Free orks* also `acceptEdits` and the usual project commands, with `git push` asked and
  `rm -rf`, force pushes, `sudo` and `.env` denied — how to start agy
  (`agy --mode accept-edits --sandbox` at *Free orks*) and Codex (`codex --sandbox workspace-write
  --ask-for-approval on-request` from *On the clock*). 📋 (or `c` / `g` / `o`) puts the Claude
  snippet, the agy or the Codex command on the clipboard. The 🛡 Warder hook still denies the dangerous whatever the settings allow.

#### 🔧 Self-improvement by the orks

The Building retro, the Town retro and the stewards keep proposing as before; *in chains* every
proposal waits for your click. *On the clock*, a proposal left unanswered for the hours you were around
is applied by the orks in 🌙 quiet hours — silence never makes the camp spend more, so the clock allows
only the cheaper half (`realm/evolution.py`), one change at a time, at most 10 a
night, never past the 🪙 budget:

| Level | The orks apply |
|---|---|
| 🕰 On the clock | what makes a building cheaper or simpler: a shorter prompt, an agent made a chain, a steward's demotion (proved on recorded runs), a run policy, a road filter |
| ⛓️‍💥 Unchained | also a script instead of an agent (sandbox-proved), a richer prompt for a ⚖️ / 💎 building, a new plain road, a building's setting, a building from the catalog |
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

An order in words (*Didn't find it?* at onboarding) becomes a plan of a whole town: one model
call in an empty folder, like the Foreman, that sees only the order and the building catalog. It
runs on the main tool (*AI tools and the main tool* above). The plan is 2–8 typed buildings from the catalog (never the Town Hall or the Builder's
scratch type) and up to 12 **plain** roads, each waiting for an event its source sends — every
building passes `masonry.validate_spec`, and a plan with problems goes back with them (up to 3
attempts). The checks also refuse a road into a building that does nothing with a cart (Pit,
Watchtower, Task Fields, War Drum, File Forest), a road from a 🚏 Signpost that does not name one of
its routes (it is raised as a road waiting for that route), and a 🎯 Catapult whose `wait_for` names
a building that has no road into it. A road `"to": "lake"` is no building's: what it carries opens in the town's Lake window (the source gets "open in Lake"). Settings that name buildings (`wait_for`, a Horn's sounds, a
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

## Phones

A phone paired with the town (design: [design/mobile.md](design/mobile.md)) sees it small: each
building's title, type and state, the questions the orks wait on (their last three lines and the
Elders' advice), spend and quotas. It may answer a question with one of its own answers, follow the
Elders' advice, **Stop all** (the desktop says which phone sent it), drop a text, a link or a file into
a **Drop file here** building (never read as a path on this machine), ask the **Warchief** and read
his answers. It never builds, demolishes, lays roads, moves
a hut, types into a terminal or changes a setting: anything else it sends is refused.

- **Settings → Phones → Pair a phone** shows a QR code: the listener's address, its certificate's
  SHA-256 fingerprint (the phone pins it) and a one-time code, good for two minutes. Five wrong tries
  in a minute void the code until a new one is shown. **Forget** stops a phone's token at once and
  closes its connection.
- The listener opens a port on the LAN (TLS, `https://<lan ip>:<port>`) only while a phone is paired or
  a code is shown, and keeps that port for the next run. `ORKCRAFT_PHONE_HOST` sets the address it
  listens on. The certificate is `phone.crt` / `phone.key` beside the machine settings (0600); the
  paired phones are kept there as `phones` (names and the SHA-256 of their tokens, never a token).
- While a phone's app is open it gets one line for each question that came, spend or a quota near or
  over its limit, an error (its title only) and a session that ended. Pushes to a phone in a pocket
  come with the relay (not built yet).
- There is no phone app yet: `python tools/phone.py` speaks the same protocol from a terminal
  (pair from the QR code's text, glance, answer, stop all, ask, chat, drop, watch).

## CLI

- `orkcraft` — open the town in the current git project (the root is found by `.orkcraft.json`
  or `.git`); `--repo PATH` for another one.
- `orkcraft hooks install` / `uninstall` — add (or remove) the session log and the Warder guard
  to the project's `.claude/settings.json` (and `.codex/hooks.json` with Codex, `.agents/hooks.json` with
  agy 1.1.12 or later; for agy's headless steps `~/.gemini/config/hooks.json` after asking); other hooks
  and settings stay as they are, and uninstall removes only orkcraft's entries.
- `orkcraft feedback calibrate [--days N]` — how far each quiet feedback signal (an accepted cart, an
  edited file, a closed pull request…) agrees with the 👍 / 👎 pressed near it, and the weight it has
  earned; it changes nothing (docs/design/native-feedback.md §8).
- `orkcraft --demo` — the showcase sandbox (simulated data).

## Installation

```bash
pipx install ./orkcraft        # or: python3 -m venv .venv && .venv/bin/pip install -e ./orkcraft
cd your-project && orkcraft hooks install && orkcraft
```

## Words and the look

Orkcraft has one look and one vocabulary. Camp (a game) and Office (a work tool) were two, switched per
machine, per project and by office hours; they are merged. The GUI wears Office's layout on Camp's design
system (sprites, the orks' heads, gold); the deprecated TUI keeps the camp's ASCII. An older
`settings.json` with `mode`, `office` and `office_days`, or an older `.orkcraft.json` with
`preferences.mode`, still loads; those keys are ignored.

**Words** (`orkcraft/realm/lexicon.py`). A concept keeps its Camp word when it says *who*: the orks, the
Warchief, the town and its buildings and roads, renown. It takes a plain word when it says *what a thing
does, what it costs or what it risks*: a building's function, the spend, autonomy, a file. Older code and
older towns still write the Camp word of a renamed concept; the interface says it in today's word
(labels, buttons, huts, toasts, the text of every GUI template), while paths (`./loot/`) and what people
and agents wrote stay as written. The voice stays the camp's: the Warchief's lines, growth news and the
onboarding (*Punk ork*).

| word | replaces |
|---|---|
| ork | — |
| orkspace | — |
| orkestration | — |
| orkestrate | — |
| town | — |
| building | — |
| hut | — |
| road | — |
| cart | — |
| biome | — |
| terrain | — |
| clan | — |
| steward | — |
| steward | keeper |
| War Map | — |
| Warchief | — |
| Town Hall | — |
| Road planner | — |
| Building retro | — |
| Ork work | — |
| Renown | — |
| mascot | — |
| deed | — |
| preview | ghost |
| output | loot |
| new orkspace | fog of war |
| spend | gold |
| context | lumber |
| ork slots | meat |
| ork slots | food |
| Budget | Treasury |
| Login | — |
| Stop all | War Horn |
| Terminals | War Tent |
| Answers | Orders |
| Phone | War Raven |
| update | — |
| critical update | — |
| Instructions | Standing orders |
| Awaiting an answer | Awaiting Orders |
| Orks | Garrison |
| Add ork | Spawn Ork |
| Add ork | Recruit |
| Ork setup | Recruiter |
| Set up | Raise |
| Setting up the town | Raising the town |
| Project file | Town Scroll |
| Town planner | Town Builder |
| Weekly retro | Town retro |
| Autonomy | Freedom |
| Propose only | In chains |
| Apply if unanswered | On the clock |
| Apply at once | Unchained |
| History | Chronicles |
| Advisor | Elders |
| Building designer | Mason & Artisan |
| Data planner | Mason |
| Layout designer | Artisan |
| Security reviewer | Warder |
| Usability reviewer | Pathfinder |
| Cost reviewer | Treasurer |
| Review board | Council |
| to-do | chore |
| note | scribble |
| context | — |
| plan | — |
| personal | — |
| Drop file here | The Pit |
| External listeners | Watchtower |
| Router | Signpost |
| Transformer | The Mill |
| Sound alerts | The Horn |
| Task board | Task Fields |
| Agent pool | Barracks |
| Review board | Clan Fire |
| Calendar | War Drum |
| File tree | File Forest |
| Wiki | Scroll Dump |
| Inspector | Lake of Insight |
| Branches & PRs | The Forge |
| Review gate | Loot Vault |
| Metrics | Tally Crag |
| Publisher | The Catapult |
| Script | Workshop |
| Sorter | Scavenger |
| Listener | Lookout |
| Router | Grot Pointa |
| Transformer | Miller |
| Notifier | Hornblower |
| Task manager | Taskmaster |
| Worker | Grunt |
| Reviewer | Chieftain |
| Scheduler | Drummer |
| File picker | Woodcutter |
| Librarian | Scroll Scrapper |
| Inspector | Seer |
| Merger | Smith |
| Gatekeeper | Quartermaster |
| Metrics ork | Crag Carver |
| Publisher | Loader |
| Script runner | Tinker |
| Worker | Peon |

**Questions on another orkspace.** Its War Map row takes the question's colour (fire orange) and
ends with 🔥. Switching to it (F1–F8 or a click on the row) opens
its questions at once, the one waiting longest first (↑↓ for the rest); behind the dialog the building
of that question is selected and the ork who asked it is picked in the garrison.
The Lake, the Crag and custom frames grow with their content, and a hut that changes size keeps off its
neighbours.

**🌙 Do not disturb** — quiet hours (default 23:00–08:00 when switched on, off otherwise). In quiet
hours no fence burns or flickers: a waiting ork shows ❓ on its label instead of 🔥, and the HUD says
`[🌙 quiet till 08:00]`. Later quiet will also mute sound, push notifications and the bot.

**F10 → 🕰 Your day** (and onboarding step 2) shows the day bar: 00:00 → 24:00, one cell per half
hour, amber for the day, dark purple for quiet, ▼ for now. Drag across it to set the quiet hours, or
Tab to an edge (start / end) and move it with ←/→ by half an hour, shift+←/→ for the whole span;
Delete turns the quiet hours off.
