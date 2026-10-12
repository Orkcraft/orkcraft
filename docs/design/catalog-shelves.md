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
| **Core** (offered by default) | Task board, Agent pool, Review gate, Inspector, External listeners, Branches & PRs (open question 1) | the main path: a task → agents in parallel → a diff → the person approves. External listeners as the way in from GitHub |
| **Plumbing** (not picked by hand, placed when needed) | Router, Transformer, Script | the cheapest thing that works ([script-first.md](script-first.md)). The Warchief or the building designer places one when a road needs logic; they stay findable in the catalog |
| **More buildings** (a shelf, off by default) | Wiki, Research, Review board, File tree, Drop file here, Calendar, Audio briefing, Publisher | useful, not for a first look |
| **Improve tools** (not in the catalog; through Improve) | Test bench, UX bench | they improve buildings, not the person's work: for experienced users and contributors |
| **Not buildings** | Sound alerts, Metrics | §3 |

**Not "made by the community".** The More shelf is called what it is. A "community" mark goes only on what other
people really brought; on the owner's own buildings it would be untrue, and the first contributor who noticed would
stop trusting the rest.

## 3. Two types that should not be buildings

A building is a way of working with information ([ork-console.md](ork-console.md) §2).

- **Sound alerts** is a notification setting: play a sound when a building burns or an ork asks. A town setting, not
  a building on the map.
- **Metrics** repeats the HUD's 🪙 and the spend slices (session, ork, building, cart, town;
  [ork-console.md](ork-console.md) §15). Its place is the Town Hall's Info.

Both keep their ids and load in older towns (CLAUDE.md, Wording); what changes is that a new town does not offer them.

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

## 6. Open

1. **Branches & PRs:** does it repeat the Agent pool, which already works a branch per task and opens a pull request?
   If it does, it is folded into the Agent pool, not shelved; if it does something the pool does not (testing a
   branch in a throw-away worktree, merging), it stays in the core.
2. **Calendar:** in the owner's daily use, or only for preparing meetings? If daily, it may belong in the core of a
   "personal productivity" shelf later.
