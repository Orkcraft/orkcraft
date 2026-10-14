// Carts on the roads (docs/design/roads-and-orcs.md §4a, town-readability.md §3, design-system-v2.md §4e). Each one
// the town sent lately rolls by itself from its road's exit gate to its entry gate once, in the time the road takes
// (`travel`, else a short trip); a filtered one turns back at the source. Orks never move carts: the town routes them.
// A cart that stopped stands at its road's buffer stop, its flag saying why: yellow, it waits for the person (its chip
// `#42 · title` always shown); ⏳, held; red, stuck. Several there are a pile with a ×N chip, never a line of carts.
// Camp draws a mine cart with its load on top (code, an asset, a message, a doc, a bundle); Office a gold stack
// moving and a square in its state's colour standing; the map zoom a dot. The words are the same in both.
import { html, cls } from "./html.js";
import { say } from "./link.js";
import { selected } from "./windows.js";
import { CELL } from "./roads.js";

const started = new Map();               // cart id → its animation-delay, fixed when first seen
const SHORT_TRIP_S = 1.6;
const CHIP_CHARS = 20;                   // a chip's title, cut (design-system-v2.md §5)
const LOUD = ["ask", "stuck", "held"];   // a pile's flag: its loudest cart's
const BEHIND = 7;                        // px between carts in a pile, back along the track
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

// The load, drawn small in the world's tokens over the bin (a placeholder until design-system/sprites/camp/carts/
// loads/ land): a scroll with </>, a crate, a sealed letter, a book, three sacks.
const LOADS = {
  code: html`<rect x="5" y="0" width="10" height="7" rx="1" class="is-bone" />
    <path d="M8 2 L6.5 3.5 L8 5 M12 2 L13.5 3.5 L12 5 M10.8 1.6 L9.2 5.4" class="is-ink" />`,
  asset: html`<rect x="6" y="0" width="8" height="7" class="is-wood" /><path d="M6 0 L14 7 M14 0 L6 7" class="is-ink" />`,
  message: html`<rect x="5" y="1" width="10" height="6" class="is-bone" /><path d="M5 1 L10 4.5 L15 1" class="is-ink" />
    <circle cx="10" cy="4.5" r="1.3" class="is-cloth" />`,
  doc: html`<rect x="6" y="0" width="8" height="7" rx="0.5" class="is-cloth" /><rect x="7" y="5.5" width="7" height="1.5" class="is-bone" />`,
  bundle: html`<circle cx="7" cy="5" r="2.5" class="is-wood-light" /><circle cx="13" cy="5" r="2.5" class="is-wood-light" />
    <circle cx="10" cy="2.5" r="2.5" class="is-wood-light" />`,
};

/** The mine cart (20 × 18): the load over an iron-banded bin on two wheels, the flag's pole at the back left. */
function MineCart({ load, state }) {
  return html`<svg class="gui-minecart" viewBox="0 0 20 18" width="20" height="18" data-load=${load} data-state=${state}>
    <ellipse cx="10" cy="17" rx="8" ry="1.2" class="gui-minecart__shadow" />
    ${state !== "moving" && state !== "back" && html`<g class="gui-minecart__flag">
      <rect x="1" y="0" width="1" height="11" class="is-pole" />
      ${state === "held" ? html`<path d="M2.5 1 H7 L5.6 3.2 L7 5.4 H2.5 L3.9 3.2 Z" class="is-held" />`
        : html`<rect x="2" y="0.5" width="6" height="4" class=${state === "ask" ? "is-ask" : "is-fire"} />`}
    </g>`}
    <g transform="translate(0 2)">${LOADS[load] || LOADS.asset}</g>
    <path d="M2 8 H18 L16.5 14 H3.5 Z" class="gui-minecart__bin" />
    <rect x="2.6" y="10" width="14.8" height="1.2" class="gui-minecart__band" />
    <circle cx="6" cy="15" r="1.8" class="gui-minecart__wheel" /><circle cx="14" cy="15" r="1.8" class="gui-minecart__wheel" />
  </svg>`;
}

/** One cart as either look draws it: Camp's mine cart, Office's gold (moving) or square (standing), the map's dot. */
function Cart({ c }) {
  return html`<${MineCart} load=${c.load || "asset"} state=${c.state || "moving"} />
    <img class="gui-cart__gold" src="/ds/sprites/icons/res-gold.png" srcset="/ds/sprites/icons/res-gold@2x.png 2x" width="8" height="8" alt="" />
    <span class="gui-cart__square"></span>`;
}

/** Where a road's carts stand: the middle of its last cell before the building, and the way they rolled in. */
function stopOf(p) {
  const cs = p.cells || [];
  if (cs.length < 2) return { x: p.entry[0], y: p.entry[1], dx: 0, dy: 0 };
  const [a, b] = [cs[cs.length - 2], cs[cs.length - 1]];
  return { x: a[0] * CELL + CELL / 2, y: a[1] * CELL + CELL / 2, dx: b[0] - a[0], dy: b[1] - a[1] };
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
        <${Cart} c=${c} />
        ${c.title && !back && named && html`<span class="gui-cart__label">${say(c.title)}</span>`}
      </div>`;
    })}
    ${Object.entries(standing).map(([road, here]) => html`<${Pile} key=${`pile-${road}`} road=${road} p=${byRoad[road]} here=${here}
      door=${asking.has((ends[road] || [])[1])} />`)}
  </div>`;
}
