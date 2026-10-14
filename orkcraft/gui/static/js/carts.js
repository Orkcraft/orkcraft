// Carts on the roads (docs/design/roads-and-orcs.md §4a, town-readability.md §3, design-system-v2.md §4e). Each one
// the town sent lately rolls by itself from its road's exit gate to its entry gate once, in the time the road takes
// (`travel`, else a short trip); a filtered one turns back at the source. Orks never move carts: the town routes them.
// A cart that stopped stands at its road's buffer stop, its flag saying why: yellow, it waits for the person (its chip
// `#42 · title` always shown); ⏳, held; red, stuck. Several there are a pile with a ×N chip, never a line of carts.
// Camp draws a mine cart with its load on top (code, an asset, a message, a doc, a bundle) from the v2 sprites; Office a gold stack
// moving and a square in its state's colour standing; the map zoom a dot. The words are the same in both.
import { html, cls } from "./html.js";
import { say } from "./link.js";
import { selected } from "./windows.js";

const started = new Map();               // cart id → its animation-delay, fixed when first seen
const SHORT_TRIP_S = 1.6;
const CHIP_CHARS = 20;                   // a chip's title, cut (design-system-v2.md §5)
const LOUD = ["ask", "stuck", "held"];   // a pile's flag: its loudest cart's
const BEHIND = 14;                       // px between carts in a pile, back along the track
const SHOWN_IN_PILE = 3;

function delayOf(c) {
  if (!started.has(c.id)) {
    started.set(c.id, `${-Math.min(c.age, 30)}s`);
    if (started.size > 400) started.delete(started.keys().next().value);
  }
  return started.get(c.id);
}

const cut = (s, n) => (s.length > n ? `${s.slice(0, n - 1).trimEnd()}…` : s);

/** A cart's chip: its short ref and its title cut. */
export function chipOf(c) {
  const title = cut(say(c.title || ""), CHIP_CHARS);
  return [c.ref, title].filter(Boolean).join(" · ");
}

// Camp's mine cart from the v2 sprites (design-system/sprites/camp/carts/, placeholders the artist's replace in place):
// the bin from the side, its four rolling frames while it moves, the load over the bin (its foot behind the rim) and the
// flag on its pole at the back left, at their art size (overview: one CSS px an art px).
const SPRITES = "/ds/sprites/camp/carts";

function MineCart({ load, state, rolling }) {
  const flag = { ask: "ask", held: "held", stuck: "fire" }[state];
  return html`<span class=${cls("gui-minecart", { "is-rolling": rolling })} data-load=${load} data-state=${state}>
    ${flag && html`<span class="gui-minecart__flag" style=${`background-image: url(${SPRITES}/flags/${flag}.png)`}></span>`}
    <span class="gui-minecart__load" style=${`background-image: url(${SPRITES}/loads/${load}.png)`}></span>
    <span class="gui-minecart__bin"></span>
  </span>`;
}

/** One cart as either look draws it: Camp's mine cart, Office's gold (moving) or square (standing), the map's dot. */
function Cart({ c, rolling = false }) {
  return html`<${MineCart} load=${c.load || "asset"} state=${c.state || "moving"} rolling=${rolling} />
    <img class="gui-cart__gold" src="/ds/sprites/icons/res-gold.png" srcset="/ds/sprites/icons/res-gold@2x.png 2x" width="8" height="8" alt="" />
    <span class="gui-cart__square"></span>`;
}

/** Where a road's carts stand: the middle of its last cell before the building, and the way they rolled in. */
function stopOf(p) {
  const cs = p.cells || [];
  if (cs.length < 2) return { x: p.entry[0], y: p.entry[1], dx: 0, dy: 0 };
  const [a, b] = [cs[cs.length - 2], cs[cs.length - 1]];
  return { x: a[0] * p.cell + p.cell / 2, y: a[1] * p.cell + p.cell / 2, dx: b[0] - a[0], dy: b[1] - a[1] };
}

/** The carts that stand at one road's stop: the loudest in front, up to two behind it, the chips. */
function Pile({ road, p, here, door }) {
  const sorted = [...here].sort((a, b) => LOUD.indexOf(a.state) - LOUD.indexOf(b.state) || b.age - a.age);
  const top = sorted[0], s = stopOf(p);
  const asks = sorted.filter((c) => c.state === "ask");
  const shown = sorted.slice(0, SHOWN_IN_PILE).reverse();
  return html`<div class=${cls("gui-pile", `is-${top.state}`, { "is-westward": s.dx < 0 })} style=${`left:${s.x}px;top:${s.y}px`} data-road=${road}
      title=${sorted.map(chipOf).filter(Boolean).join("\n")}>
    ${shown.map((c, i) => {
      const back = shown.length - 1 - i;
      return html`<div key=${c.id} class=${cls("gui-cart is-standing", `is-${c.state}`, { "is-behind": back > 0 })}
          style=${`transform: translate(${-s.dx * back * BEHIND}px, ${-s.dy * back * BEHIND}px)`}>
        <${Cart} c=${c} />
      </div>`;
    })}
    ${here.length > 1 && html`<span class="gui-cart__chip gui-pile__count ok-font-status">×${here.length}</span>`}
    ${(asks.length ? asks : [top]).slice(0, 1).map((c) => chipOf(c) && html`<span key="chip"
      class=${cls("gui-cart__chip gui-pile__chip ok-font-status", { "is-always": c.state === "ask" && !door })}>${chipOf(c)}</span>`)}
  </div>`;
}

/** `roads` the town's (a moving cart's title shows on the selected building's roads only); `asking` the buildings
 *  whose door already shows a waiting cart's chip (js/hut.js Waiting): their pile's chip shows on hover. */
export function Carts({ paths, carts, travel, roads = [], asking = new Set() }) {
  const byRoad = Object.fromEntries(paths.map((p) => [p.id, p]));
  const ends = Object.fromEntries(roads.map((r) => [r.id, [r.from, r.to]]));
  const active = selected.value;
  const trip = travel > 0 ? travel : SHORT_TRIP_S;
  const standing = {};
  for (const c of carts) if (c.stands && byRoad[c.road]) (standing[c.road] ||= []).push(c);
  return html`<div class="gui-carts" aria-hidden="true">
    ${carts.filter((c) => !c.stands && byRoad[c.road] && c.age < trip + 1).map((c) => {
      const p = byRoad[c.road];
      const d = "M" + p.points.map((q) => q.join(" ")).join(" L");
      const back = c.status === "filtered";
      const named = !!active && (ends[c.road] || []).includes(active);
      return html`<div key=${c.id} class=${cls("gui-cart is-rolling", { "is-back": back, "is-held": c.status === "held", "is-error": c.status === "error" })}
          style=${`offset-path: path("${d}"); animation-duration: ${back ? SHORT_TRIP_S : trip}s; animation-delay: ${delayOf(c)}`}>
        <${Cart} c=${c} rolling=${true} />
        ${c.title && !back && named && html`<span class="gui-cart__label">${say(c.title)}</span>`}
      </div>`;
    })}
    ${Object.entries(standing).map(([road, here]) => html`<${Pile} key=${`pile-${road}`} road=${road} p=${byRoad[road]} here=${here}
      door=${asking.has((ends[road] || [])[1])} />`)}
  </div>`;
}
