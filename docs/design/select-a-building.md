# Design — a click selects; the steward speaks for its building

Status: proposal 2026-10-09, not built. Asked by the owner ("think through"). Builds on [yards.md](yards.md) §7 (the
ork comes out on selection, nothing on hover) and [calm-town.md](calm-town.md) (the Warchief's line at the foot).

## 1. What changes

Today a click on a building **opens** it: the panel slides in on the right with Work and Info. The town has no
"selected but not opened" state, so a person who wants one small thing (run it, rate it, ask its ork) pays for a
whole window.

Proposed, as an RTS does it:

| gesture | today | proposed |
|---|---|---|
| click a building | opens its window | **selects it**: its steward comes out and speaks |
| click the selected building again | — | opens its window (Work) |
| double-click | opens (two clicks) | opens |
| right-click | the building's menu | the building's menu, **Open** first in it |
| Enter, or its number key | opens | selects; a second press opens |
| click the bare town, Escape | closes the window | deselects; the steward walks back in |

## 2. Who speaks: the steward instead of the Warchief

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

1. Second click to open, or right-click to open (and the menu on a long press)? Recommended: second click, right-click
   keeps the menu with Open first.
2. Does the steward take over the Warchief's line, or speak only in its bubble? Recommended: takes over.
3. Do not disturb inside the dial's menu, or as a small button on the dial?
