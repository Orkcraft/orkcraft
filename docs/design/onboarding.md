# Design — onboarding

Status: design notes, written 2026-10-03; stages 1–5 of §7 are implemented (presets are stubs). Builds on the quota readers
(`orkcraft/quota/`), the two display modes (`preferences.mode`), the Warder hooks and the Town Hall.

## 1. When it runs

Onboarding has two scopes:

| Scope | Where it is kept | Steps |
|---|---|---|
| **Machine** — once per machine | `~/.config/orkcraft/settings.json` (`$XDG_CONFIG_HOME` respected) | 1 Tools · 2 Mode |
| **Project** — once per project | `.orkcraft.json` (the Town Scroll) | 3 Town · 4 Raising the town |

- Opening orkcraft in a project with no `.orkcraft.json` starts onboarding. If the machine settings
  already exist, it starts at step 3.
- F10 → **🧭 Onboarding** runs steps 1–2 again; step 3 is not offered there, since it would replace the town.
- Every step has `Esc` / **Back**. **Skip** anywhere = empty town, defaults for everything not chosen yet.
- `--demo` never shows onboarding.

## 2. Step 1 — Tools

```
┌ Which clans will you lead? ───────────────────────────────────────────────┐
│                                                                           │
│  [x] claude   ✓ found · v2.x · logged in        ( subscription ▾ )        │
│  [ ] agy      ✓ found · not logged in — run `agy login`                    │
│  [ ] codex    ░ coming soon                                               │
│                                                                           │
│  The top-right corner shows limits for a subscription and 🪙 for an API.   │
│                                                     [ Skip ]  [ Next → ]  │
└───────────────────────────────────────────────────────────────────────────┘
```

- **Detection**: `shutil.which` for `claude` / `agy` (honouring `ORKCRAFT_CLAUDE_BIN` /
  `ORKCRAFT_AGY_BIN`), then a cheap local check that it is logged in (`--version`, the quota reader).
  Tools are found ones checked by default; missing ones are greyed with an install hint.
- **OpenAI (`codex`)** is listed but disabled with “coming soon” — no adapter, quota reader or Warder yet.
- **Billing — subscription or API**, per tool. Detected and only overridable: for `claude`, a set
  `ANTHROPIC_API_KEY` means API, an OAuth login means a subscription. Orkcraft **never stores a key** —
  it keeps only `billing: "subscription" | "api"`; the CLI reads its own key, as before.
- **The HUD corner** follows billing: subscription → limit bars (5 h window, week) from `quota/`;
  API → 🪙 spend. Mixed tools show both, compactly (`claude 62% · agy $1.40`).
- **No tool chosen**: Next stays enabled but warns that agents and the Builder will be unavailable,
  and offers `orkcraft --demo`.

Stored:

```json
{ "tools": { "claude": { "enabled": true, "billing": "subscription" },
             "agy":    { "enabled": false, "billing": "subscription" } } }
```

## 2b. Step 2 — Orc autonomy

A slider of four stops (`screens/autonomy.py`, `autonomy.py`): ⛓️ Ask me · 📜 Morning advice ·
🧭 Routine on their own · ⛓️‍💥 Free orcs. Under it, what the level means in two lines — ❓ the agents'
questions, 🔧 the camp's improvements (from Routine up, the orcs apply some in quiet hours, with the
safeguards: Council, checkpoint, 24 h probation, the list of changes — `realm/evolution.py`) — and the
agents' own settings, one line each, with 📋 (or `c` / `g`) copying the Claude Code permission block or
the agy command instead of showing them. From Morning
advice up, the 🏛 Elders (`realm/elders.py`) advise on the agents' permission questions in quiet hours —
Warder rules first, then the light model, a one-time yes or a no only — and the operator follows the
advice in the morning (`a`, `A` for all). Only at ⛓️‍💥 Free orcs do the Elders answer themselves in quiet
hours: their one-time yes or no goes to the agent, if the very same question still waits; what the
rules stop or the model would not advise still waits for the operator.

## 3. Step 3 — Mode and your day

```
┌ How should the town look? ────────────────────────────────────────────────┐
│   ┌ ⚒️ Forge (ASCII) ─────────┐      ┌ ⚒️ Forge (frame) ─────────┐          │
│   │  …the same live rows…    │      │  …the same live rows…    │          │
│   └──────────────────────────┘      └──────────────────────────┘          │
│        ○ 🧌 Camp          ◉ 🧌/👔 Shift           ○ 👔 Office              │
│                                                                           │
│  Your day                       ▼                                         │
│   ████████████████▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒████████████████████████              │
│   00    03    06    09    12    15    18    21  24                         │
│   █ day  █ 🌙 quiet 23:00–08:00  █ 👔 office 09:00–18:00 Mon–Fri            │
│  [x] 🌙 Do not disturb — no fires, only ❓ (later: no sound, no push)        │
│                                        [ ← Back ]  [ Skip ]  [ Next → ]   │
└───────────────────────────────────────────────────────────────────────────┘
```

- Three modes: **🧌 Camp** (the immersion look), **👔 Office** (the hidden look, `realm/modes.py`) and **🧌/👔 Shift** — Office in office
  hours on office days, Camp otherwise, switched by the clock (`schedule.py`). Camp sits under the
  camp's picture, Office under the office's, Shift between them; both cards light up for Shift. The cards show the same building with the same live rows, so only the look differs.
