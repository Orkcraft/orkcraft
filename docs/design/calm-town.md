# Design — a calm town: the map, one panel, the Warchief

The town took the whole screen of a real-time strategy game, its console included: a War Map, an
Info panel with the garrison, a Command Card of keys, a status bar, a Build button, and a building's
window over the whole town. A player of a strategy game moves a hundred units a minute and needs that
console. A person who runs orks mostly **watches**: who works, who asks, what it costs. They answer a
question, open a building, sometimes build one. The console held the screen for the rare action.

The metaphor stays in the map, the buildings, the roads and the orks. The console goes. What is left
is the map, one panel on the right, and one line to the Warchief, who does the rest with its clan.

| stage | what | state |
|---|---|---|
| 1 | the TUI deprecated: the window is the default, the TUI gets no new features (§9) | done |
| 2 | one panel on the right: a building's Work and Info, Lake's documents as its tabs (§2) | next |
| 3 | no console: the War Map, the status bar, Build and the Command Card go; the right click (§1, §3) | |
| 4 | the Warchief's line: `/` commands, `@` names, hints by rules — no model yet (§4) | |
| 5 | the Warchief delegates: tools over the specialists, answers as cards (§5–§7) | |
| 6 | the Warchief speaks first, in its line (§8) | |

## 1. The screen

```
┌ HUD: project · 🪙 🪵 · ❓ Orders (2) · Halt All ─────┬─────────────────────────────┐
│                                                     │ ⚒ Forge   ❓ a question  ⤢ ✕ │
│        the map (it pans so that the open            │ [Work] [Info] │ 📄 a.py ✕    │
│        building and its neighbours stay seen)       │ …                           │
│                                                     │                             │
│ [+ Orkspace]   [🧌 Ask the Warchief…            ⏎]  │                             │
└─────────────────────────────────────────────────────┴─────────────────────────────┘
```

- **The HUD** keeps what must never hide: the project (its settings), the treasury, **Orders** (the
  orks' questions, *Answers* in the Office; the status bar held it) and 🛑 Halt All.
- **The map** is the screen. Nothing floats over it but the two controls at its bottom.
- **The orkspaces**, bottom left, grow with use: one orkspace shows only `+ Orkspace`; two or more show
  their list (the War Map's rows, the alert on the one that asks) with `+` at its end.
- **The Warchief's line**, bottom middle (§4): the way to build, to command and to ask.
- **Gone:** the lower console (War Map block, Clan Roster, Command Card), the status bar (Orders goes
  to the HUD, the project's folder to the project's settings), the Build button (the Warchief and
  `/build`), and a building's window over the whole town (the panel's ⤢ takes its place).

## 2. One panel on the right

A click on a building opens **the panel**: the right half of the town, as Lake's window is now
(`js/lake.js`). Lake and the building's window stop competing for that half: they become **one panel**.

- **Tabs.** The building's two first: **Work** (its view, `js/buildings/<type>.js`) and **Info**. Then
  the documents opened from it, as Lake's tabs, each closable.
- **Info**, in the order it is needed: the **garrison** (each ork, its status, Deploy or Its session),
  the **steward** (goal and Freedom), the **roads** in and out, **about**, and Demolish at the bottom.
  The garrison and the old Info panel are one tab: neither filled a tab of its own.
- **No view of its own** (a type whose window draws only status lines): the Work tab is not shown,
  the panel opens on Info.
- **A question** of one of its orks stands above the tabs, whatever tab is open.
- **An ork** picked in the garrison opens in the same panel (its session, its chat) with ← back, never
  in a new window.
- **Another building** clicked replaces the building's tabs; the documents stay.
- **⤢** takes the whole town, **✕** or Esc closes, and a closed panel with documents waits as a handle
  at the right edge — Lake's behaviour, which the person knows already.
- **The camera** pans when the panel opens, so the building and the buildings its roads reach stay in
  the half of the map left.

## 3. The right click

A right click on a building opens its menu: Recruit, Lay a road, Chronicles, Pin, Demolish — what the
Command Card had in the building state, without opening the panel. A right click on the empty map:
Build here, the orkspace's settings. Every entry names its `/` command (§4), so the menu teaches the
line.

## 4. The Warchief's line

One input, bottom middle. `/` or Ctrl+K focuses it from anywhere, Esc leaves it, ↑ walks its history.

**Empty and focused**, it shows three or four hints over itself. They follow the town's state, by
rules, without a model:

| the town | hints |
|---|---|
| empty | the role's ready towns (`realm/intents.py` `for_role`), and "Tell me what you do" (the interview, `realm/interview.py`) |
| an ork asks | "❓ Answer 2 questions" — always first |
| a building selected | "Add an ork to Forge", "Connect Forge to…", "What did Forge do today?" |
| a building idle, a road failing, the budget at 80% | "Forge has stood 2 h — why?", "Where does the gold go?" |
| a building just raised | "Connect Watchtower → Forge?" |

**While typing:**

- `/` lists the **commands**, completed as typed: `/build`, `/road`, `/recruit`, `/demolish`, `/halt`,
  `/orkspace`. A command runs at once, with no model: free, instant, and the way left when no model
  can be reached. `B` and the other keys stay as shortcuts to the same commands.
- `@` names a **building or an ork**: `@Forge`, `@Grok`. The building selected on the map stands in the
  line as a chip already, so "add an ork" needs no more words.
- Anything else goes to the Warchief (§5).

**The answer** unrolls over the line as a short thread: the last two or three messages. The whole chat
is the Town Hall's Work tab. The panel does not open for an answer.

## 5. The Warchief delegates

The Warchief does not build. It understands what the person wants, writes the order for the
specialist who does it, and brings back what they made. The specialists stand already:

| who | what | where |
|---|---|---|
| 🏗 Town Builder | a whole town's plan from words | `realm/town_builder.py` |
| Foreman | one building of the catalog, its settings filled | `realm/builders.py` `propose` |
| Road planner | a road from what a building should listen to | `realm/road_planner.py` |
| Recruiter | the ork that handles a road: chain → script → agent → hybrid, the cheapest that can | `realm/recruiter.py` |
| 🛡 Council Fast Path | reviews whatever was made: budget, schemas, security | `realm/fastpath.py` |
| a building's steward | everything about its one building | its garrison |

Each specialist is one call in an empty folder: it sees the order and the catalog, never the project,
and its answer is used only when it passes its checks. That stays. The Warchief sees the town; the
specialists see only its order.

**Where a line goes:**

| the line | goes to | model |
|---|---|---|
| `/build forge`, `/halt`, `/road …` | the command | none |
| a ready town picked from the hints | `intents`, raised as it is | none |
| `@Forge why does it stand?` | Forge's steward, past the Warchief | one call |
| "add an ork that …" | Warchief → Recruiter → Council | yes |
| "I want my PRs reviewed" | Warchief → Town Builder → Council | yes |
| "what happened today?" | the Warchief, from the town's state | one call |

`@` matters: a question about one building goes straight to its steward — faster, cheaper, and the
Warchief is no bottleneck.

**In the code:** the Warchief gets **tools** that are orders — `plan_town`, `propose_building`,
`plan_road`, `recruit`, `ask_steward`, `status`. Each calls the specialist as it is and returns its
checked result as data, which the page draws as a card (§6). Its one-shot calls become a session that
keeps the town's context. `BUILD_LINE` (a building's id hidden in its text) goes. No specialist changes.

