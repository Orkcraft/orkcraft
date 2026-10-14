// Carts on Camp's lines (design-system-v3.md §4, town-readability.md §3): each cart the town sent lately rolls from its
// road's source's stop to its building's stop along the track (js/camp/layout.js `route`), once, in the time the road
// takes; it never leaves the lines. A cart that stopped stands at its building's stop (on the Review gate's weighbridge,
// its barrier down), its flag saying why: yellow, it waits for the person (its chip `#42 · title` always shown); ⏳,
// held; red, stuck. More than three there are a pile with a ×N chip.
import { html, cls } from "../html.js";
import { say } from "../link.js";
import { chipOf } from "../carts.js";
import { lengthOf } from "./layout.js";
import { V3, sizeOf } from "./sprites.js";
import { Badge } from "./signals.js";

const started = new Map();               // cart id → its animation-delay, fixed when first seen
const LOUD = ["ask", "stuck", "held"];   // a pile's flag: its loudest cart's
const SHOWN = 3;                         // carts drawn standing at a stop; more are a pile

function delayOf(c) {
  if (!started.has(c.id)) {
    started.set(c.id, -Math.min(c.age, 30));
    if (started.size > 400) started.delete(started.keys().next().value);
  }
  return started.get(c.id);
}

const loadOf = (c) => (["code", "asset", "message", "doc", "bundle"].includes(c.load) ? c.load : "asset");

/** A cart's sprite, its feet at (0, 0) of its box. */
function Bin({ c, B }) {
  const file = `carts/${loadOf(c)}.png`, s = sizeOf(file) || [40, 48];
  const w = s[0] * B, h = s[1] * B;
  return html`<img class="gui-camp__px" src=${V3 + file} alt="" draggable="false" style=${`left:${-w / 2}px;top:${-h}px;width:${w}px;height:${h}px`} />`;
}

/** The yellow flag of a cart waiting for the person: outlined, a darker lower band (§5). */
const Flag = ({ B }) => html`<span class="gui-camp__flag" style=${`left:${-18 * B}px;top:${-44 * B - 44}px`}></span>`;

function Rolling({ c, pts, dur, B }) {
  const d = `M ${pts.map((p) => p.join(" ")).join(" L ")}`;
  const back = pts[pts.length - 1][0] < pts[0][0];
  return html`<div class=${cls("gui-camp__cart is-rolling", { "is-west": back })} data-load=${loadOf(c)} data-road=${c.road}
      title=${say(chipOf(c))}
      style=${`offset-path:path("${d}");animation-duration:${dur}s;animation-delay:${delayOf(c)}s`}>
    <${Bin} c=${c} B=${B} />
  </div>`;
}

/** Where a building's stopped carts stand: on its weighbridge (the Review gate), else on its line at its stop, the
 *  later ones back along the line; and how far apart. */
function standOf(p, B, T) {
  if (p.type === "loot" && p.spur) return { x: p.cx, y: p.y + p.h * 0.69, dx: 0 };
  if (p.wall === "out") return { x: p.stop.x - T * 0.2, y: p.stop.y + T * 0.3, dx: -44 * B };
  return { x: p.stop.x, y: p.stop.y + T * 0.3, dx: -44 * B };
}

function Standing({ list, p, L }) {
  const B = L.step.b, at = standOf(p, B, L.T);
  const loud = LOUD.find((s) => list.some((c) => c.state === s)) || "moving";
  const lead = list.find((c) => c.state === loud) || list[0];
  const pile = list.length > SHOWN;
  const pileS = sizeOf("carts/pile.png");
  return html`<div class=${cls("gui-camp__stand", `is-${loud}`)} data-id=${p.id} style=${`left:${at.x}px;top:${at.y}px`}>
    ${pile && pileS ? html`<img class="gui-camp__px" src=${`${V3}carts/pile.png`} alt="" style=${`left:${-pileS[0] * B / 2}px;top:${-pileS[1] * B}px;width:${pileS[0] * B}px;height:${pileS[1] * B}px`} />`
      : list.slice(0, SHOWN).map((c, i) => html`<div key=${c.id} class="gui-camp__cart" data-load=${loadOf(c)} style=${`left:${i * at.dx}px;top:0`}><${Bin} c=${c} B=${B} /></div>`)}
    ${loud === "ask" && html`<${Flag} B=${B} />`}
    ${(loud === "held" || loud === "stuck") && html`<${Badge} kind=${loud === "held" ? "held" : "fire"} x=${0} y=${-56 * B - 36}
      title=${say(loud === "held" ? "Held: waits for a limit to reset" : "Stuck on an error")} />`}
    ${(loud === "ask" || pile) && html`<span class="gui-camp__chip is-cart">${[pile ? `×${list.length}` : "", loud === "ask" ? chipOf(lead) : ""].filter(Boolean).join(" · ")}</span>`}
  </div>`;
}

/** How long a cart takes along its route: the road's own time, else by its length (2–9 s). */
export function tripOf(L, pts, travel = 0) {
  return Math.max(travel || 0, Math.min(Math.max(lengthOf(pts) / (140 * L.step.b), 2), 9));
}

/** The carts rolling into each building now, and in how many seconds each arrives: building id → [seconds]. */
export function arriving(L, roads, carts = [], travel = 0) {
  const byId = Object.fromEntries(roads.map((r) => [r.id, r])), out = {};
  for (const c of carts) {
    const r = byId[c.road];
    if (!r || c.stands || c.state === "back") continue;
    const pts = L.route(r.from, r.to);
    if (!pts || pts.length < 2) continue;
    const at = tripOf(L, pts, travel) - c.age;
    if (at > -2.5) (out[r.to] = out[r.to] || []).push(at);
  }
  return out;
}

export function CampCarts({ L, roads, carts = [], travel = 0 }) {
  const B = L.step.b;
  const byId = Object.fromEntries(roads.map((r) => [r.id, r]));
  const rolling = [], standing = new Map();
  for (const c of carts) {
    const r = byId[c.road];
    if (!r) continue;
    if (c.stands) {
      const p = L.buildings[r.to];
      if (!p) continue;
      if (!standing.has(r.to)) standing.set(r.to, []);
      standing.get(r.to).push(c);
      continue;
    }
    if (c.state === "back") continue;                  // filtered: it never left its source
    const pts = L.route(r.from, r.to);
    if (!pts || pts.length < 2) continue;
    const feet = L.T * 0.3;
    const dur = tripOf(L, pts, travel);
    if (c.age > dur + 0.5) continue;
    rolling.push({ c, pts: pts.map(([x, y]) => [Math.round(x), Math.round(y + feet)]), dur });
  }
  return html`<div class="gui-camp__layer is-carts">
    ${rolling.map(({ c, pts, dur }) => html`<${Rolling} key=${c.id} c=${c} pts=${pts} dur=${dur} B=${B} />`)}
    ${[...standing].map(([id, list]) => html`<${Standing} key=${id} list=${list} p=${L.buildings[id]} L=${L} />`)}
  </div>`;
}
