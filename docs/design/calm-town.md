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
| 2 | one panel on the right: a building's Work and Info, Lake's documents as its tabs (§2) | done |
| 3 | no console: the War Map block, the status bar, Build, the Command Card and the advisor go; the right click (§1, §3) | done |
| 4 | the Warchief's line: `/` commands, `@` names, hints by rules — no model (§4) | done |
| 5 | the Warchief delegates: its answer's order goes to a specialist, its cards (§5–§7) | done |
| 6 | the Warchief speaks first, in its line (§8) | done |
| later | a plan's buildings as ghosts on the map; `@building` straight to its steward; the Foreman fills one building's settings | |

## 1. The screen

```
┌ HUD: project ▾ · Stop all · Answers (2) ·············· Spend · Context · Agents ┬──────────────────┐
│                                                     │ Forge  ? a question  ⤢ ✕   │
│        the map (it scrolls so that the open         │ [Work] [Info] │ a.py ✕     │
│        building and its neighbours stay seen)       │ …                          │
│                                                     │                            │
│ [+ Orkspace]   [🧌 Ask the Warchief… or / ]         │                            │
└─────────────────────────────────────────────────────┴────────────────────────────┘
```

- **The HUD** keeps what must never hide: the project (its settings), Halt All, **Orders** (the orks'
  questions, *Answers* in the Office; the status bar held it) and the treasury (`js/chrome.js`).
- **The map** is the screen. Nothing floats over it but the two controls at its foot.
- **The orkspaces**, bottom left, grow with use: one orkspace shows only `+ Orkspace`; two or more show
  their list (the one that asks marked) with `+` at its end. `+` asks a name (`orkspace.new` on the host).