**While they work** the card shows the steps as they happen — this is also what makes the wait of a
chain of calls bearable:

```
you: I want my PRs reviewed
🧌:  I gave it to the Town Builder.
     🏗 Town Builder plans…            ✓
     🛡 the Council reviews…            ✓  (Treasurer: ~🪙0.2 a PR)
     [the plan on the map: 2 buildings, 1 road]   [Build] [Change] [Cancel]
```

## 6. Answers are cards

1. **A plan.** Ghost buildings and dashed roads on the map itself (`widgets/ghost.py` and the raising
   of an approved plan show the way), and in the card the list and the cost: **Build · Change ·
   Cancel**. Change is simply going on talking: "without the Watchtower".
2. **A choice.** Options as chips, not an open question: "Where do the tasks come from? [GitHub
   Issues] [Linear] [Other…]" — the interview's mechanics.
3. **A summary.** "Today: Forge closed 3 PRs, the Pit waits for an answer." Building names are links;
   a hover lights the building on the map.
4. **Done.** "✓ Grok joined the Forge" and **Undo** for a few seconds.

## 7. When the Warchief asks first

By how reversible and how costly an act is:

| the act | how |
|---|---|
| reading: a status, what a building did, why it stands | at once |
| cheap and reversible: an ork, a road, a rename | at once, with Undo |
| building, demolishing, anything that costs gold or touches code | only through a plan card |

The town's **Freedom** sets the line: unchained, the Warchief builds and offers Undo; in chains,
every change is a card. Whatever it makes still passes the Council.

## 8. When the Warchief speaks first

Rarely, and in its line, never in a dialog:

```
[🧌 ❓ The Pit asks about the migration · answer   |  Ask the Warchief… ]
```

An ork's question, a building idle for hours, a road failing, the budget. Toasts stay for what is
instant; the line is for what wants a decision.

## 9. The TUI is deprecated

`orkcraft` opens the window (`orkcraft gui`) when its packages are installed. `orkcraft tui` opens
the terminal UI, which says on start and on exit that it is deprecated. Without the window's packages
the TUI opens as before.

- New features go to the GUI only. The TUI gets fixes, nothing else; `tui/wording.py` and the TUI's
  views are not extended for a new feature.
- `core/`, `realm/` and `design/` keep no face (`tests/test_architecture.py`): that protects the
  core, whatever face it has.
- In a release or two: `tui/`, `screens/`, `widgets/`, `wm/`, `app.py` and the Textual and Rich
  dependencies go. A remote machine without a display uses `orkcraft gui --browser` over a
  forwarded port.

## 10. Words

New concepts get their pair in `realm/lexicon.py` `TERMS` when they are built: the panel, the
Warchief's line, a plan card. In the Office the Warchief is the *Lead agent* already.
