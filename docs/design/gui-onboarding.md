# Design — onboarding in the GUI

Status: written 2026-10-07; a first cut stands (`gui/onboarding.py`, `js/onboarding.js`, `static/onboarding.css`,
`realm/mcp.py`). It replaces the TUI's onboarding ([onboarding.md](onboarding.md)) in the window. The TUI keeps
its own until it is removed (CLAUDE.md: new features go to the GUI). The design canvas, with every screen for a
gnome: https://claude.ai/artifact/9cbL7oNunN9RFti2nb82te. Wording: ork, orkestration; plain words for what a thing
does (`realm/lexicon.py`): Town planner, External listeners, Agent pool, Output, Publisher.

## 1. The steps

```
1 Your AI tools                 always · + Request a tool
2 Who are you?                  without --role: all 11 classes in two rows; --role gnome: the 2 gnomes
3 Tools the orks can use        only when an MCP server is connected to an AI tool
4 Your first town               the class's towns, drawn · Use this town · Doesn't fit · Empty town
  4b What should your town do?  only on "Doesn't fit": one sentence (3 examples) · what it uses, prefilled
5 Setting up the town           over the map: the steps live, the Autonomy card in a corner
```

| Who | Screens |
|---|---|
| a Growth-Hack Gnome from orkcraft.dev (`--role marketing`), no MCP | 1 · 4 · 5 |
| a gnome from orkcraft.dev (`--role gnome`) | 1 · 2 (the two gnomes only) · (3) · 4 · 5 |
| a gnome with no `--role`, MCP connected | 1 · 2 · 3 · 4 · 5 |
| "Doesn't fit" | … 4 · 4b · 5 (the planner draws the town first) |
| Skip, from any step but the first | an empty town; the tools found stay on; no Security reviewer |

What changed from the TUI, and why:

- **"How well do you know orkestration?" is gone.** It chose three things, and each has a new home: the punk
  ork's path is **Empty town, I'll build it myself** on step 4; Skip is allowed everywhere (the run is 3–5
  screens); what the planner reads of a person's experience comes from the tools and MCP servers they have.
- **Industry and the typical day are gone.** They only ordered the intents (★); the town step now shows the
  class's towns as tabs, the first one starred.
- **👍 / 👎 per tool is gone.** Only the planner read it; how a tool is rated belongs to an Agent pool's window,
  where it picks the model.
- **The camp rules are no longer a step.** They are a card over the map while the town goes up (§6): nothing
  waits on them, and Later keeps the defaults.

Every answer goes to the host at once (`onboarding.*` commands); the host decides the next step and the
page draws what the snapshot's `onboarding` says. Nothing of the machine is written before step 4 is answered.

## 2. Your AI tools

Only what is installed: one row each with ✓ (orks run on it), its version, whether it is logged in, and how it
is paid for. `tools.detect` runs on a thread from the first frame; the step says "Looking…" until it is in.
Below: the other AI tools found (`tools.detect_others`: Cursor, Copilot…), which orks can't run on yet, and
the Security reviewer checkbox (on; it installs the Warder hooks when the town is set up, as the TUI did).

**Request a tool** opens a small dialog: the tool's name, a link, what orks would do with it. It opens a GitHub
issue in the browser, filled in (`onboarding.request` returns the URL). Nothing is sent from Orkcraft: the
person submits it there. No backend, no usage event.

## 3. Who are you?

Every class at once, one card per role, in two rows (6 + 5): Burnout Peon, Bug Ork, The Jira Lich, Roadmap
Wraith, Gradient-Sick Elf, Lore Elf, Keyword Gnome, Growth-Hack Gnome, Data-Mining Goblin, Indie Knight,
Wandering Skeleton (Someone else). Each card is its nick and its role, the role's own mascot at stage 1
(`design-system/sprites/mascots/<role>-1.png`) on its kin's biome ground (`--glyphs` of `js/terrain.js`), so
the two gnomes are told apart by their own gear. One click picks it; there is no second question.

- `orkcraft --role <role>` (`--role marketing`) or a class with one role (`--role knight`) skips this screen
  (`settings.preset_role`).
- A class with two roles from the landing page (`--role gnome`, `peon`, `lich`, `elf`) is kept as `profile.kin`
  (`intents.class_kin`): this screen shows only that kin's two cards, side by side ("Two kinds of gnomes…").
  A machine that finished an onboarding is never asked again. The TUI still opens on the class's first role
  (`intents.CLASSES`).

Stored: `profile.role`, `profile.kin`.

## 4. Tools the orks can use (MCP)

