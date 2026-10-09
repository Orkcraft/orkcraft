# Design — the Warchief's line does more, cards come in three sizes, tiers say what they are

Status: discussed with the owner 2026-10-09; what is built is marked **Built**. Builds on
[select-a-building.md](select-a-building.md) (a click selects, Build in place), [yards.md](yards.md) §7 (fences and
bare buildings) and [building-views.md](building-views.md) §1a (a card shows more the bigger it is).

## 0. Three kinds of building

| kind | example | on the town |
|---|---|---|
| **no agent** (a yard) | Calendar, File tree, Router | no room for an ork on the left; nobody comes out under the mouse |
| **a view** | Task board, Agent pool, Review board, Wiki, Calendar | a **medium card** in its fence from the start (§4) |
| **no view** (bare) | Signpost, Mill, External listeners, Drop file here | its house, its name and a plate with what it says first |

The person may shrink a medium card to minimal (§4) or fold it; a town of ten medium cards would fill the screen.

## 1. The Warchief's line: buttons before the words

An empty field is the blank page: a new person does not know what to type. The line starts with two or three
buttons, then the field.

- **Build** (always) — opens the build tray (§2); the catalog dialog until the tray is built. **Built.**
- **Answers (N)** — only while orks wait on the person (the glossary's word for the orks' questions, realm/lexicon.py);
  it opens them. It takes the place of Answers in the HUD. **Built.**
- **Improve** (**built**, `warchief.improve`) — the Warchief goes through the latest 👎 of every building, says what went wrong in each and offers a
  change (a rule, a step, a tier, an ork), each a card with Apply or Not now. With no 👎 it says so and offers
  nothing.
  - *Later, written down only:* with no 👎 the Warchief asks every building for its use (runs, failures, spend,
    what was opened, what was ignored) and looks for the problem himself.
- **While a building is selected** the buttons are its own two or three quick actions and its steward speaks in the
  line (select-a-building.md §2): one place, one way. **Built** (its first step: the field still asks the Warchief).

## 2. Build from the line, not a dialog (built)

