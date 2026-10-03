# Design — onboarding

Status: design notes, written 2026-10-03, reworked the same day: the person comes first — who they
are, how their day goes — then the town for that role; the interview and the Town Builder when no
ready town fits; the machine's part last. Implemented (`screens/onboarding.py`, `realm/intents.py`,
`realm/interview.py`). Builds on the quota readers (`orkcraft/quota/`), the display modes, the
Warder hooks, the Town Hall and the Town Builder (`realm/town_builder.py`).

## 1. When it runs

| Part | Where it is kept | Steps |
|---|---|---|
| **The person** — once per machine | `~/.config/orkcraft/settings.json` → `profile` | Who you are · Your day |
| **The town** — once per project | `.orkcraft.json`, `.orkcraft/`, the order `.orkcraft/town/order.json` | The town · (the interview) |
| **The machine** — once per machine | `~/.config/orkcraft/settings.json` | Tools · Autonomy · The look and the hours |

```
Who are you? → Your day → What should your first town do? ─┬─ an intent ───────────────────┐
                                                            ├─ an empty town ──────────────┤
                                                            └─ none fits → Sources → Outputs │
                                                                 → Problems → AI tried ──────┤
  ┌─────────────────────────────────────────────────────────────────────────────────────────┘
  └→ Tools (+ the Warder) → Autonomy → The look and the hours → the town is raised
        an intent: its buildings and roads, no model · none fits: the Town Builder adapts the
        role's templates to the answers → the plan → approved → raised
```

- A project with no `.orkcraft.json` starts onboarding. A machine already onboarded skips the
  machine's part; one that also has a profile starts at the town.
- F10 → **🧭 Onboarding** asks who you are, your day and the machine's part again — never the town.
- Every step has `Esc` / **Back** (the first one: Esc = Skip); Back keeps what was chosen.
  **Skip** anywhere = an empty town, defaults for the rest, no Warder.
- The title counts the steps of this run: the interview adds four (“step 4 of 10”).
- Nothing is written before the last step. `--demo` never shows onboarding.

## 2. Who are you?

```
┌ 🧭 Who are you?  ·  step 1 of 6 ──────────────────────────────────────────────────────┐
│ Your role and where you work. Your first town starts from what people like you do.       │
│  I work as…                       …in                              \ .--. /            │
│  🛠 Software engineer             🎮 Gaming                          >( oO )<           │
│  🧭 Engineering manager           💳 Fintech                           \ww/  $          │
│  📋 Product manager               🛒 E-commerce                      .-|  |-/           │
│  🎨 Product designer              ☁️ SaaS / B2B                      | |  |             │
│ ▌📈 ASO manager                  ▌🎮 Gaming                          /GOBLIN\           │
│  📣 Marketing / growth manager    …                                                      │
│  …  🧩 Someone else [ your role, in your words ]                                         │
│ → ASO manager in Gaming · 3 ready towns for this role, or the Builder makes one with you │
│                                                              [ Skip ]  [ Next → ]        │
└──────────────────────────────────────────────────────────────────────────────────────────┘
```

- Ten roles and “Someone else”, nine industries and “Something else” (`realm/intents.py`);
  “else” opens a field for the operator's own words. A role is required, the industry is not.
- The mascot follows the role's family: engineers orc · designers elf · managers knight ·
  marketing and data goblin · founders and others skeleton.
- Stored: `profile.role`, `role_other`, `industry`, `industry_other`.

## 3. Your day

```
┌ 🧭 How does your day go?  ·  step 2 of 6 ───────────────────────────────────────────────┐
│ What fills a typical day, and what comes back on a schedule. The town takes over the     │
│ routine.                                                                                  │
│  A typical day is…                            It comes back as…                           │
│  [x] 📨 Inbox and messages                    [ ] ☀️ A daily summary or stand-up            │
│  [ ] 🗣 Meetings and syncs                    [x] 📅 A weekly report or sync              │
│  [x] 📈 Watching metrics and dashboards       [ ] 🚀 Releases or launches                 │
│  [x] 💬 Users, customers, reviews             …                                            │
│  …  [ a typical day in your words ]                                                       │
│                                                    [ ← Back ]  [ Skip ]  [ Next → ]       │
└──────────────────────────────────────────────────────────────────────────────────────────┘
```

- Multi-select (`SelectionList`): ten parts of a day, six rhythms, and a free field.
- What it is for: an intent lists the parts of a day it takes over (`Intent.day`); those that
  fit come first with ★. The Town Builder reads the day, the rhythm and the free text too —
  a weekly report becomes a schedule in a Watchtower.
- Stored: `profile.day`, `profile.rhythm`, `profile.day_other`.

## 4. What should your first town do?

