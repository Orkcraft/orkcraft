# Sprites

This is the brief for Camp's pixel art in the style of Warcraft 2. Office uses none of it.

**Principle:** the art is part of the frame, not a picture in it. Buildings and decorations are quiet. They name the place at a glance and never pull the eye away from the cards, the fire and the text.

## Building headers

- **Shape: a small, compact building, low and centred.** The building is twice as wide as it is high (2:1). It stands in the middle of its card's top edge. The frame's top edge stays visible on both sides, so the building reads as a finial on the frame. Never stretch a building across the card.
- **View: a flat 2D front view.** Use an orthographic elevation: no perspective, no top-down view, no three-quarter view.
- **Placement: it stands on the card and is not framed.**
  - The base is the bottom row of the sprite, and it sits directly on the card's top edge.
  - There is no ground strip and no backdrop. The background is transparent.
  - The roof rises over the map ground.
  - The card's frame, selection and fire light only the card. The selected or active building gets a soft glow behind it in the frame's colour. The UI draws that glow, so never paint it into the sprite.
- **Low detail.**
  - Use one silhouette plus **one** element that tells the building apart: an anvil-shaped chimney for the Forge, a sheaf for Task Fields, tusks and a red war banner for the Watchtower.
  - Leave out smoke, fire, embers, props, debris, banners with patterns, highlights and texture noise.
  - Fire is a UI state. It is never painted in.
- **Muted palette, matching the frame.** Use these 6–8 colours, taken from the tokens:

  | Colour | Token | Use |
  |---|---|---|
  | `#050403` | `bevel-lo` | outline |
  | `#1f1a12` | `panel` | dark oak |
  | `#3a2f1f` | `panel-raised` | oak |
  | `#7a6240` | `bevel-hi` | worn wood, the lit edge |
  | `#3e6b48` | `frame` | moss or hide, sparingly |
  | `#c99a3e` | `frame-focus` | **one** small gold accent |

  - Stone is a dark grey-brown (`#4a4438`).
  - There are no bright colours, and nothing brighter than the gold accent.
  - Keep the contrast low: the building should read as part of the card's bevelled frame.
- **Light and pixels.**
  - Light comes from the top left, with 2 shades per material.
  - Draw a 1px `bevel-lo` outline.
  - Use hard pixels on an 8px grid, with no anti-aliasing and no dithering.
- **No text.** One sprite serves every biome.

### Sizes

| Size | Card width | Building sprite | Buildings |
|---|---|---|---|
| XS | 192 | 64×32 | The Pit, The Mill, The Horn |
| S | 240 | 80×40 | Signpost, Scroll Dump, Loot Vault, The Catapult, Workshop, Custom |
| M | 288 | 96×48 | Watchtower, Task Fields, Barracks, Clan Fire, The Forge, Tally Crag |
| L | 336 | 112×56 | War Drum, File Forest, Town Hall, Lake of Insight |
| Window | any | 128×64 | every building, the same building a size up |

Files:

- `buildings/<id>/header.png`
- `buildings/<id>/banner.png`, which is the 128×64 window version
- `buildings/<id>/@2x/…`, made with nearest-neighbour scaling

**Every building**: the words that go into the header prompt below, and the sizes. Complete, ready-to-copy prompts for all 19 are in the Building prompts section.

