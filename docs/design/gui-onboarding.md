# Design — onboarding in the GUI

Status: written 2026-10-07; a first cut stands (`gui/onboarding.py`, `js/onboarding.js`, `static/onboarding.css`,
`realm/mcp.py`). It replaces the TUI's onboarding ([onboarding.md](onboarding.md)) in the window. The TUI keeps
its own until it is removed (CLAUDE.md: new features go to the GUI). The design canvas, with every screen for a
gnome: https://claude.ai/artifact/9cbL7oNunN9RFti2nb82te. Wording: ork, orkestration; plain words for what a thing
does (`realm/lexicon.py`): Town planner, External listeners, Agent pool, Output, Publisher.

## 1. The steps

```
1 Your AI tools                 always · + Request a tool
2 Who are you?                  only without --role · 7 classes on their biome's ground
2b Which gnome are you?         only for a class with two roles (orks, undead, elves, gnomes)
3 Tools the orks can use        only when an MCP server is connected to an AI tool
4 Your first town               the class's towns, drawn · Use this town · Doesn't fit · Empty town
  4b Tell the town planner      only on "Doesn't fit": in · out · what each tool is best at · words · what hurts
5 Setting up the town           over the map: the steps live, the Autonomy card in a corner
```

| Who | Screens |
|---|---|
| a gnome from orkcraft.dev (`--role marketing`), no MCP | 1 · 4 · 5 |
| a gnome with no `--role`, MCP connected | 1 · 2 · 2b · 3 · 4 · 5 |
| a goblin with no `--role` (one role) | 1 · 2 · (3) · 4 · 5 |
| "Doesn't fit" | … 4 · 4b · 5 (the planner draws the town first) |
| Skip, from any step but the first | an empty town; the tools found stay on; no Security reviewer |

What changed from the TUI, and why:

- **"How well do you know orkestration?" is gone.** It chose three things, and each has a new home: the punk
  ork's path is **Empty town, I'll build it myself** on step 4; Skip is allowed everywhere (the run is 3–5
  screens); what the planner reads of a person's experience comes from the tools and MCP servers they have.
- **Industry and the typical day are gone.** They only ordered the intents (★); the town step now shows the
  class's towns as tabs, the first one starred.
- **👍 / 👎 per tool moved to 4b** ("best at" and a note). Only the planner reads it, and only on that path.
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

Seven classes, each on its biome's ground with its mascot (`design-system/sprites/mascots`, `--glyphs` of
`js/terrain.js`): Ork, Undead, Elf, Gnome, Goblin, Knight, Skeleton (Someone else). A class with one role
picks it; a class with two asks which (2b), each with its nick and its stage-1 / stage-2 head.

- `orkcraft --role <role or class>` (`settings.preset_role`) skips both screens.
- **To do:** a class from the landing page (`--role gnome`) maps to one role today (`intents.CLASSES`:
  gnome → marketing). Keep the class as `profile.kin` instead and ask 2b, so a Keyword Gnome is not
  made a Growth-Hack Gnome.
- **To do:** the landing page's class art, larger than the 12 × 11 heads, into `design-system/sprites` and
  onto these cards.

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
(the allow-list of `mcp__<server>__*`), and show them in its window.

## 5. Your first town

The class's towns (`intents.for_role`), one tab each, the first starred. Each is drawn on the class's ground:
the buildings' header sprites in a row joined by roads, a plate with each one's name and what it does, and the
MCP glyphs on the agents. Below: **How it works** (the plan's summary) and three buttons.

- **Use this town** → step 5 with that plan (`town_builder.check`; no model call).
- **Doesn't fit: tell the planner** → 4b. Closed, with a line, when Claude Code is off.
- **Empty town, I'll build it myself** → step 5 with nothing to raise.

### 4b. Tell the town planner

One page instead of the TUI's two: **Work comes from** and **…and goes to** as chips (the class's common ones
first, ✦), each with a field for another; **Your AI tools are best at**, a choice and a note per tool; **What
should this town do, in your words**; **What hurts**, as chips. **Build my town** saves the order
(`town_presets.save_order`) and goes to step 5, where the planner draws the town first (`town_builder.plan` on a
thread). If it fails, the step says so and the order waits in the Town Hall, as before.

**To do:** mark the MCP servers that are on among the chips (Amplitude ✓ MCP) and preselect them.

## 6. Setting up the town

No full-screen progress bar: the onboarding leaves and the town is drawn, and the buildings go up on the map one
step a tick (`RAISE_STEP_S`, the host's clock), so each one appears in front of the person.

- **Bottom left, the log:** every step with ✓ done, ⚒ now (it bobs; still under `prefers-reduced-motion`),
  · next, ✗ failed. While the planner draws: "The town planner is drawing your town…". At the end:
  **Open the town**, which closes the onboarding.
- **Bottom right, the Autonomy card:** "While they build: how free are your orks?" with the three levels
  (`town.settings`, `town.settings.set`, as Settings uses them). Later and Done put it away; the default stands.
- **To do:** draw the planned buildings on the map before they stand: a dashed outline of the header where it
  will be, then a scaffold over the rising sprite (the canvas's screen 5), and the roads as they are laid. Today
  a building appears when it stands.
- **To do:** quiet hours on the Autonomy card (today: Settings).
- **To do:** the town's orkspace takes the class's biome at once (`biomes.settle`): today it follows on the next
  growth tick.

## 7. Where it lives

| Part | File |
|---|---|
| The MCP servers, names only | `orkcraft/realm/mcp.py` (no face; tests/test_mcp.py) |
| The steps, the answers, the raising queue | `orkcraft/gui/onboarding.py` (the host's `onboarding`; tests/test_gui_onboarding.py) |
| The screens and the cards over the map | `orkcraft/gui/static/js/onboarding.js` |
| Their look, from the design system's tokens only | `orkcraft/gui/static/onboarding.css` |

The host turns it on for a first run (`Town.first_run`: no layout for the project yet), unless
`ORKCRAFT_ONBOARDING=0` or the demo. Commands: `onboarding.tools` · `.request` · `.kin` · `.role` · `.mcp` ·
`.town` · `.survey` · `.back` · `.skip` · `.close`.

**To do:** F10 → Onboarding in the GUI menu: steps 1–3 again on a project that has a town (never step 4).
**To do:** move the shared parts of `screens/onboarding/flow.py` here once the TUI is gone.