`realm/mcp.py` reads the MCP servers already connected to the AI tools: `~/.claude.json` (global and this
project's), `.mcp.json`, `~/.codex/config.toml` (`[mcp_servers]`), `~/.gemini/settings.json`. **Names only**:
never a command, an argument, an environment variable, a header or a URL, since those may hold a token. A
server in several tools is one row with each tool named. The step appears only when one is found; all start on.

The ones on go to the Town planner (the order says "MCP servers the orks may use: …") and are kept as
`profile.mcp`. Their glyph (`gui/static/icons/services`, a letter for a service with none) is drawn on the
buildings whose orks call them: the **Agent pool** and the **Publisher**. An MCP server is a tool an agent
calls, not a source of events: an **External listener** that should hear a service needs a Login and a
webhook (the Watchtower's own Add a source), never an MCP server.

**To do:** give each Agent pool raised from the onboarding the servers it needs in its agents' settings
(the allow-list of `mcp__<server>__*`), and show them in its window. It belongs with each tool's own way of
allowing a server: a field of each tool in the registry (`realm/harnesses.py`, docs/design/harnesses.md).
The servers are read from all six tools already (`realm/mcp.py`: Hermes' `mcp_servers`, pi's and Cursor's
`mcp.json`).

## 5. Your first town

The class's towns (`intents.for_role`), one tab each, the first starred. Each is drawn on the class's ground:
the buildings' header sprites in a row joined by roads, a plate with each one's name and what it does, and the
MCP glyphs on the agents. Below: **How it works** (the plan's summary) and three buttons.

- **Use this town** → step 5 with that plan (`town_builder.check`; no model call).
- **Doesn't fit: tell the planner** → 4b. Closed, with a line, when no AI tool that can plan is on.
- **Empty town, I'll build it myself** → step 5 with nothing to raise.

### 4b. What should your town do?

One question, the rest prefilled, so the page asks for one sentence and a glance instead of forty choices:

- **What should your town do?** One or two sentences in the person's words: the only thing asked.
  **Build my town** waits for it.
- **Or start from one of these:** three examples for the class (`interview.STARTERS`), not its ready
  towns, which the person has just passed over. A click puts the sentence in the field to edit.
- **The planner will use:** at most six chips, already chosen. First the MCP servers turned on in step 3
  (four at most), then where the class's work usually comes from and goes to (`Role.sources`,
  `Role.outputs`), skipping one an MCP server already names and a second Slack. A click leaves one out
  (an MCP server left out here is turned off); **+ add** names one more in a word.

Gone from the first cut: what hurts (the sentence says it), and what each AI tool is best at (the planner
has the list of tools; how a tool is rated belongs to an Agent pool's window, where it picks the model).

The order (`town_presets.save_order`) is the class, the kept sources and outputs, what was added, the
MCP servers on and the sentence. Step 5 draws the town from it first (`town_builder.plan` on a thread). If
that fails, the step says so and the order waits in the Town Hall, as before.

## 6. Setting up the town

No full-screen progress bar: the onboarding leaves and the town is drawn, and the buildings go up on the map one
step a tick (`RAISE_STEP_S`, the host's clock), so each one appears in front of the person.

- **Bottom left, the log:** every step with ✓ done, ⚒ now (it bobs; still under `prefers-reduced-motion`),
  · next, ✗ failed. While the planner draws: "The town planner is drawing your town…". At the end:
  **Open the town**, which closes the onboarding.
- **Bottom right, the Autonomy card:** "While they build: how free are your orks?" with the three levels
  (`town.settings`, `town.settings.set`, as Settings uses them). Later and Done put it away; the default stands.
- **On the map, the plan first.** Each building's spot is chosen before it stands (four across, as a hut
  without a spot), so the whole town is drawn at once as dashed plans where it will be (`js/town.js` with
  `Ghost`). The one going up now is scaffolding, its sprite rising out of the ground; when it stands, its hut
  rises into the same place once (`is-fresh`). No motion under `prefers-reduced-motion`.
- **Quiet hours** on the Autonomy card: 23:00–08:00 on or off (`onboarding.quiet`; the hours themselves in
  Settings).
- **The class's ground at once:** the first orkspace takes the class's biome when the town is chosen
  (`biomes.home_of`), so the plan is drawn on it.

The planner (4b) runs on the machine's main tool (`builders.planner_runner`: the chosen main tool if it is
on, else the first on). The Security reviewer is installed when any AI tool is on: its hooks guard all six.

## 7. Where it lives

| Part | File |
|---|---|
| The MCP servers, names only | `orkcraft/realm/mcp.py` (no face; tests/test_mcp.py) |
| The steps, the answers, the raising queue | `orkcraft/gui/onboarding.py` (the host's `onboarding`; tests/test_gui_onboarding.py) |
| The screens and the cards over the map | `orkcraft/gui/static/js/onboarding.js` |
| Their look, from the design system's tokens only | `orkcraft/gui/static/onboarding.css` |

The host turns it on for a first run (`Town.first_run`: no layout for the project yet), unless
`ORKCRAFT_ONBOARDING=0` or the demo. Commands: `onboarding.tools` · `.request` · `.role` · `.mcp` ·
`.town` · `.survey` · `.back` · `.skip` · `.close` · `.quiet` · `.start` · `.cancel`.

**Set up again** (the bare map's right-click menu, `onboarding.start`): your AI tools, who you are (every class)
and the MCP servers once more, on a town that stands, never the town step. What was chosen before is kept on
the first screen; the answers are saved when the last step is answered; Cancel leaves with nothing saved.

**To do:** move the shared parts of `screens/onboarding/flow.py` here once the TUI is gone.
