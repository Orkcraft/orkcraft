# Design — a colour pass: keep the style, make what matters stand out

Status: proposal 2026-10-12, the owner's question ("is it too pale? brighter colours? is it all one style?"); nothing
changed. Priority **P0 for the token pass** (§3, the demo GIF is judged on it), **No** for redrawing the sprites.
Builds on [gui-design-system.md](gui-design-system.md), `design-system/tokens.json`, [sprites.md](sprites.md),
[portrait.md](portrait.md) (the looks). Looked at: `docs/img/town.png` (2026-10-11) and the buildings' `header@2x.png`
side by side.

## 1. What is seen

**The sprites are one style, and a good one.** Two inks and an accent: moss greens for the body, bone and cream for
horns, scrolls and paper, a little gold for fire and light. The silhouettes differ well (the horned hall, the forge's
chimney, the drum, the scroll heap, the tower, the board, the gate, the mill). Nothing to redraw.

**Why it reads pale** is not the palette but three things together:

1. **Figure and ground are the same colour.** Green buildings stand on a green ground (`canvas` `#172a0a` in Camp ·
   forest). With little contrast between them, the eye has nothing to catch.
2. **Idle buildings are dimmed on purpose:** `brightness(.78) saturate(.8)` on every hut not busy, alerting or selected
   (`layout.css`, `.gui-hut__roof`). In a calm town, which is most of the time and the whole of today's screenshot,
   everything is dimmed at once.
3. **The warm accent does two jobs.** Gold is the forge's fire, the drum's sun, the HUD's sun and also "look here"
   (Answers, a yellow dot, the error badge's orange is near it). A signal that shares its colour with decoration does
   not stand out.

**Where the style is not one:**

- **Four type families:** Almendra SC (a gothic display: the wordmark, "Town Hall"), Pixelify Sans (the War Map), Titillium
  Web (the text), JetBrains Mono (code). Two display faces for one role.
- **The War Map's rows** in purple, blue and green bars: colours from nowhere else in the palette.
- **The roads**, "the point" of the README, are thin grey dashes, the faintest thing on the screen.
- Some sprite edges look soft rather than crisp at 2×: to check at 1× (a generator's resample left in).

## 2. The rule

> **A strategy game's rule: a quiet ground, clear units, loud signals.** The ground stays dark and calm; buildings
> stand off it; the warmest, brightest colours are kept for what needs the person (🔥, ❓, an error) and nothing else.

Brighter everywhere is not the answer: it would make the signals of [ork-console.md](ork-console.md) §5 harder to see,
not easier.

## 3. The pass (tokens and CSS only, P0)

1. **Ground away from the buildings' hue:** Camp · forest's `canvas` and `terrain` toward a dark neutral earth (brown or
   grey), so the green buildings stand off it. Ice and void are checked the same way.
2. **Idle dimming softened:** from `.78 / .8` to about `.92 / .95`, so a calm town is calm but not faded; busy and
   selected stay bright.
3. **Warm colours for signals only:** 🔥 and errors a clear red-orange, ❓ a clear yellow, both kept out of decoration
   and chrome; the HUD's sun stays, it is the clock.
4. **Roads seen:** a warm path colour, wider, the selected building's roads brighter as today; carts visible on them.
5. **One display face:** Pixelify Sans (it matches the sprites) for titles and the wordmark, or Almendra SC; not both.
   Titillium for text and JetBrains Mono for code stay.
6. **The War Map's rows** in the palette's own tones.

**How it is decided, not by taste:** the same demo town in three variants of these tokens, each screenshot put through
three checks: in grey (do buildings and roads still stand off the ground?), squinted or blurred (what is seen first?),
and five seconds with a tester ("what needs you here?"). The variant where the answer is the 🔥 and the ❓ wins.

## 4. Not now

- **Redrawing the sprites, or a new palette for them:** No. They are the product's strongest look.
- **A light theme:** Later, if testers ask.
- **Office:** untouched by this pass; it is calm and monochrome by design.

## 5. Open

1. Is the green-on-green of Camp · forest a choice the owner wants to keep (a forest camp), so that only the buildings
   are lifted, or may the ground change?
2. Which display face stays: Pixelify Sans or Almendra SC?
