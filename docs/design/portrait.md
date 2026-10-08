# Design — the portrait: you in the corner, two looks, Do not disturb

The operator's mascot heads the Settings dialog (growth.md §7.3): a 72 × 68 portrait, the name, the
stage, the next stage and the deeds. Settings is opened rarely, so the mascot is rarely seen, and what
a person changes most about how the town treats *them* (its look, its noise) has no place at all.

The mascot moves to a **portrait** in the HUD's left corner, as a hero's in Warcraft III: small, always
there, a click opens it. Its menu holds the person, not the town: who you are, how the town looks to
you, and whether it may disturb you.

| stage | what | state |
|---|---|---|
| 1 | the portrait and its menu; You leaves Settings (§1, §2) | done (`js/portrait.js`) |
| 2 | Do not disturb (§4) | done (`disturb.py`, `gui/you.py`, the Horn, `gui/notify.py`) |
| 3 | two looks, Camp and Office; the old Office leaves the docs (§3, §6) | done (`town.css`, `office.css`) |
| 4 | the phone: the portrait in its top bar, the menu as a sheet (§5) | the host's part done (`portrait` in the compact snapshot, `you.dnd` and `you.look` allowed); the sheet is the app's |
| later | Change role from the menu; a new stage's glow; the Warchief addressing you by your stage | |

## As built

- **The portrait** is 28 × 26 in the HUD (the HUD is 28 px high), its marks inside its corners. Its menu
  is a popover under it (a sheet at the window's foot below 640 px).
- **Office** is `data-theme="office"` + `data-look="office"`: the design system's office theme (flat
  panels, hairlines, the system font) with `gui/static/office.css`'s greys over it. The warm `office`
  palette of `design-system/tokens.json` is left for the design system's previews.
- **The CSS both looks share** (the huts' sprites small at the left, the roads as a block diagram) moved
  from `office.css` to `town.css`, scoped `[data-look]`; `index.html` opens on `data-look="camp"`.
- **The Horn** asks `town.hushed()` (the GUI host sets it from `gui/you.py`) and logs a call it kept as
  `dnd` ("do not disturb" in its window). The TUI never sets it.
- **The summary** shows in the Warchief's line until ✕; its click opens Answers when a question waits,
  else the Horn that kept a sound. It goes to the phones as one news line (`kind: "dnd"`).
- **Not built:** Change role (the onboarding has no way back to Who are you? yet), the new stage's glow,
  and the Warchief's address by stage (it addresses no one by stage yet, in either look);
  `orkcraft gui --look` stays gone: the look is set in the window.

## 1. The portrait

```
┌[▣]┬ orkcraft ▾ · Stop all · Answers (2) ············ Spend · Context · Agents ┐
│ II🌙                                                                          │
│                                                                               │
```

- **Where:** the HUD's first item, before the town's name (`js/chrome.js`). The map stays clear.
- **Size:** 32 × 32. The head (12 × 11 grid) at 2×, on its kin's biome ground, in a bevelled frame.
- **Marks:** the stage I–IV at the bottom right; 🌙 at the top right while Do not disturb holds; an
  `alert` dot at the bottom left while an ork asks (a click on the dot opens Answers, a click elsewhere
  the menu). Not Renown: Renown is a building's.
- **A new stage** glows softly until the menu is opened (it glowed in Settings before). The Warchief's
  line still says it once, and its link opens the menu.
- **Office** (§3) draws a monogram instead of the head: the role's two letters in a circle (SE, QA,
  EM, PM, PD, GD, AS, MK, DA, FO, and `··` for someone else), no stage mark. 🌙 and the dot stay.

## 2. Its menu

A click (or Enter) opens a popover under the portrait; Esc or a click outside closes it.

```
┌──────────────────────────────────────────┐
│ [head 4×]  The Jira Lich · stage 2       │
│            Next: a building at II        │
│ 🏰 🛤 👍 ░ ░ ░ ░ ░   deeds, grey ahead    │
├──────────────────────────────────────────┤
│ Look            [ Camp | Office ]        │
│ Do not disturb  [ Off | 1 h | Until 9:00 | On ] │
├──────────────────────────────────────────┤
│ Town settings…  ·  Change role           │
└──────────────────────────────────────────┘
```

- **You** (`settings.js` `You`) moves here whole: the head at 4×, the name, the stage, Next, the deeds
  with their hints. Settings loses it and with it the "Camp: orkcraft" divider: Settings is the town's
  rules only.
- **Change role** (later) is the onboarding's Who are you? (gui-onboarding.md §3).
- **Town settings…** opens Settings, as the town's name in the HUD does.
- In Office the head is the monogram at 2× and the deeds row is plain marks, no emoji.

## 3. Two looks: Camp and Office

One vocabulary (CLAUDE.md, Wording) and one layout. A **look** changes only how the town is drawn,
as `data-look` always did; the words, the panel, the line and every action are the same in both.