- **The Warchief's line**, bottom middle of what the panel leaves (§4): the way to build, to command and to ask.
- **Gone:** the lower console (War Map block, Info, the garrison, Command Card), the status bar, the
  Office's advisor with its Build, and a building's window over the whole town (the panel's ⤢ does it).
  Camp keeps the Town Hall's hut in its corner, with *Ask me anything* on it.

## 2. One panel on the right

A click on a hut opens **the panel** (`js/windows.js`): the right half of the town. Lake and the
building's window no longer compete for that half: they are **one panel**.

- **Tabs.** The building's two first: **Work** (its view, `buildings/<type>.js` `panes`) and **Info**
  (`js/console.js`). Then the documents opened from anywhere (Lake's tabs, `js/lake.js`), each closable.
- **Info**, in the order it is needed: the name with 👍 / 👎, why it is here and its runs with History;
  its type's **quick actions**; the **garrison** (each ork, its status, Deploy or Its session); the
  **steward** (goal and Freedom, Watch, Report, Redesign, the roads it listens to with their handlers,
  + Listen); the **roads out**; Demolish at the bottom.
- **No view of its own:** its status lines in Work, or the panel opens on Info.
- **A question** of one of its orks stands above the tabs, whatever tab is open.
- **An ork** picked in the garrison or the steward's part opens in the same panel (its Info, its
  commands, its models and tools) with ← back, never in a new window.
- **Another building** clicked replaces the building's tabs; the documents stay.
- **⤢** takes the whole town, **✕** or Esc closes (Esc steps back first: whole → half, an ork → its
  building); a closed panel with documents waits as a handle at the right edge.
- **The map scrolls** when a building opens: the room grows by the panel's width, and the building and
  the buildings its roads reach are brought into the part left (all of them when they fit).
- The Town Hall's Work has a **Chat** tab: the whole conversation with the Warchief.

## 3. The right click

On a hut (`js/menu.js`): Open, Info, Listen to…, Ask the Warchief about it, Pin / Unpin, Demolish… — what
the Command Card had, without opening the panel. On the bare map: Build here… (the catalog, the
building raised where the click was), Tidy up (every hut that is not pinned laid out along its roads,
left to right, from the top left: `js/tidy.js`), Settings. An entry names the `/` command that does the same,
so the menu teaches the line.

## 4. The Warchief's line

One input at the town's foot (`js/warchief.js`). `/` or Ctrl+K focuses it from anywhere, Esc leaves it,
↑ / ↓ walk its history, Tab completes a command, Backspace on an empty line drops the last chip.

**Empty and focused**, it shows hints over itself. They follow the town's state, by rules, no model:

| the town | hints |
|---|---|
| an ork asks | "Answer N questions" — always first |
| a building open | "Add an ork to Forge" (`/recruit @Forge `), "Connect Forge to…" (+ Listen), "What did Forge do today?" |
| an empty orkspace | three starters ("I want my pull requests reviewed", …) and "Pick a building from the catalog" |
| otherwise | "Where does the gold go?" when spend is near its limit, "What happened today?", "Build something new", "Connect two buildings" |

**While typing:**

- `/` lists the **commands**, completed as typed; one runs at once, with no model — free, instant, and the
  way left when no model can be reached: `/build [what]` (the catalog, or the type named), `/road @from @to`
  (or `@into`: + Listen), `/recruit @building what it does` (the Recruiter), `/open @b`, `/demolish @b`,
  `/orders`, `/halt`, `/orkspace name` (goes there, or makes it), `/sessions`, `/audit`, `/settings`, `/new`.
  A command that misses a name says how to write it.
- `@` names a **building** (completed from the orkspace's). The building open in the panel stands in the
  line as a chip already, so "add an ork" needs no more words.
- Anything else goes to the Warchief, with the buildings named as what the person points at.

**The answer** unrolls over the line: its last messages, its cards, the hints. The whole chat is the
Town Hall's Chat tab. A press over the line never takes the focus from the field, so what it shows
stays put under the mouse.

## 5. The Warchief delegates

The Warchief does not build. It understands what the person wants, writes the order for the specialist
who does it, and brings back what they made (`core/warchief.py`). Its answer ends with at most one line:

| `DO: {…}` | who | where it runs |
|---|---|---|
| `{"plan": order}` | 🏗 Town Builder, then 🛡 the Council's Fast Path | the hall's worker, in a thread (`realm/town_builder.py`, `realm/fastpath.py`) |
| `{"build": type}` | one building of the catalog, its defaults | at once, no model |
| `{"road": into, "from": from, "order": …}` | the road planner | the GUI console's job (`gui/road_planner.py`) |
| `{"recruit": building, "order": …}` | the Recruiter, then the Council | the GUI console's job (`gui/recruiter.py`) |
| `{"keeper": building, "order": …}` | the building's keeper | the GUI console's job (`gui/keeper.py`) |

An order that names a type or a building that does not exist is dropped: the answer stays words. The
last three go out on the bus (`bus.ORDER`); the GUI host starts the console's job, and a refusal (a
building with no keeper, the budget spent) comes back on the card. Each specialist stays one call in an
empty folder: it sees the order and the catalog, never the project, and its answer is used only when it
passes its checks. The Warchief sees the town; the specialists see only its order. An older answer's
`BUILD: <type>` line still reads as a build.

```
you: I want my PRs reviewed
🧌:  I gave it to the Town Builder.
     Town Builder done ✓ · Council done ✓
     Review desk: Watchtower (listens to GitHub) · Council (two orks review) · 1 road · $0.04
     [Build] [Change] [Cancel]
```

## 6. Answers are cards

A card stands in its answer (`js/buildings/town_hall.js` `Card`), in the line and in the Chat tab alike:

1. **A plan.** The steps (Town Builder, Council) as they finish, then the buildings with why each, the
   roads, the cost and the Council's warnings: **Build · Change · Cancel**. Change goes on talking
   ("Change the plan: …"); a plan the Council blocks says why and cannot be built.
2. **A building.** Its type: **Build · Cancel**.
3. **A face's job.** Who has it and the order; its offer opens as the console's dialog when it is
   ready (the road to lay, the ork to hire, the change line by line) and nothing changes before the
   person takes it there.
4. **Done.** What it raised, and **Undo**: the buildings come down and the roads up.

## 7. When the Warchief asks first

| the act | how |
|---|---|
| reading: a status, what a building did, why it stands | an answer, no card |
| a road, an ork, a building's change | always through its offer (the console's job): Lay, Hire, Apply |
| a building or a plan | a card: Build — unless the town is **unchained** (Freedom ⛓️‍💥): then raised at once, with Undo |

Whatever is raised passed the Council first (a plan) or is the catalog's own (a building).

## 8. When the Warchief speaks first

Rarely, and in its line, never in a dialog: while the line is left alone it shows what wants a
decision — an ork's question (a click opens Orders on it), else spend near or over its limit (a click
asks it where the gold goes). Toasts stay for what is instant; the line is for what wants a decision.

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

The road planner got its Office word (*Link planner*) in `realm/lexicon.py` `TERMS`; the Warchief is the
*Lead agent* there already. The panel, the line and a card are plain words in both modes.
