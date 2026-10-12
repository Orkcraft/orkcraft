# Design — a click selects; the steward speaks for its building

Status: proposal 2026-10-09; §1 (a click selects), §2 (the command card), §7–8 built. Asked by the owner ("think through"). Builds on [yards.md](yards.md) §7 (the
ork comes out on selection, nothing on hover) and [calm-town.md](calm-town.md) (the Warchief's line at the foot).

## 1. What changes

Today a click on a building **opens** it: the panel slides in on the right with Work and Info. The town has no
"selected but not opened" state, so a person who wants one small thing (run it, rate it, ask its ork) pays for a
whole window.

Proposed, as an RTS does it — **built 2026-10-09** (`js/windows.js` `selected`, `pickBuilding`): a click selects,
the selected one clicked again (so a double click) or **Open** on its card in the Warchief's line opens its Work;
Escape closes the window, and with no window up lets the building go; 1–9 select, the same number again opens:

| gesture | today | proposed |
|---|---|---|
| click a building | opens its window | **selects it**: its steward comes out and speaks |
| click the selected building again | — | opens its window (Work) |
| double-click | opens (two clicks) | opens |
| right-click | the building's menu | the building's menu, **Open** first in it |
| Enter, or its number key | opens | selects; a second press opens |
| click the bare town, Escape | closes the window | deselects; the steward walks back in |

## 2. Who speaks: the steward instead of the Warchief

**Built, first step (2026-10-09): the line is the building's command card** (`js/warchief.js`), as an RTS's bottom
panel is the selected unit's. While a building is selected (open in the panel):

- the face is its steward's, **under its building's hat** (its Info on a press), and its name stands beside it (in
  the tooltip when the line is narrow); ✕ beside it gives the Warchief's line back, at large, while the building
  stays selected;
- the buttons are its quick actions (`b.quick`, three, ⋯ for the rest in its Info), **Q, W, E** do them from
  anywhere but a field (by the key's place, so any keyboard layout); Answers shrinks to ❓ N; Build and Improve
  wait for the Warchief (the open panel leaves the line little room);
- **the field is its steward's**: "Tell Task manager or ask it…". What is typed goes to its keeper (core/keeper.py,
  `keeper.ask`): it answers, or proposes a change of its rules and settings, line by line, with Apply (Revert takes
  it back). To the Warchief, with the building named as `@` does, from a yard (no steward), a building that keeps no
  settings (the snapshot's `keeper`), words that name another building too, and the demo (its keeper calls no
  model): "Ask the Warchief about Calendar…". `/` commands stay the Warchief's.

**The hats** (`tools/hat_sprites.py`, `js/icons.js` `HATS`): one ork head, two rows of a role's hat over it as the
Warchief's crown — a beret and quill for the Wiki, the Mill, the Gramophone and the Lake; a horned helm for External
listeners, the Horn and the Crag; a leather cap with goggles for the Forge, the Workshop and the Catapult; a visored
cap for the Task board, the Calendar, the Vault and the yards; a plumed helm for the Agent pool and the Review board; a
lamp on a hard hat for the Mine. The steward that comes out of its building wears it too (js/visit.js).

**It answers from what happened** (built 2026-10-09): the keeper's prompt carries the building's lately
(`core/keeper.py` `lately`, no model): its week by the ledger (runs, done, failed, results, 👍 / 👎), the status lines
it shows now, its chronicle's newest eight events and the operator's newest three 👎 with their notes and the output
they were on. So "why did the invoice go to bugs?" is answered from the 👎 and the rules, and a question changes
nothing (value null); its answer opens as the keeper's dialog, Close. A wake (core/wakes.py) reads none of it: what woke it is its request.

While a building is selected, the Warchief's line at the foot **becomes the building's steward**: its face, its
name ("Steward of the Calendar"), and the line asks *it*. Deselected, the Warchief comes back. One line, two
speakers: never two chat boxes at once.

The steward's bubble over the building holds, in this order:

1. **Two or three quick actions**, the type's own (`b.quick`, today's tray): Run, Add a task, Check now. At most
   three; the rest stay in Info.