```
┌ 🧭 What should your first town do?  ·  step 3 of 6 ─────────────────────────────────────┐
│ For ASO manager in Gaming  ·  ★ takes over a part of your day                             │
│ [ 🏰 Start with an empty town ]                                                           │
│  [ 📈 ASO manager ▾ ]                                               (the mascot)          │
│ ▌⭐ Review Desk  ★                                                                         │
│  🔑 Keyword Tracker  ★                                                                    │
│  🧪 Listing Lab                                                                           │
│  ❓ None fits — tell the Builder about your work                                          │
│  store reviews sorted, replies drafted for approval                                       │
│  🏗 🗼 Store reviews · 🗿 Review sorter · 🏕️ Reply writers · 📦 Replies to approve · …     │
│                                                    [ ← Back ]  [ Skip ]  [ Next → ]       │
└──────────────────────────────────────────────────────────────────────────────────────────┘
```

- **Intents** are ready towns for a job the role does: 3 per role, 33 in all. Each is a plan in the
  Town Builder's answer shape (buildings from the catalog, plain roads), checked by
  `town_builder.check` in the tests, and raised with **no model call**.
- The dropdown browses other roles' intents; the picked role is the one whose templates the
  Builder adapts.
- **🛡 The Warder** checkbox sits here only when the machine's part is not asked and `claude` is
  on; otherwise it is on the Tools step.
- **❓ None fits** adds the interview (§4b) before the machine's part.

## 4b. The interview — when none fits

Four pages, each a multi-select with a field for anything else; the role's common options come
first, marked ✦ (`Role.sources`, `Role.outputs`, plus the industry's, `INDUSTRY_SOURCES`).

| Page | Question | Options (some) |
|---|---|---|
| Sources | Where does your work come from? | Jira, Confluence, Linear, Asana, Notion, GitHub, Slack, Email, Calendar, Google Drive / Sheets, Figma, App Store Connect, Google Play Console, AppTweak / Sensor Tower, Amplitude / Mixpanel, Sentry, Zendesk, HubSpot, CSV / Excel, this repository |
| Outputs | Where does the result go? | Jira, Confluence, Asana, Linear, Notion, Slack, Email, Google Docs / Sheets, Figma, pull requests, store listings, reports in the repository, a dashboard in Orkcraft, a webhook or any API |
| Problems | What hurts in the way you work now? | copying between tools, reports take hours, things slip, notification noise, context switching, waiting on others, stale docs, the same routine every week, no single view |
| AI | Which AI have you tried, and what went wrong? | ChatGPT, Claude, Claude Code, Gemini, Copilot, Cursor, Zapier / n8n — no access to my data, copy-pasting context, forgets between sessions, makes things up, inconsistent, checking takes as long, security, cost |

The answers become the **order** (`town_presets.save_order(root, prompt, role, answers)`): the
prompt is `interview.summary` — one line per question, the operator's words included. Once the
camp stands, the **Town Builder** plans from it with the role's intents as templates
(`intents.templates_text`, the `ADAPT` block of the planner's prompt): start from the closest one,
give each source a way in (Watchtower webhooks and schedules, Pit, Scroll Dump, File Forest) and
each output a way out (Catapult to the tool's API, the token in an environment variable named by
`token_env`; Loot Vault for what is accepted first), answer each problem with a building or road,
and avoid what went wrong with AI before (a person's accept step, rules over agents). The plan
is checked like any other, reviewed (`screens/town_plan.py`) and raised; “Later” or a failed call
leaves the order burning 🔥 in the Town Hall, which keeps the role and the answers for a retry.

## 5. Tools

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

- **🛡 The Warder** for this project (same as `orkcraft hooks install`, it edits `.claude/settings.json`)
  is a checkbox here, on by default, when the run raises a town; Back keeps the tools picked.

## 6. Orc autonomy

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

## 7. The look and the hours

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

## 8. Raising the town

No separate progress screen: the town itself opens and the progress bar runs along its bottom.

1. create `.orkcraft/` and the camp's git (branch `camp`);
2. install the hooks / Warder (if checked);
3. for “none fits”: the order is saved;

then, on a bar of its own, an intent's buildings one by one and its roads
(`raise_town_plan`) — or the Town Builder for the order. An empty town ends with a toast:
`B` build · `P` presets · `?` all keys.

## 9. Edge cases

- A tool is found but not logged in — shown, unchecked, with the login command; checking it is allowed.
- A tool disappears later — the HUD greys its corner; no onboarding rerun.
- A narrow terminal — cards and the mascot stack or hide; the minimum is the list and the buttons.
- Onboarding interrupted (quit mid-way) — nothing is written until each step's Next; the project
  part is written only on **Build**.
- An existing `.orkcraft.json` — no onboarding; F10 → 🧭 Onboarding redoes who you are, your day and
  the machine's part.
- No tool chosen — intents are still raised (no model); “none fits” leaves the order in the Town Hall.

## 10. Later

- Industry-specific intents (an ASO town for a games studio differs from one for a bank).
- Real connectors for the named sources and outputs (Jira, Figma, Asana…) as building types,
  instead of webhooks and the Catapult.
- A follow-up question from the Builder when the answers contradict each other.
- `codex` support.
