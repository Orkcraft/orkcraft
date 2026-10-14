# Design — the development backlog to the launch, with what runs in parallel

Status: 2026-10-13, gathered from the decisions of 12–13 October ([decisions-2026-10.md](decisions-2026-10.md)).
Estimates are a product view in working days, not a promise. **∥** means it can run beside the others of its column
or another lane without waiting; **after X** means it waits for X. Each item merges when the critical tests pass
(CLAUDE.md).

## 1. The lanes

Five lanes can run at once; inside a lane, items mostly run in order.

| lane | what | touches |
|---|---|---|
| **A. Agents and status** | the way to ask, one status, the 🥩 list, the console | `core/`, `realm/`, `hooks/`, the console's views |
| **B. Small fixes** | the removals and defaults; then the onboarding | `quota/`, prompts, settings, `gui/` onboarding |
| **C. Camp's look** | colour, readability, the card as a building, rails, the catapult | `design-system/`, `gui/static/` (CSS, `town.js`, `roads.js`) |
| **D. The doors and the name** | PyPI, the Claude Code plugin, README, landing | packaging, `docs/`, a new plugin folder |
| **O. The owner, no code** | the name, the art, the tests on people, the terms | — |

**One collision to plan:** C3 (the card as a building) and A3/A4 (status, badges, the 🥩 list) both draw on the
building's card in `gui/static`; A3's data first, C3's drawing on top, not both at once in the same files.

## 2. P0 now (this week, by 18 October)

| id | item | lane | days | runs | where |
|---|---|---|---|---|---|
| B1 | Cursor's token reader out, or behind an explicit opt-in | B | 0.5 | ∥ | decisions §5 |
| B2 | "Warcraft" out of the shipped prompts, the design system and the docs listed | B | 0.5 | ∥ | open-questions Q18 |
| B3 | the night's work off in a new town | B | 0.25 | ∥ | cut-list |
| B4 | External listeners limited to GitHub, a schedule, a webhook, a file | B | 0.5 | ∥ | cut-list |
| B5 | agy marked experimental, off by default, with the account-ban warning | B | 0.25 | ∥ | decisions §5 |
| A0 | the local event log and its events (asked, assumed, answered, stopped; quest and install events) | A | 1 | ∥, first in A | dogfood-logs §3 |
| A1 | research R2: how Claude Code's run asks a question (its own form, an MCP tool, a block at the end) | A | 0.5 | ∥ with A0 | open-questions R2 |
| A2 | the way to ask, Claude Code only: questions pinned on top, assumptions marked, counted into A0 | A | 2 | after A0, A1 | ork-console §4, §20; decisions §8 |
| A3 | one status: waits that say why, until when and how to skip; the ork's cart named | A | 2 | ∥ with A2 once the status model is agreed | ork-console §5, §19; cart-waybill §4 |

**This week's critical path:** A0 → A2, about 3.5 days; everything in lane B beside it.

## 3. P0 before the launch (weeks 2–3)

| id | item | lane | days | runs | where |
|---|---|---|---|---|---|
| A4 | the 🥩 list with 🔥 · ❓, Stop all; the console folded | A | 2 | after A3 | ork-console §7, §8 |
| A5 | the console unfolded, and the Work panels it replaces removed | A | 3 | after A4 | ork-console §15; lighter-buildings |
| A6 | the Agent pool's lanes as roles | A | 1.5 | ∥ after A3 | ork-console §11 |
| W1 | "since your last look" (and on opening the laptop), wins first | A | 2 | after A0, A3 | audience §2a |
| W2 | quiet working hours (asked in the onboarding), questions gathered, assume-and-mark where safe | A | 1.5 | after A2 | audience §2a |
| W3 | "leaving the camp": the morning plan and cap, the Mac kept awake only while carts work | A | 1.5 | after W2 (`gui/awake.py` exists) | audience §2a |
| B6 | the onboarding cut: the AI tools found and the class, the rest to Settings | B | 1 | ∥ | first-mission §4 |
| B7 | Mission 1, quests 1–3 and 3½ (no model, free) | B | 3 | after A2, A4 (quest 2's ❓ and console) | first-mission §3 |
| B8 | quests 4–5; the hooks asked before quest 4, failing open | B | 2 | after B7 | first-mission §3; Q16 |
| C1 | the colour pass by tokens, forest only; Camp's UI off gold | C | 1.5 | ∥ | color-pass §3; Q18 |
| C2 | readability: outlines and shadows, yellow and red reserved (banners maroon), badges only for exceptions, a chip on a waiting cart | C | 1.5 | after C1 | town-readability |
| C3 | the card as a building for the five core buildings: cover lifting on zoom, facade, crest; signals on the cover; a sheet on the phone | C | 4 | after C1; after A3's data | color-pass §6a–6c |
| C4 | roads drawn as rails, carts as mine carts, loads and flags | C | 2.5 | ∥ with C3 (`roads.js`) | color-pass §6d |
| C5 | the ways in outside the wall, the Publisher's catapult at the end, the launch | C | 1 | after C4 | camp-story |
| C6 | the commissioned art put in (replacing generated sprites in what the GIF shows) | C | 1.5 | after O3 | color-pass §10 |
| D1 | Orkline (or its new name) on PyPI, published by CI | D | 1 | **after O1 (the name)** | distribution §3 |
| D2 | the Claude Code plugin: its hooks failing open, `/orkcraft`; its own marketplace | D | 3 | after D1, B8's hooks | distribution §3 |
| D3 | README's first screen, GitHub description, topics, preview image, the small disclaimer | D | 1 | drafts ∥ now; published after O1 | launch-prep §2a |
| D4 | the landing page | D | 2 | after O1, D5 | launch-prep §2b |
| D5 | the GIF: the camp → a ❓ answered → the cart through the gate → the catapult launch | D | 1 | after B7, C3–C5 (C6 for the public one) | audience §5; camp-story §2 |

## 4. The owner's lane (no code, beside everything)

| id | item | by |
|---|---|---|
| O1 | the name: the lawyer's hour on ORK and "-craft", Orcline and Orcworks checked, five developers asked | 17 October |
| O2 | the five-second test of the reference frame on three to five developers | this week |
| O3 | the letter to the artist (licence first, CC-BY 4.0), the commission | after O2; art in 3–6 weeks |
| O4 | Google's agy FAQ and terms, OpenAI's terms, read | this week |
| O5 | the community's home opened (after O1), the devlog's first post, the list of places, the testers' invitation | from 19 October |
| O6 | the first three testers, remote workers first | within two weeks |

## 5. P1, after the testers

The phone as the console (since your last look, the sheet, the camera on what waits); the town's clock and held work;
a cart's id, its waybill and its origin; Work gone type by type; the Town Hall's roles folded, then ork faces; the
score with "launched" and the 💡 list; the VS Code and Open VSX extension; each biome's palette; Q21 (the first look at
running sessions); research R3–R10.

## 6. The sum

- **Lane A** ≈ 17 days, **B** ≈ 8, **C** ≈ 14, **D** ≈ 8 (D waits on the name).
- **With three lanes of code at once** (A, B then C, D after the name), P0 before the launch is **about two and a half
  to three weeks**, its critical path lane A (A0 → A2 → A3 → A4 → A5) and the art (O3 → C6) for the public GIF.
- **This week:** lane B entire, A0–A3, C1 can start.
