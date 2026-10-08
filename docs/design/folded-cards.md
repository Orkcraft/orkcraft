# Design — folded cards: a hut that shows its name only

A person who runs orks mostly watches (calm-town.md). Most huts say the same thing all day: a Signpost's
counters, a Mill's last run, a Pit's "Drop here". Their cards take the room the busy ones need, and the
eye reads them again and again for nothing. A hut may **fold**: its card keeps its title bar — number,
icon, name, the keeper's head, `?`, the pin — and drops the rest. It opens again by itself, on top of
its neighbours, while something on it wants the person.

| stage | what | state |
|---|---|---|
| 1 | Fold / Unfold on a hut, kept in the Town Scroll; folded types in the catalog; a peek on trouble and on a drag; a mark in the title | |
| 2 | marks of more types (Watchtower, Barracks, Forge); Fold the quiet ones / Unfold all on the bare map; `/fold @name` | |

## 1. What a folded hut shows

```
 ┌──────────────────────────────────────┐        ┌──────────────────────────────────────┐
 │ 3 ⚙ The Mill               📌  ▸    │        │ 3 ⚙ The Mill        error  📌  ▸    │
 └──────────────────────────────────────┘        └──────────────────────────────────────┘
   quiet                                            its worker says ERROR: a peek opens under it
```

- **The title bar stays as it is** (js/hut.js): the number, the spinner while it works, the type's icon,
  the name, the keeper's head (it flashes when it asks), `?`, the pin, the road handle. The roof sprite
  and the flames stay too: fire is how a question is seen (gui-design-system.md: questions are fire).
- **The fold toggle** stands right of the pin: `▾` on an open card folds it, `▸` on a folded one opens it.
  Its title says what a press does (*Fold the card* / *Unfold the card*). A press never opens or drags
  the hut.
- **A mark** may stand before the pin: a word or a number in a tone, what the hidden card would have
  said first. Every hut gets one for free — `error` (danger) while its worker's state is `ERROR`,
  `paused` (warning) while it is paused. A type adds its own with `mark(b)` in its page module
  (js/types.js): `{text, tone}` or null. Stage 1: the Pit — how many were dropped.
- **The quick actions** stay: the tray on the card's bottom edge comes out under the title bar while the
  mouse is on the hut, as on an open card.
- **The parts' checkboxes** (js/parts.js: Task Fields, War Drum) are not shown while the card is folded:
  there is nothing to hide. Unfolded, the parts the person hid stay hidden.

## 2. The peek: open on top, never push

A folded card opens by itself — **a peek** — while one of these holds:

| why | until |
|---|---|
| an ork of it asks (`alert`) | the question is answered |
| its worker's state is `ERROR` | the state clears |
| it is paused | it resumes |
| a file, a link or a text is held over it (a drag) | the drag leaves it or lets go |

- **A peek lies over the huts under it**, it never moves them. The town places huts by their folded
  height (js/town.js), the peek draws the card's inside below the title bar, above its neighbours,
  with a shadow. A hut never jumps while the person aims at another one.
- **A peek is not the person's choice**: it changes nothing in the Town Scroll, and the hut folds again
  when its reason is gone.
- **`▸` on a peeking hut puts it away** for that reason: the card folds while the same question, the
  same error, the same pause stand; a new one peeks again. Unfold in the right click opens it for good.
- **A drag peeks any folded hut**, so a drop target is never a title bar alone: the Pit takes a file
  held over its folded card exactly as over its open one (buildings/pit.js `useDropZone`).
- Under `prefers-reduced-motion` a peek appears without its slide.

## 3. Who keeps it

- **The Town Scroll**, as the pin: `folded` on the building (`scroll.py` `BuildingSpec`, `false` by
  default and then left out of the file). How a town is laid out goes with the town to another machine,
  unlike a part of a card hidden (that stays in this browser, js/parts.js).
- **The catalog** says which types are built folded: `BuildingType.folded` (realm/catalog.py). Built
  folded: **The Pit**, **Signpost**, **The Mill**, **Scroll Dump** — they say little and act on their
  own; trouble peeks them. Every other type is built open. The type's word counts once, when the building
  is raised (core/buildings.py `raise_spec`); after that it is the person's. A building that stood before
  stays open: an update never folds what the person was looking at.
- **The snapshot** (gui/state.py) says `folded`.
- **The host**: `building.fold` toggles it (gui/console.py), as `building.pin` does: saves the scroll,
  records `folded` / `unfolded` in the chronicle. No toast: the hut shows what happened.
- **The Town Hall** never folds: it is the way to the Warchief.

## 4. Where it is reached

- **The toggle** on the hut (§1).
- **The right click** on a hut (js/hut.js `hutMenu`): *Fold the card* / *Unfold the card*, after Pin.
- **Stage 2**: on the bare map *Fold the quiet ones* (every hut without a peek reason and not
  selected) and *Unfold all*; the Warchief's `/fold @name`. The menu entries then name the command.

## 5. Layout

- A folded hut is measured as it draws (js/hut.js `measure`), so the roads meet its title bar and
  Tidy up (js/tidy.js) lays it out by its folded size.
- Folding lifts the huts under it as hiding a part does (js/parts.js `lost`): a fold counts as every
  part hidden. Unfolding gives the room back. A hut built folded has no taller height to give back.
- The peek's inside is placed out of the flow (absolute, under the title bar), so the hut's measured
  size stays the folded one while it peeks.

## 6. Words

Plain words, since they say what a control does (CLAUDE.md, One vocabulary): **Fold the card**,
**Unfold the card**, **folded**. The glossary (realm/lexicon.py `TERMS`) gets `fold` — *Fold* — with
no old spelling. The marks say plain words: `error`, `paused`, a number with what it counts.

## 7. Tests

- scroll: `folded` saves and loads; an old scroll without it loads open.
- catalog / core: a Pit raised from the catalog stands folded, a Barracks open.
- host: `building.fold` toggles, saves, records it, the snapshot says it; the Town Hall refuses.
- browser (tests/test_gui_browser.py): a folded hut shows its name and no body; a peek on an alert
  shows the body without moving the hut under it; a file dragged over a folded Pit peeks it.
