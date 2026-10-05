# Design — onboarding

Status: design notes, written 2026-10-03, reworked on 2026-10-04 and on 2026-10-05: one operator
for now — an indie maker who already makes things with AI — and three steps. Who they are is not
asked: the role is the founder's (`intents.FOUNDER`), and the project shows the rest. Implemented
(`screens/onboarding.py`, `realm/intents.py`, `realm/interview.py`, `tools.py`). Builds on the quota
readers, the display modes, the Warder hooks, the Town Hall and the Town Builder
(`realm/town_builder.py`). Wording: ork, orkestration (CLAUDE.md).

## 1. The steps

```
1 Your AI tools — only the installed ones: ✓ lead · paid by  (looked for in the background from the start)
2 Your day — 🧌 Camp · 👔 Office · 🧌/👔 Shift · office hours · 🌙 do not disturb
3 What should your first town do? — the indie maker's three towns (★ fits this project) · ❓ None fits · 🏰 Empty town
     └─ None fits → a phrase, in the same step → the Town Builder
```

| Who | Steps | Count |
|---|---|---|
| a new machine | AI tools · your day · town | 3 |
| a known machine, a new project | the town only | 1 |
| F10 → 🧭 Onboarding | AI tools · your day — never the town | 2 |

- Kept per machine in `~/.config/orkcraft/settings.json` (`profile` = `{"role": "founder"}`, `tools`,
  `mode`, `quiet`, `office`); per project in `.orkcraft.json`, `.orkcraft/` and the order
  `.orkcraft/town/order.json`. Older profile keys (orkestration, industry, day, the 👍 / 👎 of the
  AI tools) are let go on the next save.
- Every step has `Esc` / **Back**; Back keeps what was chosen. **Skip** = an empty town, defaults for
  the rest, no Warder; the CLIs found are kept on.
- The orks' autonomy is not asked: it keeps its default (📜 Morning advice), a toast at the end
  says so, F10 → 🏛 Ork autonomy changes it.
- Nothing is written before the last step. `--demo` never shows onboarding.

## 2. Your AI tools

Only what is installed, one row each — found in the background since the start (`tools.detect`
for the CLIs orkcraft leads, `tools.detect_others` for the rest: Cursor, GitHub Copilot, the
ChatGPT app, Gemini CLI, Aider, Windsurf — a binary on PATH or their folder on disk; nothing is
run, no key is read).

```
tool                    paid by
[✓] Claude Code         subscription ▾
[✓] Antigravity         subscription ▾                not logged in
    Cursor                                            found — orkcraft does not run it
Not found: …
[✓] Install the 🛡 Warder in this project (recommended)
```

- The CLIs orkcraft leads get ✓ (on when found) and how they are paid for — subscription or API;
  the HUD corner follows it. Orkcraft never stores a key.
- The others are named only, so the operator sees they were found.
- The Warder checkbox is here when the run raises a town.

Stored: `tools` (enabled, billing).

## 3. Your day

The screen of F10 → 🕰 Your day: the look — 🧌 Camp · 👔 Office · 🧌/👔 Shift, as cards of the same
building — and the day bar with 🌙 do not disturb (the quiet hours, 23:00–08:00 when turned on) and,
for Shift, the 👔 office hours. Drag across the bar, or Tab to an edge and move it with ←/→.

Stored: `mode`, `quiet`, `office` (`office_days` stay as they are: F10 → 🕰 Your day).

## 4. What should your first town do?

The indie maker's three intents — ready towns, raised with no model — each named the ork way and
said plainly beside it:

| Town | What it does | ★ when the project shows |
|---|---|---|
| 🏚 One-Knight Studio | code, copy and releases in one town | code (`pyproject.toml`, `package.json`, `src/`…) or notes for agents (`CLAUDE.md`, `AGENTS.md`, `.cursorrules`…) |
| 📨 Inbox Keep | mail and GitHub sorted into tasks | a GitHub remote in `.git/config`, or `.github/` |
| 🧪 Side Quest | a light town for a pet project | next to nothing yet: no code and three things or fewer in the folder |

The ★ ones come first, the reason under the highlighted one (“★ code and CLAUDE.md here”), its
buildings beside it (`intents.project_fit`; only names and the git config are read).
**❓ None fits** — closed with a note when Claude Code is off — opens a field in the same step: in
a phrase, what the town should do. **🏰 Empty town** sits at the bottom, beside the buttons.

## 5. None fits — a phrase for the Town Builder

The order (`interview.summary`) is three lines: who (an indie maker who already works with AI
agents), what is in the project (`intents.signs_text`: code, notes for agents, GitHub), and the
phrase. The Town Builder starts from the three templates (`ADAPT`): every source named needs a way
in (every webhook through a Watchtower), every output a way out, code goes through a Forge. The
plan is reviewed and raised; Later leaves the order burning 🔥 in the Town Hall.

## 6. Raising the town

No separate progress screen: the town itself opens and the progress bar runs along its bottom.

1. create `.orkcraft/` and the camp's git (branch `camp`);
2. install the hooks / Warder (if checked);
3. for “none fits”: the order is saved;

then, on a bar of its own, an intent's buildings one by one and its roads
(`raise_town_plan`) — or the Town Builder for the order. An empty town ends with a toast:
`B` build · `Y` roads · 🏰 Town Hall → 📜 Preset or 🛠 New.

## 7. Edge cases

- A tool is found but not logged in — shown, checked, with "not logged in" beside it.
- A tool disappears later — the HUD greys its corner; no onboarding rerun.
- A narrow terminal — the mode cards stack; a short one (under 52 rows, 80 when stacked) hides them,
  the radios stay; the minimum is the list and the buttons.
- Onboarding interrupted (quit mid-way) — nothing is written until the last step; the project part
  is written only on **Build**.
- An existing `.orkcraft.json` — no onboarding; F10 → 🧭 Onboarding redoes the AI tools and the day.
- A profile from before (another role) — read as the indie maker's; the next save keeps only that.
- No tool chosen — intents are still raised (no model); “none fits” is closed without Claude Code.

## 8. Later

- Other roles again (engineers, managers, designers, ASO, data) — their towns and the questions
  about who one is were taken out on 2026-10-05; git history has them.
- More from the project for the ★: the languages, CI, an issue tracker named in the README.
- Real connectors for the sources and outputs named (Jira, Figma, Asana…) as building types,
  instead of webhooks and the Catapult.
- Picking each building's model from the AI tools found.
