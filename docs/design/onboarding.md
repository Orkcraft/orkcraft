# Design — onboarding

Status: design notes, written 2026-10-03, reworked on 2026-10-04: five steps on the usual path.
How well the operator knows orkestration picks the path; who they are and their day are one
screen; the AI tools installed are one screen, rated 👍 / 👎; then the town; the camp rules last.
Implemented (`screens/onboarding/`, `screens/autonomy.py`, `realm/intents.py`,
`realm/interview.py`, `tools.py`). Builds on the quota readers, the display modes, the Warder
hooks, the Town Hall and the Town Builder (`realm/town_builder.py`). Wording: ork, orkestration
(CLAUDE.md).

## 1. The steps

```
1 How well do you know agent orkestration?  ── (the AI tools are looked for in the background from here)
  ├─ 🐣 new / 🪓 some
  │    2 Who are you? — role · industry · a typical day (chips in the role's words)
  │    3 Your AI tools — only the installed ones: ✓ lead · paid by · 👍 / 👎 · good for / weak at
  │    4 What should your first town do? — the role's intents (★ fits your day) · None fits · 🏰 Empty town
  │        └─ None fits → 5 Where work comes from and goes · 6 What hurts
  │    5 (7) Camp rules — ork autonomy · the look · quiet hours
  └─ 🤘 punk ork
       2 Your AI tools · 3 Camp rules → an empty town to build themselves
```

| Who | Steps | Count |
|---|---|---|
| 🪓 some, an intent | orkestration · who + day · AI tools · town · camp rules | 5 |
| 🐣 new, none fits | the same + 2 interview pages; no Skip after the first step | 7 |
| 🤘 punk ork | orkestration · AI tools · camp rules → empty town | 3 |
| a known machine, a new project | the town only (a punk ork: an empty town, no questions) | 1 / 0 |
| a known machine, no profile yet | orkestration · who + day · town | 3 |
| F10 → 🧭 Onboarding | orkestration · who + day · AI tools · camp rules — never the town | 4 |

- Kept per machine in `~/.config/orkcraft/settings.json` (`profile`, `tools`, `autonomy`, `mode`,
  `quiet`); per project in `.orkcraft.json`, `.orkcraft/` and the order `.orkcraft/town/order.json`.
- Every step has `Esc` / **Back** (the first one: Esc = Skip); Back keeps what was chosen.
  **Skip** = an empty town, defaults for the rest, no Warder; the CLIs found are kept on.
- Nothing is written before the last step. `--demo` never shows onboarding.

## 2. How well do you know agent orkestration?

| Answer | Path |
|---|---|
| 🐣 **New to it** — chats with AI, never ran agents | everything, walked through: no Skip after this step |
| 🪓 **Some** — Claude Code, Cursor, rarely more than one agent | everything, Skip allowed |
| 🤘 **Punk ork** — orkestrates agents already | AI tools and camp rules, then an empty town and a toast on how to build it |

The Town Builder reads it: new to orkestration → fewer buildings and an accept step.

## 3. Who are you?

One screen: the role (10 + Someone else), the industry (9 + Something else, both with a field for
one's own words), the mascot, and **a typical day as chips** in the role's words — an ork's start
with ⌨️ Writing code · 🧪 Tests and CI · 🚢 Deploys, a lich's with 📋 Status updates · 👥 1:1s ·
🤝 Hiring, an elf's with 🎨 Mockups…, then the general ten (Inbox, Meetings, Reviews, Reports,
Metrics, Planning, Users, Research, Incidents, Hands-on work), and a field for the day in one's own
words. A role's own part counts as its general one for the intents (`interview.DAY_AS`: writing
code → hands-on work), so ★ still finds the towns that fit.

| Role | Kin | Mascot |
|---|---|---|
| Software engineer · QA engineer | orks | Merge Ork · Bug Ork |
| Engineering manager · Product manager | undead | Jira Lich · Roadmap Wraith |
| Product designer · Game designer | elves | Figma Elf · Lore Elf |
| ASO manager · Marketing / growth | gnomes | Keyword Gnome · Funnel Gnome |
| Data analyst | goblins | Dashboard Goblin |
| Founder / indie maker | knights | Indie Knight |
| Someone else | skeletons | Wandering Skeleton |

Stored: `profile.orchestration`, `role`, `role_other`, `industry`, `industry_other`, `day`, `day_other`.

## 4. Your AI tools

