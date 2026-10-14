// The card is the building (docs/design/design-system-v2.md §4a, color-pass.md §6a–6c; backlog C3), for the five core
// buildings first: Task board, Agent pool, Review gate, Inspector, External listeners. The others keep today's card
// until their turn.
//
// At the map and the overview zoom a building is its **cover** — a hall's roof, an open ground's scene, a tower or a
// gate — with its **facade** at the door and its **crest** above; the signals sit on the cover: ❓ over it, 🔥 as the
// cover smouldering, a count chip at the door. Close up the cover fades in a quarter-second, the walls stay as the
// card's frame, the inside is the card and the crest becomes its header mark. Hover or select makes it half-clear.
// Office keeps the same place and size with no cover: the walls are the card's plain border (a look changes the
// drawing, never the place). On the phone a tap opens the card as a sheet from the bottom (js/pocket.js).
//
// The art is the v2 kit in design-system/sprites/camp/ (§11), drawn once a piece is there; until then each piece is
// a neutral placeholder in the art tokens (cover.css). The GUI asks the server which pieces it has (kit.json), so it
// never asks for a file that is not.
import { signal } from "@preact/signals";
import { html, cls } from "./html.js";
import { town, say } from "./link.js";
import { TypeIcon } from "./icons.js";

// The five, by type id (code names stay, CLAUDE.md): the cover's kind and material, the footprint (the owner's answer
// 8: Agent pool L, the others M), the crest (one per building, never repeated in a camp) and the facade's file.
export const CORE = {
  watchtower: { kind: "tower", size: "M", crest: "horn", facade: "watchtower" },
  fields: { kind: "hall", roof: "thatch", size: "M", crest: "skull", facade: "fields" },
  barracks: { kind: "hall", roof: "canvas", size: "L", crest: "axes", facade: "barracks" },
  loot: { kind: "gate", size: "M", crest: "banner", facade: "loot_vault" },
  lake: { kind: "open", size: "M", crest: "lens", facade: "lake" },
};

/** The inside of a building in art pixels (v2 §2.4); the card close up is twice that, today's widths. */
export const FOOTPRINT = { XS: [96, 64], S: [120, 80], M: [144, 96], L: [168, 112] };
/** The walls round the inside, CSS px (cover.css --wall-*): the sides and the front, the back. Placeholders until the
 *  walls kit lands. For now they stand inside today's card widths (a card keeps its place on the town and in its
 *  neighbours' way), not outside the footprint as v2 §4b draws them. */
export const WALL = { side: 12, back: 16 };
const TITLE = 28;                                   // the card's title bar (--titlebar)

/** A core building's kit, or null (any other building, the Town Hall): the five keep a cover. */
export const coverOf = (b) => (b && CORE[b.type]) || null;

/** The box of a covered card, CSS px, by zoom: its width at every level but the map's (half), its height at the overview
 *  (the footprint under its title) and on the map (half of that). Close up its height is what its card says. */
export function coverBox(kit, lvl) {
  const [fw, fh] = FOOTPRINT[kit.size] || FOOTPRINT.M;
  const w = 2 * fw, h = fh + TITLE + WALL.side + WALL.back;
  return lvl === "a" ? [Math.round(w / 2), Math.round(h / 2)] : [w, h];
}

// -- the kit's sprites ----------------------------------------------------------------------------------------------
export const kitFiles = signal(new Set());
if (typeof fetch === "function") {
  fetch("/ds/sprites/camp/kit.json").then((r) => (r.ok ? r.json() : { files: [] }))
    .then((d) => { kitFiles.value = new Set(d.files || []); }, () => {});
}
const has = (path) => kitFiles.value.has(path);
const url = (path) => `/ds/sprites/camp/${path}`;
// The nine pieces (v2 §4b): corners on top, then the edges, the centre under them; [w, h] in art px. The back (top)
// corners and edge are 32 deep, the others 24; edges repeat every 8 px along their length.
const PIECES = { nw: [24, 32], ne: [24, 32], sw: [24, 24], se: [24, 24], n: [8, 32], s: [8, 24], w: [24, 8], e: [24, 8], c: [32, 32] };
const AT = (k) => ({ nw: "left top", ne: "right top", sw: "left bottom", se: "right bottom", n: `${24 * k}px top`,
  s: `${24 * k}px bottom`, w: `left ${32 * k}px`, e: `right ${32 * k}px`, c: "center" });
const REPEAT = { nw: "no-repeat", ne: "no-repeat", sw: "no-repeat", se: "no-repeat", n: "repeat-x", s: "repeat-x",
  w: "repeat-y", e: "repeat-y", c: "repeat" };

/** A nine-slice kit (`covers/hall/roof-canvas`) as a background, once all its pieces are here; else null. `k`: CSS px
 *  per art px (the walls are drawn at ½ till the frame has room for their art size). */
function nineSlice(dir, k = 1) {
  const names = Object.keys(PIECES);
  if (!names.every((n) => has(`${dir}/${n}.png`))) return null;
  const at = AT(k);
  return names.map((n) => `url("${url(`${dir}/${n}.png`)}") ${at[n]} / ${PIECES[n][0] * k}px ${PIECES[n][1] * k}px ${REPEAT[n]}`).join(", ");
}