| Building | File | Sprite | Generate at | What to write in ‹building› / ‹telling element› / gold |
|---|---|---|---|---|
| The Pit | `buildings/pit/header.png` | 64×32 | 512×256 | dug pit ringed with rough stones / a short wooden chute slanting down into it / a thin rim on the chute's mouth |
| The Mill | `buildings/mill/header.png` | 64×32 | 512×256 | low timber water-mill hut / a large wooden waterwheel half-sunk at its side, fed by a short plank chute with a thin stream of water / the wheel's axle hub |
| The Horn | `buildings/horn/header.png` | 64×32 | 512×256 | giant curved war horn / the horn resting on a wooden trestle stand / the ring of the horn's mouthpiece |
| Signpost | `buildings/signpost/header.png` | 80×40 | 640×320 | wooden waymark on a small stone mound / one post with two arms pointing left and right / the cap of the post |
| Scroll Dump | `buildings/scrolls/header.png` | 80×40 | 640×320 | small lean-to shed / a heap of rolled scrolls piled against its side / the tie of one scroll |
| Loot Vault | `buildings/loot/header.png` | 80×40 | 640×320 | squat stone strongroom / a heavy iron-bound chest lid set into its front / the chest's lock plate |
| The Catapult | `buildings/catapult/header.png` | 80×40 | 640×320 | wooden catapult at rest / its throwing arm lowered on a low frame with two wheels / the iron tip of the arm |
| Workshop | `buildings/workshop/header.png` | 80×40 | 640×320 | small plank workshop shed / a saw-tooth roof / the head of one hammer hanging by the door |
| Custom | `buildings/custom/header.png` | 80×40 | 640×320 | half-built frame of poles and planks / scaffolding around an empty doorway / one rope binding |
| Watchtower | `buildings/watchtower/header.png` | 96×48 | 768×384 | short orkish lookout tower of lashed logs on four splayed log legs, in the manner of the Warcraft III Horde watch tower / a lookout platform ringed with sharpened stakes under a pointed hide roof with two curved bone tusks, and a small ragged red war banner / the tip of the roof spike |
| Task Fields | `buildings/fields/header.png` | 96×48 | 768×384 | small timber barn with a low fence / a tied wheat sheaf leaning by the door / the wheat sheaf |
| Barracks | `buildings/barracks/header.png` | 96×48 | 768×384 | pair of hide war tents / two tent peaks side by side on wooden poles behind a low log front / the tip of one tent pole |
| Clan Fire | `buildings/council/header.png` | 96×48 | 768×384 | ring of standing stones around a cold fire pit with no flames / a low log bench in front / one carved rune stone |
| The Forge | `buildings/forge/header.png` | 96×48 | 768×384 | smithy / an anvil-shaped stone chimney / a band around the chimney |
| Tally Crag | `buildings/crag/header.png` | 96×48 | 768×384 | low rock outcrop / rows of vertical tally notches carved into its face / one notch inlaid |
| War Drum | `buildings/war_drum/header.png` | 112×56 | 896×448 | huge round war drum / the drum under a small roof on two posts / the drum's rim |
| File Forest | `buildings/forest/header.png` | 112×56 | 896×448 | grove of three dark pine tops / a low log fence with a small gate in front / the gate latch |
| Town Hall | `buildings/town_hall/header.png` | 112×56 | 896×448 | orkish great hall / a long timber hall with a steep roof and a pair of horns on the gable / the tips of the gable horns |
| Lake of Insight | `buildings/lake/header.png` | 112×56 | 896×448 | small wooden pier at the edge of a still pond / reeds at the water's edge and the water as one flat dark slate band / the cap of an unlit lantern post |

## Map ground

The ground is **one flat colour per biome**, with no patches, no texture and no tiles.

| Biome | Ground |
|---|---|
| Forest (`camp`) | `canvas` #172a0a (a dark moss green the footpath's verge melts into) |
| Ice (`camp-ice`) | `canvas` #070d14 |
| Void (`camp-void`) | `canvas` #080808 |

## Decorations

There are **5–7 per screen in all**, scattered by the app.

- They never sit under a card or touch one. Keep a margin of 24px or more.
- They are not interactive.
- Draw them in the same flat front view and the same muted style as the headers, but darker. Each one is a silhouette with 2 shades, about 1.5:1 against `canvas`, so it reads as a shape in the dark and not as an object to look at.

| Biome | Files | Size | Variants |
|---|---|---|---|
| Forest | `doodads/forest/tree-1…3.png` | at most 16×24 | a pine, a broad oak, a dead tree |
| Forest | `doodads/forest/bush-1…3.png` | at most 16×12 | a round bush, a fern, a stump |
| Ice | `doodads/ice/mountain-1…3.png` | at most 32×24 | an icy peak, a twin peak, a low glacier ridge |
| Ice | `doodads/ice/tree-1…2.png` | at most 16×24 | a snow-laden pine, a bare frozen tree |
| Void | `doodads/void/rock-1…3.png` | at most 32×24 or 16×12 | ash rocks, a broken spire |

## Roads and carts

Roads are subscriptions between buildings, and carts are the events travelling along them. Road tiles lie on the map, so they are drawn **top-down**, like the Warcraft 2 map. Carts are drawn **from the side**, in the same flat 2D view as the building headers. They follow the same quiet rule: they are lower in contrast than the cards, and only the selected road and its carts draw the eye. The UI draws that emphasis, so it is never painted in.

### Road tiles