Only what is installed, one row each — found in the background since the first step
(`tools.detect` for the CLIs orkcraft leads, `tools.detect_others` for the rest: Cursor, GitHub
Copilot, the ChatGPT app, Gemini CLI, Aider, Windsurf — a binary on PATH or their folder on
disk; nothing is run, no key is read).

```
tool                    paid by          👍 👎  what for
[✓] Claude Code         subscription ▾   👍 👎  documentation ▾   tickets ▾
[✓] Antigravity         subscription ▾   👍 👎                              not logged in
    Cursor                               👍 👎                    weak at… ▾
Not found: …
[✓] Install the 🛡 Warder in this project (recommended)
```

- The CLIs orkcraft leads get ✓ (on when found) and how they are paid for — subscription or API;
  the HUD corner follows it. Orkcraft never stores a key.
- Every tool gets 👍 and 👎; a 👍 opens **good for**, a 👎 **weak at**: code · architecture ·
  documentation · search (web, Jira) · tickets. One tool can be both — liked for docs, weak at
  tickets. The cells keep their columns when hidden, so the screen stays a table.
- What it is for: a test of how people find the tools they use, and later the choice of models.
  The Town Builder reads it today: work a tool is liked for may go to agents, work it is weak at
  gets a person's accept step or a rule.
- The Warder checkbox is here when the run raises a town.

Stored: `tools` (enabled, billing) and `profile.ai_tools` = {tool: {title, like, good, dislike, weak}}.

## 5. What should your first town do?

The role's three intents — ready towns, raised with no model — each named the ork way and said
plainly beside it (“⭐ Review War Tent — store reviews sorted, replies drafted”), those that fit
the day first with ★; the buildings of the highlighted one below. A dropdown browses other roles'
intents. **❓ None fits** — closed with a note when Claude Code is off — opens the interview.
**🏰 Empty town** sits at the bottom, beside the buttons.

## 5b. The interview — when none fits

Two pages, multi-select, the role's common options first (✦):

| Page | Questions |
|---|---|
| Where does your work come from, and where does it go? | sources (Jira, Confluence, the stores, analytics…) · outputs (Asana, Figma, Sheets, a webhook…) |
| What hurts in the way you work now? | the problems, and anything else the Builder should know |

What went wrong with AI is no longer asked: the 👎 on the tools step says it per tool. The answers
become the order; the Town Builder adapts the role's intents to it (`ADAPT`): every webhook comes
in through a Watchtower, every output gets a way out, every problem a building or a road. The plan
is reviewed and raised; Later leaves the order burning 🔥 in the Town Hall.

## 6. Camp rules

The ork autonomy slider (⛓️ In chains · 🕰 On the clock · ⛓️‍💥 Unchained — docs/design/barracks-planning.md §2 — with what
each means and the agents' own settings to copy) and, below it, the look — 🧌 Camp · 👔 Office ·
🧌/👔 Shift — and 🌙 quiet hours 23:00–08:00 on or off. The hours themselves and the office days
are F10 → 🕰 Your day (the day bar); the slider alone is F10 → 🏛 Ork autonomy.

## 7. Raising the town

No separate progress screen: the town itself opens and the progress bar runs along its bottom.

1. create `.orkcraft/` and the camp's git (branch `camp`);
2. install the hooks / Warder (if checked);
3. for “none fits”: the order is saved;

then, on a bar of its own, an intent's buildings one by one and its roads
(`raise_town_plan`) — or the Town Builder for the order. An empty town ends with a toast:
`B` build · `P` presets · `?` all keys.

## 8. Edge cases

- A tool is found but not logged in — shown, checked, with "not logged in" beside it.
- A tool disappears later — the HUD greys its corner; no onboarding rerun.
- A narrow terminal — cards and the mascot stack or hide; the minimum is the list and the buttons.
- Onboarding interrupted (quit mid-way) — nothing is written until each step's Next; the project
  part is written only on **Build**.
- An existing `.orkcraft.json` — no onboarding; F10 → 🧭 Onboarding redoes orkestration, who you
  are, your AI tools and the camp rules.
- Skip before the tools step — the CLIs found in the background are kept on.
- No tool chosen — intents are still raised (no model); “none fits” leaves the order in the Town Hall.

## 9. Later

- Industry-specific intents (an ASO town for a games studio differs from one for a bank).
- Real connectors for the named sources and outputs (Jira, Figma, Asana…) as building types,
  instead of webhooks and the Catapult.
- A follow-up question from the Builder when the answers contradict each other.
- Picking each building's model from the 👍 / 👎 (today the Builder only reads them).
- Day chips per industry, not only per role.