The catalog of 21 buildings with a paragraph each is too much. Build **grows the Warchief's line** by one row of small
icons over its bar, in the line's own frame (`js/build.js` `BuildRow`), not a window of its own: the line's field is
already where words go, so it finds in the row, and Enter that finds no icon asks the Warchief, whose line it is. The
row is one line of 34-pixel icons with a thin rule between the groups, about 70 px tall in all (the first tray, a
window of labelled tiles, stood six times as tall: the owner's call, 2026-10-09); a narrow line scrolls it sideways.

- each icon says **what you want done**, not which house does it: mail, Slack, Jira, Confluence, tasks, a calendar,
  agents, a review, a wiki, research, listening, code, a check, sending, a route, a transform, a chart, a sound, files
  dropped (`design-system/sprites/intents/`, drawn by `tools/intent_sprites.py`; which building each raises is
  `INTENTS`). The line over the row says the icon under the mouse: its word, its building, its summary. A source's icon raises External listeners
  already listening to it when Claude has a connector for it (its setup in the Warchief's line, `want`), else that
  setup says so;
- **For you** first, framed in gold: three of the onboarding's role's own buildings not standing yet (`builder.for_role`:
  counted over its ready towns), External listeners on a source the role reads; then the rest in the catalog's groups;
- typing in the line filters it by the icon's own word first ("mail" leaves Mail), else by its building's name and
  summary; Enter takes the first left, or with none asks the Warchief what to build; Escape, Build again or a press
  elsewhere puts the row away;
- a press picks it and its ghost follows the mouse (select-a-building.md §8); **a double press builds it at a free
  spot**, no ghost, for a person who does not mind where; from the map's *Build here* a press builds it there.
- *Later:* `^` in the line names a building to build, as `@` names one that stands.

## 3. Place first, then set up

Place first, as now: you place it, the worker builds it, you answer meanwhile — and the ghost shows where it stands
among its roads. *Later* leaves it standing with a **needs setup** plate, so a building half set up is never lost.
Setup first would only win if many leave half way: the usage stats will tell (docs/usage-stats.md).

## 4. A card in three sizes, and its window

The levels of building-views.md §1a, chosen by the person: the card's corner **snaps** to three sizes (no growing by
itself: it was turned off, yards.md §7).

| size | what it shows | Task board | Agent pool | Calendar |
|---|---|---|---|---|
| **minimal** | the least: what a bare building's plate says and one line | tasks, and the last changed | agents, and idle / working / a problem | events and scheduled runs today, and the next |
| **medium** (the default) | the whole interface, small | the task cards, the notes scrolling | the agents at work and what each works on | the whole list |
| **large** | the medium, roomier: a scrolling list becomes a list, details come in | | | |
| **window** | the large card on half the screen | | | |

Five types have a view: 5 × 3 cards. First the Task board, the Calendar and the Agent pool; the others keep the
medium.

## 5. Info stays a window of its own, its settings in it (built)

Info is not folded into the window: it opens on its own, from the ⚙ in the ork's bubble (yards.md §4) as from the
panel. It holds two parts, one under the other (§7):

- **the building** — what it is and what for: its name, 👍 / 👎, its runs, then its **goal** and its **Freedom**;
- **the steward** — who works it and how: its **tier** (§6, three chevron steps), its **AI tool** (its model
  dialog), Watch, Report, Redesign, the roads it listens to and its road rules.

The ⚙ in the bubble opens Info scrolled to the steward's part (`js/visit.js` `openSteward`); the bubble no longer
picks the AI tool in place.

## 6. Tiers say what they are (built)

*Elder / Warrior / Laborer* said nothing about how heavy a model is. In every word a person reads:

| tier (code) | word | mark | models |
|---|---|---|---|
| `laborer` | **Novice** | ★ one chevron | the light ones: haiku, gemini flash low, gpt luna |
| `warrior` | **Seasoned** | ★★ two chevrons | the middle: sonnet, gemini flash high, gpt sol |
| `elder` | **Veteran** | ★★★ three chevrons | the heavy ones: opus, gemini pro, gpt astra |

- Code, settings and town scrolls keep `elder`, `warrior`, `laborer` (CLAUDE.md, Wording); `realm/lexicon.py` keeps the
  old words in `was`, so an old line says today's word.
- The mark is a pixel chevron (`icons/rank-1..3.png`): in Info beside the tier, and **on the ork itself when it comes
  out**, so the person sees how heavy a mind is working without opening anything.

## 7. The steward's tier is its own, not the goal's (built)

Asked by the owner: the steward *is* the working agent; the goal is a piece of its prompt — what the retros
optimise the building towards. Until now the goal also chose the models of the steward's work, so 💎 Quality made
the steward heavier and 🪙 Thrift lighter, and the two could not be set apart.

- The steward has **its own tier**, Novice, Seasoned or Veteran (`OrcSpec.tier` on the lead steward,
  `steward_models.level_of`), set in Info (`building.steward_level`).
- Its tier picks a **column** of the work table (steward-at-work.md §2): every task keeps its own weight (a sort
  light, a plan heavier), the tier says how heavy the whole steward is. A tier picked for one task stays first.
- **A tight quota** still runs it on the light column for a while (`Worker.aim_now`).
- **No change in cost on the day**: a steward with no tier of its own has the one its goal gave it (Thrift →
  Novice, Balance → Seasoned, Quality → Veteran); the first time the goal changes, that tier is written down as
  its own, so a new goal never moves it.
- **The goal keeps its meaning**: the retros and Optimize aim at it, the steward's prompt says it, and an Agent
  pool's orks follow it (realm/plans.py `GOALS`: the light tier, review, parallelism) — that is the building's
  strategy, not its steward's mind.

## Order

1. The line's buttons: Build, Questions (N), Improve (§1) — and a selected building's own (with select-a-building.md).
2. Tiers' names and marks (§6), the ork wearing its mark; Info's two parts with the steward's tier and AI tool
   (§5, §7). **Built.**
3. Build as a tray from the line, a double press builds at a free spot (§2). **Built.**
4. The medium card by default and three snapping sizes for the Task board, the Calendar, the Agent pool (§4).
5. `^` in the line (§2).
