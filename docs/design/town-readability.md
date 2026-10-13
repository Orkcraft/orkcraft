# Design — carts, orks and their link, readable on a bright camp

Status: proposal 2026-10-13, the owner's ask after the round-2 frame ([color-pass.md](color-pass.md) §9c); nothing
built. Builds on [ork-console.md](ork-console.md) §5 (one status), [cart-waybill.md](cart-waybill.md) §4 (an ork's
status names its cart), [work-and-play.md](work-and-play.md) (Office gives the same as rows).

## 1. The problem

The camp is now bright: saturated grass, warm paths, red banners. Carts and orks are small sprites on it. They are lost
first, and so are what they carry, whether an ork works, waits or is stuck, and which ork works on which cart.

## 2. The rules

1. **Separate by value, not by colour.** Every cart and ork has a one-pixel dark outline and a small dark shadow
   ellipse, as cosy farming games draw them. The ground stays in a middle value band ([color-pass.md](color-pass.md)
   §9c: a step quieter, two or three tones), so a dark outline always reads. Checked in grey.
2. **Signal colours are reserved.** Yellow means a question (❓). Red with a flicker means an error or 🔥. Neither
   appears in the ground or the buildings. **The banners' red goes darker, towards maroon**, and an error is told
   from a banner by its shape and motion as well as its colour.
3. **Normal work is motion; only exceptions are badges.** A working ork swings its tool. A badge over its head appears
   only for what needs the person or explains a stop. A camp where everything has a badge reads as noise.
4. **Text lives on UI chips, not on the grass.** Any word on the map (a cart's title, a count) sits on a small dark
   chip in the GUI's own font and tokens: the Office look's chip drawn over Camp. Never pixel text straight on the
   ground.
5. **More detail as you zoom in, and on attention.** By default the map shows signals; words appear when they are
   asked for.

## 3. A cart

| zoom | what it shows |
|---|---|
| map | a dot in its state's colour; ❓/🔥 if it waits or is stuck |
| overview (the GIF's zoom) | the cart sprite, its **load as an icon**, its **state flag** |
| close, hover or selected | a chip above it: `#42 · Login form` (short ref and a title cut at about 20 characters) |

- **The load says its kind**, one icon on top of the cart: a scroll with `</>` (code), a crate (an asset), a sealed
  letter (a message from outside), a book (a doc). A number badge `×3` when it carries several items.
- **The state flag** on its pole: moving (no flag), waiting for a person (yellow), held for a limit's reset (⏳),
  stuck (red, flickering), at the gate (the gate's own colour).
- **A queue is a pile**, not a line of sprites: a pile of carts beside the building and a `×4` chip.
- **The chip is always shown** for a cart that waits for the person, so a question never hides behind a hover.

## 4. An ork

| state ([ork-console.md](ork-console.md) §5) | how it is drawn |
|---|---|
| working | the tool swings; no badge |
| asks | yellow ❓ bubble, the loudest thing in the camp |
| stuck or error | a red `!` that flickers (the 🔥 stays on its building) |
| held for a limit | ⏳ badge, the ork sits |
| idle | sits by its building, slightly dimmed (today's `brightness(.78)`) |

The badge stands on a dark chip with an outline, so yellow and red read on green.

## 5. An ork and its cart

1. **Next to each other in the world.** Orks never move carts: the town routes a cart along its road by itself
   (the owner, 2026-10-13). An ork works on a cart **inside its building**: the cart stands at the ork's place at
   the table, and leaves by the track when the work is done. Most of the time the link is seen with no help.
2. **A spotlight on hover or select.** Pointing at an ork or a cart draws a short dashed rope between them, lifts
   both, and dims the rest of the camp (about 30 % less saturation). The same works from the 🥩 list: pointing at a
   row lights its ork and cart in the camp.
3. **Named in words.** The ork's status line names its cart ([cart-waybill.md](cart-waybill.md) §4): "Grunt: on #42,
   waits for your answer". The cart's chip names its ork when one holds it.
4. **No colour per pair.** Giving each ork and cart a matching colour runs out after five pairs and collides with the
   reserved colours of §2.

## 6. How it is checked

On the reference frame and then in the town, at the overview zoom on a 13-inch laptop:

- **The grey test:** every cart and ork is seen apart from the ground.
- **Five seconds:** "which ork waits for you, and which cart is stuck?" Both are found.
- **The link:** with eight orks and ten carts, pointing at the waiting ork shows its cart in under a second.
- **The phone:** the same chips at least 11 px tall, tap in place of hover.

## 7. Priority

- **P0 now**, with the colour pass ([color-pass.md](color-pass.md) §3) and one status: the outlines and shadows, the
  reserved signal colours (the banners to maroon), badges only for exceptions, the chip always on a cart that waits.
- **P0 before the launch**, with the GIF: the load icons and the state flags at the overview zoom.
- **P1**, with the waybill ([cart-waybill.md](cart-waybill.md)): the spotlight and rope, piles for queues, zoom
  levels of detail.
- **No:** a colour per ork-and-cart pair; titles always on for every cart.