| | Camp (the default) | Office |
|---|---|---|
| buildings | the huts' building sprites | a card: the name and its status lines, no sprite |
| the Warchief's line | 🧌 | `›` |
| the portrait | the mascot's head, the stage | the role's monogram |
| colour | the Camp palette (gold, moss, bronze) | monochrome greys with one accent, the Camp gold muted (`#b8a06a` dark, `#7a6630` light): the selected, the focus ring; light or dark as the system says |
| type | Almendra titles, Titillium | the system UI stack |
| emoji in labels | yes | no (`modes.plain`) |
| a building that waits for you | flames climb its roof (when the town's `fire` is on) | its frame turns `danger`, no flames |
| the Warchief | jokes, addresses you by your stage ("My Lord Lich") | plain ("Forge asks for a decision") |
| growth news, a new stage's glow | yes | no; the stage and the deeds keep counting and show again in Camp |

- **What stays coloured in Office:** `danger`, `warning`, `success`, each with its mark (✗ ⚠ ✓). They
  say what costs money or risks work; monochrome never hides them.
- **The onboarding** keeps its voice and its sprites in both looks: it is where the mascot is chosen.
- **Stored** per machine, the person's and not the town's: `~/.config/orkcraft/settings.json` →
  `look` (`camp` | `office`), default `camp`.
- **Tokens:** Office is the design system's office theme (`data-theme="office"`) with its colour tokens
  redrawn in greys (`office.css`, light and dark under `prefers-color-scheme`), never hand-made colours
  in a component: a building's window, being a UI document of roles (design-system.md), follows it with
  no change.

## 4. Do not disturb

For the person, not the orks: nothing stops working, nothing is lost, it all waits.

| | while it holds |
|---|---|
| 📯 the Horn | sounds nothing; each call is logged as kept, why "do not disturb" |
| the Warchief | does not speak first (calm-town.md §8); it answers when asked |
| toasts | only `error` |
| pushes to phones | all held but one: the budget is spent and the orks stopped |
| Answers | the questions gather; its count in the HUD stays |
| the map | as it is: a building that waits still shows it |

- **How long:** 1 hour · until morning (the end of the machine's quiet hours, else 9:00) · until
  turned off. The menu shows the end ("Until 9:00").
- **When it ends:** one line in the Warchief's line, and one push, of everything that gathered:
  the questions, the sounds kept, the toasts held, the pushes held, and the spend if it crossed into
  `warn` or `over` ("While you were away: 3 questions, 2 sounds kept, 1 error, spend at 92%"). A
  click opens Answers when a question waits, else the Horn's log of calls.
- **Stored** per machine: `settings.json` → `dnd_until` (an ISO time, `"on"`, or none). The host puts
  it in the snapshot (`dnd`) for the page, the Horn and the notifier (`gui/notify.py`).
- **Apart from the Horn's own mute and quiet hours:** those are the building's settings and stay
  in its window. Do not disturb is over them, for one person, for a while.

## 5. On the phone (mobile.md)

- The portrait at 28 px at the left of the app's top bar; a tap opens the menu as a bottom sheet.
- The look follows the machine's `look` in the snapshot (mobile.md §4: it sends `camp` or `office`).
- Do not disturb set on the phone is the machine's: it is the person who is not to be disturbed,
  wherever they set it. The phone's own Focus works as it always did.

## 6. What changes elsewhere

- **CLAUDE.md:** "Camp and Office are merged; there are no modes" becomes "One vocabulary. Two looks:
  Camp (the default) and Office (calm, monochrome); a look changes only how things are drawn."
- **The old Office leaves the docs:** gui-design-system.md (its two looks and "the GUI has one look,
  Office"), calm-town.md, mobile.md §4 and the rest that call the old vocabulary or today's look
  "Office". `realm/lexicon.py` keeps one sentence of history.
- **"Camp" names only a look in the interface.** The town's rules are the town's ("Town settings"),
  never the "camp's".
- **Code, renamed once:** today's look is `data-look="office"` (`gui/static/office.css`,
  `look: "office"` in `gui/state.py` and `gui/mobile.py`). It becomes `camp` (`camp.css`), and
  `office` is the new look. An exception to "code keeps its names", taken because the old value is
  written in code only, never in a person's settings or a Project file, and the two would collide.
- **`realm/lexicon.py` `TERMS`:** `look` "Look", `look.camp` "Camp", `look.office` "Office", `dnd`
  "Do not disturb", `portrait` "portrait".
- **growth.md §7.3** points here: the portrait's menu, not Settings, is where the mascot lives.

## 7. Not doing

- No third look, no per-building look.
- Office changes no word: a building is a building, the Warchief is the Warchief.
- Do not disturb never stops, pauses or slows an ork.

## 8. Open questions

None for now.
