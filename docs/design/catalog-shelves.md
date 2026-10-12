# Design — the catalog on shelves: the core first, the rest one click away

Status: proposal 2026-10-12, talked through with the owner; nothing built. Priority **P0** for the decision and the
README, since it shapes the testers' first fifteen minutes and the first screen people see; the catalog flag it
needs is small. Builds on [onboarding.md](onboarding.md) (role, industry, intents, the first town),
[ork-console.md](ork-console.md) (the main scenario) and [script-first.md](script-first.md) (the cheapest thing that
works).

## 1. Why

The catalog has twenty building types. Many are there because the owner needs them, not because the main scenario
does. A new person sees twenty names before seeing one ork work, and the README's table of twenty makes the product
look bigger and vaguer than it is.

> **By default the town offers only what the main scenario needs:** several coding agents in parallel, who works
> and who waits, stepping in to one. The rest is on a shelf, one click away. Nothing is deleted; older towns load as
> they are.

## 2. The shelves

| shelf | types | why |
|---|---|---|
| **Core** (offered by default) | Task board, Agent pool, Review gate, Inspector, External listeners | the main path: a task → agents in parallel → a diff → the person approves. External listeners as the way in from GitHub |
| **Plumbing** (not picked by hand, placed when needed) | Router, Transformer, Script | the cheapest thing that works ([script-first.md](script-first.md)). The Warchief or the building designer places one when a road needs logic; they stay findable in the catalog |
| **More buildings** (a shelf, off by default) | Wiki, Research, Review board, File tree, Drop file here, Audio briefing, Publisher, Branches & PRs (§3b), Metrics (§3a), the Calendar's meetings ([town-time.md](town-time.md)) | useful, not for a first look |
| **Improve tools** (not in the catalog; through Improve) | Test bench, UX bench | they improve buildings, not the person's work: for experienced users and contributors |
| **Not a building** | Sound alerts | §3 |

**Not "made by the community".** The More shelf is called what it is. A "community" mark goes only on what other
people really brought; on the owner's own buildings it would be untrue, and the first contributor who noticed would
stop trusting the rest.

## 3. Sound alerts is not a building; Metrics and Branches & PRs are redefined

A building is a way of working with information ([ork-console.md](ork-console.md) §2).

**Sound alerts is a notification setting:** play a sound when a building burns or an ork asks. A town setting, not a
building on the map. Its id stays and it loads in older towns (CLAUDE.md, Wording); a new town does not offer it.

### 3a. Metrics: a chart of an outside source (Later, on the More shelf)

Decided with the owner 2026-10-12. **Metrics is not there to count tokens per answer.** Today (`realm/catalog.py`
`crag`) it charts the town's own sources: limits, spend, tokens, runs, orks, tasks, CPU, a road's numbers. That moves:

- **The town's own numbers go to a window from the HUD (P1):** a click on 🪙 or on a limit opens the town's spend and
  limits, the summed slices of [ork-console.md](ork-console.md) §15 (session, ork, building, cart, town).
- **Metrics becomes a chart of an outside source:** Sentry, Amplitude and the like. A pie, bars or a line, chosen
  for the data; a threshold still raises `charts.threshold`. Setting a chart up is the Mason's (the source and its
  fields) and the Alchemist's (the chart's shape); fetching and drawing is code, so Metrics is a yard with no ork of
  its own.
- **It refreshes itself** on a cadence set on the building (hourly by default): one chart should not need a second
  building and a road. That cadence shows on the Calendar like every schedule ([town-time.md](town-time.md) §2). A road
  may still ask it for a fresh chart.

Open: **how it reaches the source.** Orkcraft keeps no API keys and talks to models only through the person's AI
tools. Through those tools' MCP servers (as the Publisher does) each refresh is a model call, which an hourly chart
should not cost; through the source's own API it needs a token, kept as the name of an environment variable (as the
audit already asks). To decide before it is built.

The catalog's own description of `crag` and `docs/reference.md` change with the build, not before: the reference
says what is built.

### 3b. Branches & PRs: manual git (More shelf, no further investment)

Decided 2026-10-12: Branches & PRs is the owner's way of working with git by hand, partly in place of a git tree or
an IDE's git tools. In the main scenario branches and pull requests are the Agent pool's and the person reads the
diff in the Inspector, so it is not core. A manual git interface competes with IDEs and git clients that do it
better; it stays on the More shelf as it is. What is the agents' own (their branches and worktrees) belongs in the
Agent pool, later.

## 4. Packs by kind of user: Later, and no new system

Shelves by kind of user (game dev, personal productivity…) are a good idea for later, not now: with no outside users
yet, any pack would be built on guesses. The onboarding already asks the role and the industry and builds the first
town from the role's intents ([onboarding.md](onboarding.md)); when there are users, packs grow out of those intents
(a role → a shelf), with no new mechanism. A game dev pack comes last of all: part of the game dev community is
hostile to AI, so it waits until testers ask for it.

## 5. What it changes outside the code

- **The README:** its table of twenty buildings becomes the core's five or six and one line: "and fourteen more on
  the shelf, one click each".
- **The demo** shows the core only.

## 6. Decided

1. Branches & PRs: manual git, More shelf (§3b).
2. The Calendar is two things: the town's time (P1, [town-time.md](town-time.md)) and the person's meetings (More
   shelf).
3. Metrics: a chart of an outside source, Later; the town's own numbers to a HUD window, P1 (§3a).