- **Grid.** Roads use 32×32 tiles (two steps of the map's 16px grid), centred on the road's line. The path is about a third of the tile wide through its middle and meets every edge it reaches straight on, so tiles join edge to edge.
- **Look.** A forest footpath: packed dark earth (#5a4128, ruts #3e2c1a, lit #7a5c36) with two foot-worn ruts and a thin uneven verge of dark moss (#2f5216 / #24410f) with a few leaves and pebbles. Outside the verge the tile is transparent; the verge melts into the forest ground #172a0a.
- **Biomes.** The same footpath serves every biome for now. Optional variants are `-ice` (packed snow: #2b4763 / #8fa3b5) and `-void` (ash: #2a2620 / #4d4538).
- **States.** These are drawn by the UI, never painted in:
  - faint (a road of an unselected building): the tile at 85% opacity;
  - bright (a road of the selected building): the tile as drawn;
  - selected: the tile with a 1px `road-selected` glow and its label chip.

**Tiles.** The app turns them by 90° steps. Return roads use the straight, every other tile, fainter.

| File | What | Derived by the app |
|---|---|---|
| `roads/straight.png` | a horizontal straight | the vertical straight |
| `roads/corner.png` | a corner from the right edge down to the bottom edge (┌), a rounded inner curve | ┐ └ ┘ |
| `roads/tee.png` | a tee: left to right with a branch down (┬) | ├ ┤ ┴ |
| `roads/cross.png` | a crossing (┼) with a small trodden clearing | — |
| `roads/end.png` | a dead end with the path coming in from the left and a rounded end | the other three directions |
| `roads/gate-out.png`, `roads/gate-in.png` | the path coming in from the left to a small wooden post: a gold ▶ where a road leaves a card, a gold ● ring where it enters one; turned so the post stands at the card | the four sides |

### Carts

A cart is one event (a commit, a mail, a dropped file), shown as an orkish **mine cart** (a squat iron tub on two small wheels) riding along the plank road. Its iron body and gold load must stand out against the brown road, so it differs from the road in colour as well as shape. A first handcart drawn in wood blended into the road.

- **Size.** 20×18: a stocky tub. At 16px a side-profile cart turns into a blob, and 32×24 is too heavy for the map.
- **Placement.** On a horizontal road, the bottom of the wheel sits 2px above the bottom edge of the track, so the cart rides on the road rather than sinking into it.
- **View: a flat side profile.** This is an orthographic side elevation: no perspective, no top-down view, no three-quarter view. You see one wheel, the side of the box and the handles, as in a side-scroller. The cart stands on the bottom row of the sprite.
- **Directions.** The mine cart is symmetric, so one side-profile sprite (`carts/minecart.png`) serves both left and right; a second frame with the wheels turned is optional. On a vertical road the app uses `carts/cart-down.png` (front view, coming towards you) and `carts/cart-up.png` (back view, going away); both are done. Both are 20×18, the same size as the side view, in the same flat 2D style, centred on the track.
- **Palette.** The tub is dark iron and slate, cooler and darker than the road: outline #050403, iron #2a2a2e, iron edge #55555c, slate #3a3a40. The rim is riveted gold #c99a3e, and the load heaped in the tub is a gold-amber #e8b94a. Wood (#3a2f1f) is used only for the wheel hubs, if at all.
- **Status.** The UI draws status, never the sprite:
  - sent and delivered: as drawn;
  - held: the cart stops at the gate with a 1px `cart-held` outline;
  - error: it stops with a `cart-error` outline;
  - filtered: 50% opacity, then it turns back.
- **Jams.** `carts/jam.png` (24×16) shows three carts nose to tail. When more than six carts are on one road, the UI shows it with a ×N counter.
- **Coin.** `icons/coin.png` (16×16) flashes at a frame when an agent spends.

**Prompts** (add the shared tail of the decorations, without the magenta line if the generator handles transparency):

> Pixel art in the style of Warcraft II (1995), top-down view of a map tile: **‹a straight packed-dirt road running left to right / a road corner coming in from the right edge and turning down to the bottom edge / a four-way dirt crossroads / a dirt road coming in from the left and ending in a rounded dead end›**. The track is exactly half the tile's height, centred, with darker wheel ruts and a 1px darker verge. Palette only #5c4326 #3f2e1a #a0703c. Seamless: the track meets the tile edges straight on. Square 1:1 canvas, chunky pixels, very low detail, no stones, no grass, no text. Solid flat magenta #ff00ff outside the track.

> Pixel art in the style of Warcraft II (1995): a small orkish mine cart seen exactly from the side, as a flat 2D side profile (orthographic side elevation, no perspective, not top-down, not isometric, not three-quarter). It is a squat, slightly tapered iron tub on two small solid wheels, with a thick riveted gold rim along the top edge and a heap of glowing gold-amber ore rising just above the rim. The wheels sit on one straight base line at the very bottom of the image. The silhouette is stocky, about 4:3, as tall as it is wide or a little wider. The body is dark iron, clearly cooler and darker than brown wood. Palette only #050403 #2a2a2e #55555c #3a3a40 #c99a3e #e8b94a. Chunky pixels, very low detail, 2 shades per material, 1px dark outline, no shadow, no ground, no rails, no text. Solid flat magenta #ff00ff background. Square 1:1 canvas, with the cart centred.

**Moving down (front view):**

> Pixel art in the style of Warcraft II (1995): the same small orkish mine cart seen exactly from the front, coming straight towards the viewer, as a flat 2D front elevation (orthographic, no perspective, not top-down, not isometric, not three-quarter). The squat iron tub is seen from its front end: a slightly tapered trapezoid with a thick riveted gold rim along the top and a heap of glowing gold-amber ore rising just above the rim. Two small solid wheels show at the bottom left and bottom right, seen edge-on as short dark stubs. Everything stands on one straight base line at the very bottom of the image. The silhouette is about as wide as it is tall. The body is dark iron, clearly cooler and darker than brown wood. Palette only #050403 #2a2a2e #55555c #3a3a40 #c99a3e #e8b94a. Chunky pixels, very low detail, 2 shades per material, 1px dark outline, no shadow, no ground, no rails, no text. Solid flat magenta #ff00ff background. Square 1:1 canvas, with the cart centred.

**Moving up (back view):** use the same prompt, but with "seen exactly from behind, moving straight away from the viewer" and a plain iron back panel with one gold coupling hook in the middle.

Generate tiles and carts at 8× (128×128) and reduce them to 16×16 with nearest-neighbour scaling. Keep the texture to 2–3 rows of light marks: finer detail averages away at 16px, as it did on the first straight tile.

## Shared sprites

| File | Size | Use |
|---|---|---|
| `fx/fire.png` | 64×16: 4 frames of 16×16 in a row, a 0.6 s loop | Small flames over a burning building's roof. The UI adds 1 to 4 of them. **Done.** |
| `icons/<action>.png` | 32×32 | Command buttons. Same muted palette, gold for the symbol. |
| `icons/res-*.png` | 16×16 | HUD resources: `res-quota` (hourglass), `res-gold` (coins), `res-lumber` (crossed logs), `res-meat` (meat on the bone). **Done.** |
| `portraits/<kind>.png` | 46×38 | Ork portraits (agent, chain, hybrid, Builder, Peon, Grunt, Goblin) |

## The ork

The ork replaces the 🧌 pictograph everywhere in Camp: the roster, the War Map, the Command Card and the HUD. It follows the house reference: a round green head with no body, heavy brows, tired half-lidded eyes with purple bags, two pale tusks along the cheeks and a flat line of a mouth. No tie and no pickaxe: the head alone reads best at small sizes.

| File | Size | Use |
|---|---|---|
| `orks/ork.png` | 16×15 (`ork-w` × `ork-h`) | Badges, the roster, the War Map and anywhere 🧌 stood. **Done.** It sits inside the badge plate with room to spare. |
| `orks/ork-portrait.png` | 26×24, centred in the 46×38 portrait slot | The Command Card and the selected ork. **Done:** the source at its own pixel grid. |
| `orks/ork-idle.png`, `ork-busy.png`, `ork-waiting.png` | 16×15 | The ork's states, replacing 💤, ⚙ and 🔥: eyes shut; heavy lids, brows dipped and a drop of sweat; brows up, eyes wide and a flame on the head. **Done**, drawn as pixel edits of `ork.png` so the four heads match exactly. |

- **Why 16×15.** It sits inside the badge plate, title bars included, without touching the plate's edges. With the tie gone, the head alone still reads at this size: brows, eyes and tusks survive. At 20px the head overflowed the plate in window title bars.
- **How the done sprites were made.** The source is pixel art on an uneven generator grid (about 23 px per cell). The portrait was rebuilt by finding the cell edges and taking each cell's median colour, giving 26×24. The 16×15 icon is a block reduction of the source that keeps the outline, with the eye rows mirrored so both eyes match.
- For a variant, draw it once, large, on the same grid as the base and reduce it the same way. Keep the outline and the tusks; they carry the face.
- Its greens are muted and a little darker than the reference so it sits with the frames. The selected ork is outlined in `frame-focus` by the UI, never in the art.
- Office shows no ork sprite. It says "Agent" in words.

**Ork prompt:**

> Pixel art in the style of Warcraft II (1995): the head of a tired orkish office worker, drawn as a flat 2D front view (no perspective, not three-quarter). The head is an almost perfect circle with no neck and no body: muted moss-green skin in 3 shades with a soft lighter patch at the top left, a 1px dark green outline. Heavy straight dark-green brows; tired, half-lidded pale-yellow eyes with black pupils and dull purple bags under them. Two pale bone tusks run diagonally up along the lower cheeks from the mouth corners. The mouth is one flat dark line, with a short lighter chin line below it. Nothing below the chin: no tie, no tools, no body. Palette only #12261b #2f5e46 #4f8a45 #6aa84f #93c45a #e6e2b8 #6e5470 #d8c79a #a89470 #1a1a1a. Chunky pixels, very low detail, a calm, deadpan, slightly sleepy expression, no shadow, no ground, no text. Solid flat magenta #ff00ff background. Square 1:1 canvas, with the head centred and filling about 70% of it.

For a state variant, keep the prompt and change only the face: **idle** "the eyes are closed as two short flat lines"; **busy** "the brows are drawn together in focus and a single drop of sweat sits on the forehead"; **waiting** "the brows are raised, the eyes wide open, and one small orange flame burns on top of the head".

## Still to draw

These sprites don't exist yet, listed in the order they matter. Every prompt asks for a solid magenta background, which is keyed out afterwards. Road tiles, the cart's back view, decorations and the ork variants have their prompts in their own sections above.

| # | Sprite | Files | Size | Replaces |
|---|---|---|---|---|
| 1 | Window banners | `buildings/<id>/banner.png` | 128×64 | the header stretched onto an opened window |
| 2 | Decorations | more forest trees and bushes, a third ice peak, more void rocks (done: pine, dead tree, stump, two ice peaks, frozen tree, ash spire) | 16×12 to 32×24 | the empty decoration slots |

**Window banners (128×64):** use the building's prompt from Building-prompts with two changes: "the same building a little wider, with one more element of its shape (a side wing, a second window, a fence post)" and a 2:1 canvas. Keep the palette and the level of detail.

## Prompt templates

Generate at 8× the target size (so 768×384 for an M header). Then reduce it with nearest-neighbour scaling. Add the shared tail below to every prompt.

**Shared tail:**

> Flat 2D front view (orthographic elevation, no perspective, not top-down, not isometric). Muted, low-contrast palette of only these colours: outline #050403, dark oak #1f1a12, oak #3a2f1f, worn wood #7a6240, dark stone #4a4438, moss #3e6b48, and one tiny gold accent #c99a3e. Very low detail, chunky pixels on an 8px grid, 2 shades per material, light from the top left, 1px dark outline. No smoke, no fire, no glow, no props, no texture noise, no text, no UI. Solid flat magenta #ff00ff background everywhere around the shapes.

**Building header (2:1):**

> Pixel art in the style of Warcraft II (1995): a single small, compact orkish **‹building›**, low and squat, with **‹its one telling element›**. The only gold is **‹gold›**. It is centred and fills the canvas, its base a straight line along the very bottom edge, like a small finial standing on top of a wooden frame. 2:1 canvas, twice as wide as it is high. ‹shared tail›

**Window version (2:1, 128×64):** use the same prompt with a little more of the same building's shape, and the same palette and level of detail.

**Decoration:**

> Pixel art in the style of Warcraft II (1995): a single tiny **‹pine tree / round bush / icy mountain peak›**, drawn as if for a 16×24 (tree) or 32×24 (mountain) sprite, so only a few big pixel steps,, as a dark silhouette with 2 shades. It is meant to sit almost unnoticed on a dark **‹forest / snow›** ground, with its base on the very bottom edge. Palette: **‹forest: #0a130c #1f3823 #2b4a30 · ice: #070d14 #162736 #2b4763 #8fa3b5 for the snow caps only›**. Chunky pixels, very low detail, 1px darker outline. No glow, no text. Solid flat magenta #ff00ff background. **‹1:1.5 / 4:3›** canvas.

**Post-processing:**

1. Key out #ff00ff.
2. Downscale ×1/8 with nearest-neighbour scaling to the exact size.
3. Quantize to the palette above, without dithering.
4. Check that the base touches the bottom row and that the building is centred.