- **The day bar** (`widgets/day_bar.py`): 48 half-hour cells, amber day, dark purple 🌙 quiet, grey
  👔 office (Shift only), ▼ now. Mouse: drag a stretch for the selected span. Keys: Tab picks an edge,
  ←/→ move it, shift+←/→ move the whole span, Delete turns quiet off. Where quiet and office overlap both hold
  (frames, and no fires): the cell is half purple, half grey.
- **Quiet hours**: no fires flicker, a waiting orc shows ❓; later no sound, no push, no bot.
- Stored in the machine settings: `mode`, `quiet`, `office`, `office_days` (Mon–Fri by default).
  `preferences.mode` in the Town Scroll stays an optional per-project override.
- The same screen is F10 → 🕰 Your day, with Save and Cancel.

## 4. Step 4 — Town

```
┌ Choose a town ────────────────────────────────────────────────────────────┐
│  [ Start with an empty town ]                                              │
│                                                                           │
│  Domain: [ Engineering ▾ ]                          ┌──────────────┐      │
│  ────────────────────────────────────────           │   ASCII orc  │      │
│  ◉ 🛠 Solo Forge                                     │              │      │
│  ○ 🔍 Review Gate                                    └──────────────┘      │
│  ○ 🐛 Bug Hunt                                                             │
│  ○ 🚀 Release Train                                                        │
│  ○ Didn't find it?                                                         │
│     [ describe the town you need…                              ]          │
│                                                                           │
│  [x] Install the 🛡 Warder (recommended) — edits .claude/settings.json      │
│                                                     [ ← Back ]  [ Build ] │
└───────────────────────────────────────────────────────────────────────────┘
```

- **Domains and their mascots**: Engineering — orc · Design — elf · Management — knight · Indie — skeleton.
  The ASCII mascot beside the list follows the dropdown.
- **Town presets** are a new thing (today's presets in `realm/catalog.py` are single buildings): a
  piece of the Town Scroll — buildings, roads, layout — kept as JSON templates. The selected preset
  shows a short description and its buildings below the list.
- **For now every preset is a stub that opens an empty town.** Names and descriptions:

  | Domain | Preset | What it will be |
  |---|---|---|
  | ⚔️ Engineering | 🛠 Solo Forge | one developer: tasks → agents → tests → merge |
  | | 🔍 Review Gate | PR review and diff inspection |
  | | 🐛 Bug Hunt | bug reports triaged and fixed in worktrees |
  | | 🚀 Release Train | changelog, tests, cutting a release |
  | 🧝 Design | 🎨 Mockup Grove | an idea → mockup variants → a pick |
  | | 📐 Design System | tokens, components, consistency checks |
  | | 🖼 Asset Pipeline | generating assets and accepting them in the Loot Vault |
  | | 🗣 Critique Circle | the Clan Fire reviews design decisions from every side |
  | 🛡 Management | 📋 War Room | tasks, statuses, a daily digest |
  | | 📨 Inbox Keep | mail, GitHub and webhooks sorted into tasks |
  | | 🥁 Sprint Drum | sprint planning, calendar, retro |
  | | 📊 Ledger Tower | metrics, spend, reports |
  | 💀 Indie | 🎮 Game Jam | a fast prototype, tasks and builds |
  | | 🏚 One-Skeleton Studio | code, copy and marketing in one town |
  | | 📣 Launch Crypt | landing page, posts, collecting feedback |
  | | 🧪 Side Quest | a light town for a pet project |

- Presets that need an agent are disabled (with a note) when no tool was chosen in step 1.
- **Didn't find it?** — the prompt is saved as an **order** and, once the empty town stands, the
  📜 **Town Builder** (`realm/town_builder.py`) plans a town from it: typed buildings from the catalog
  and plain roads between them, checked like any spec. The operator approves the plan
  (`screens/town_plan.py`), asks again with a note, or leaves it for later — then the order waits in
  the Town Hall, which burns 🔥 until it is opened (opening it offers to plan it; F10 → 📜 Town Builder).
- **The Warder** is installed here (same as `orkcraft hooks install`), with the checkbox on by default,
  because it changes `.claude/settings.json`. Hidden when `claude` is not enabled.

## 5. Step 4 — Raising the town

No separate progress screen: the town itself opens and the progress bar runs along its bottom.
Each bar step is real work:

1. create `.orkcraft/` and the camp's git (branch `camp`);
2. install the hooks / Warder (if checked);
3. place the buildings one by one (they appear as if being built) and lay the roads;
4. for a custom prompt: the order saved; the Town Builder starts as soon as the town stands.

At the end, a short toast with three keys: `B` build · `P` presets · `?` all keys.
With a stub preset steps 3–4 are empty and the bar finishes at once.

## 6. Edge cases

- A tool is found but not logged in — shown, unchecked, with the login command; checking it is allowed.
- A tool disappears later — the HUD greys its corner; no onboarding rerun.
- A narrow terminal — cards and the mascot stack or hide; the minimum is the list and the buttons.
- Onboarding interrupted (quit mid-way) — nothing is written until each step's Next; the project
  part is written only on **Build**.
- An existing `.orkcraft.json` — no onboarding; F10 → 🧭 Onboarding redoes only steps 1–2.

## 7. Plan

1. Machine settings file (`tools`, `billing`, `mode`) and the `preferences.mode` fallback.
2. Tool detection + billing detection; the HUD corner switching between limits and 🪙.
3. Screens 1–2 (Textual modals), the F10 entry.
4. Screen 3 with stub presets, domains and mascots; the pending order in the Town Hall.
5. Step 4: creation steps on the town with the progress bar; hooks install from onboarding.
6. The Town Builder for a custom prompt (done). Later: real town presets, `codex` support.