/** The cover's own picture: a roof kit for a hall, else its kind's one sprite (the pond, the lookout, the gatehouse).
 *  On the map, the pipeline's half-size copies (`map/`, v2 §11), never resampled live. */
function coverArt(kit, far) {
  const map = far ? "map/" : "";
  if (kit.kind === "hall") {
    const bg = nineSlice(`${map}covers/hall/roof-${kit.roof}`, far ? 0.5 : 1);
    return bg ? `background:${bg}` : "";
  }
  const one = { open: "covers/open/pond.png", tower: "covers/tower/lookout.png", gate: "covers/gate/gatehouse.png" }[kit.kind];
  const file = one && (has(`${map}${one}`) ? `${map}${one}` : has(one) ? one : null);
  // at its own size, its foot on the front wall, on the yard's trodden earth
  return file ? `background:url("${url(file)}") center bottom / auto no-repeat, var(--world-earth)` : "";
}

/** The walls kit as the card's frame, once it is here (cover.css draws stone or logs till then): stone round a hall and
 *  an open ground, the palisade round a tower's or a gate's yard. */
export function wallArt(kit) {
  const bg = nineSlice(kit.kind === "tower" || kit.kind === "gate" ? "covers/hall/walls-palisade" : "covers/hall/walls-stone", 0.5);
  return bg ? `--walls-art:${bg};` : "";
}

/** The building's crest: its sprite once it is here, else a bone plate on a pole with its type's sign. `mark`: drawn
 *  small in the card's title bar, the header mark close up. */
export function Crest({ b, kit, mark = false }) {
  const file = `crests/${kit.crest}.png`;
  return html`<span class=${cls("gui-crest", { "is-mark": mark, "is-art": has(file) })} aria-hidden="true">${has(file)
    ? html`<img class="gui-crest__art" src=${url(file)} alt="" draggable="false" />`
    : html`<span class="gui-crest__plate"><${TypeIcon} type=${b.type} /></span>`}</span>`;
}

function Facade({ kit }) {
  const file = `facades/${kit.facade}.png`;
  return html`<span class=${cls("gui-cover__facade", { "is-art": has(file) })} aria-hidden="true">${has(file)
    && html`<img src=${url(file)} alt="" draggable="false" />`}</span>`;
}

// -- the signals on the cover ---------------------------------------------------------------------------------------

/** The orks of a building in the 🥩 list (core/slots.py): at work, and asking (an open question counts once). */
export function countsOf(b) {
  const rows = ((town.value && town.value.slots) || {}).rows || [];
  const mine = rows.filter((r) => r.building_id === b.id);
  const asks = Math.max(mine.filter((r) => r.state === "asks").length, b.alert ? 1 : 0);
  const work = mine.filter((r) => r.state === "thinking" || r.state === "tool").length;
  return { work, asks };
}

/** `🥩 2 · ? 1` on a chip at the door (v2 §5.3), only while something is at work or asks. */
function Count({ b }) {
  const { work, asks } = countsOf(b);
  if (!work && !asks) return null;
  const said = [work && say(`${work} at work`), asks && say(`${asks} asks you`)].filter(Boolean).join(" · ");
  return html`<span class="gui-cover__count" title=${said} aria-label=${said}>${work ? html`<img class="ok-sprite"
    src="/ds/sprites/icons/res-meat.png" srcset="/ds/sprites/icons/res-meat@2x.png 2x" width="12" height="12" alt=""
    draggable="false" />${work}` : ""}${work && asks ? html`<span class="gui-cover__sep">·</span>` : ""}${asks
    ? html`<b class="gui-cover__q">?</b>${asks}` : ""}</span>`;
}

/** The cover of a core building in Camp: the roof (or scene, or tower, or gate) that lifts close up, its facade at the
 *  door, its crest above, ❓ over it, the count chip at the door and its name under it (on the map too, till the crests
 *  are art enough to tell the buildings apart). `fire`: what burns on the roof
 *  (js/hut.js Flames). Drawn inside the card, over it; the card's own words stay under it, unseen but wired. */
export function Cover({ b, kit, number, lvl, burning = false, fire = null }) {
  const far = lvl === "a";
  const asks = countsOf(b).asks > 0;
  return html`<span class=${cls(`gui-cover is-${kit.kind}`, { [`is-${kit.roof}`]: !!kit.roof, "is-burning": burning })}>
    <span class=${cls("gui-cover__roof", { "is-art": !!coverArt(kit, far) })} style=${coverArt(kit, far)}>${burning && html`<span class="gui-cover__smoke" aria-hidden="true"></span>`}${fire}</span>
    ${!far && html`<${Facade} kit=${kit} />`}
    <span class="gui-cover__top"><${Crest} b=${b} kit=${kit} />${asks
      && html`<span class="gui-cover__ask" role="img" title=${say("A question waits for you")} aria-label=${say("Asks you")}>?</span>`}</span>
    ${!far && html`<${Count} b=${b} />`}
    ${html`<span class="gui-cover__name" title=${number <= 9 ? say(`Press ${number} to open it`) : ""}><span class="no">${number}</span>${say(b.title)}</span>`}
  </span>`;
}

// -- the spotlight from the 🥩 list (v2 §8): a row pointed at lights its building and its ork --------------------------
export const lit = signal(null);          // the 🥩 row pointed at: {key, building_id}