2. **👍 / 👎**, and the AI tool for a building whose ork thinks (today's bubble).
3. A question its ork waits on, if any: the `!` first, before everything else.

The bubble goes when the building is deselected or another one is clicked (yards.md §7 already does this).

## 3. Why

- One small thing costs one click, not a window that then has to be closed.
- The steward is who answers for a building (script-first.md: it writes the rules): talking to it where it stands
  says so without a word.
- The panel stays for real work, so it can be wider and stay open without hiding half the town by accident.

## 4. Risks and what to settle first

- **A habit breaks**: today one click opens. The second click opens, so it costs one click more, and the bubble says
  "Click again to open" the first few times (counted per person, then never again).
- **Touch**: no right-click, no hover. Tap selects, a second tap opens; a long press is the menu.
- **The Warchief's line taken over** must be obvious: the face and the name change, and an ✕ beside the name gives
  the Warchief back without deselecting.
- **Tests**: every browser test that clicks a building to open it clicks twice or presses Enter twice.

## 5. Do not disturb beside the sun and moon (from the HUD's dial)

The dial in the middle of the HUD (js/chrome.js `Hour`) says the hour: sun or moon. Do not disturb is the person's
own "quiet now". Proposed: **move the horn into the dial's menu** and draw the dial with a struck horn on it while
Do not disturb holds. The hour and the person's quiet are one question ("will the town bother me now?") and one
place answers it. The corner keeps the portrait alone.

Open: whether the horn should stay one click away (it is used at the start of a meeting, quickly). If yes, a second,
smaller button on the dial's right edge, not in the menu.

## 6. Questions for the owner

1. ~~Second click to open, or right-click to open?~~ A second click (or Open on the card); right-click keeps the menu
   (built).
2. ~~Does the steward take over the Warchief's line, or speak only in its bubble?~~ Takes over (§2, built).
3. Do not disturb inside the dial's menu, or as a small button on the dial?

## 7. A building just raised is set up in the Warchief's line (built 2026-10-09)

Asked by the owner: a new building's first settings belong in the Warchief's dialog, not on its Work page, and as
few as can be. Built for the Watchtower first; a type joins by exporting `Setup` (and `setupAsk`) from its module.

- Build raises the building (one press in the catalog, as before) and **does not open its window** when its type has
  a `Setup` (`js/build.js` `raised`): the Warchief asks over his line instead, "External listeners stands. What should
  it listen to?" (now "… is going up. What should it listen to?", §8), with the answers as buttons. *All its settings* opens the window; *Later*, Escape or a press
  elsewhere puts the question away.
- **The Watchtower's answers** are the services Claude Code has a connector for (Gmail, Slack, Jira, Confluence). One
  press adds it through Claude's connection as it comes: every 30 min, at most $0.50 a day, its usual ask, every
  message sorted (`act add_quick`, `watchtower_add.Adding.quick`); saved when its first look answers. With no
  connector, the line says how to connect one, or to pick a source in its settings.
- A type with no `Setup` opens in its window as before.

## 8. Build as a strategy game does it (built 2026-10-09)

Asked by the owner: Build → pick a building → place its ghost → it goes up under scaffolding while the Warchief asks
its setup → the scaffolding comes down and it stands.

1. **Pick** in Build (the catalog, as before). The dialog closes; nothing is built yet.
2. **Place**: the building's ghost follows the mouse (`js/town.js` `Placing`): **the building itself, faded, 1:1** —
   its house, its fence or plate, its size — so it stands where and as big as the ghost was (since 2026-10-09; before,
   the onboarding's small ghost). A card that fills with what its building finds (a Task board's tasks) can grow once
   it stands: the ghost cannot know that yet; its corner stays where the ghost's was. A press builds it there (`town.build` with the spot); Escape
   or a right click lets it go. A spot already given (the map's menu, *Build here*) skips this step.
3. **Scaffolding**: the building is raised at once, but drawn as scaffolding with its sprite rising
   (`js/build.js` `raised`, `constructing`), sized as a house so it stands where it was placed.
4. **The Warchief asks** its setup meanwhile, if its type has one (§7). The scaffolding stays up until that is
   over: answered, *Later*, Escape or a press elsewhere (`endSetup`). A type with no questions stands after a moment
   (1.6 s).
5. **It stands**: the scaffolding comes down and the building rises into place once (`built`, the onboarding's
   rise).

Not built: a first prompt for a type with no setup of its own (no one setting holds "what this building is for"
today: `prompt` only names it, `ork.orders` and `building.recruit_ask` speak to or hire an ork). To be decided per type.
