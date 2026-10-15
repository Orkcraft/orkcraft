// Carts on Camp's lines (design-system-v3.md §4, town-readability.md §3): each cart the town sent lately rolls from its
// road's source's stop to its building's stop along the track (js/camp/layout.js `route`), once, in the time the road
// takes; it never leaves the lines. A cart that stopped stands at its building's stop (on the Review gate's weighbridge,
// its barrier down), its flag saying why: yellow, it waits for the person (its chip `#42 · title` always shown); ⏳,
// held; red, stuck. More than three there are a pile with a ×N chip.
import { useEffect, useRef } from "preact/hooks";
import { html, cls } from "../html.js";
import { say } from "../link.js";
import { chipOf } from "../carts.js";
import { lengthOf } from "./layout.js";
import { pointAt, aheadOn, step, thrown } from "./traffic.js";
import { V3, sizeOf } from "./sprites.js";
import { Badge } from "./signals.js";
import { waybillOf, tokensWord } from "./waybill.js";

const LOUD = ["ask", "stuck", "held"];   // a pile's flag: its loudest cart's
const SHOWN = 3;                         // carts drawn standing at a stop; more are a pile

const launched = new Map();              // cart id → its launch's delay, fixed when first seen (as `started`)
function launchAt(c, dur) {
  if (!launched.has(c.id)) {
    launched.set(c.id, (dur - c.age).toFixed(2));
    if (launched.size > 200) launched.delete(launched.keys().next().value);
  }
  return launched.get(c.id);
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

// The rolling carts, moved each frame by the traffic (js/camp/traffic.js): id → { el, pts, len, v, s, rank, parks,
// throws, done }; the switches' stands by index. One loop for the town, running while a cart rolls.
const moving = new Map();
let stands = [], raf = 0, last = 0, keep = { gap: 64, eps: 16, T: 64 };
const GONE_S = 1.2;                       // an arrived cart stays this long at its stop, then the stop's own drawing

function place(c) {
  if (!c.el) return;
  const p = pointAt(c.pts, c.s);
  c.el.style.transform = `translate(${Math.round(p.x)}px,${Math.round(p.y)}px)`;
  c.el.classList.toggle("is-west", p.face < 0);
  c.el.classList.toggle("is-gone", c.done !== null && c.done > GONE_S);
}

function frame(now) {
  const dt = Math.min(0.1, (now - (last || now)) / 1000);
  last = now;
  const live = [...moving.values()].filter((c) => c.done === null || c.done <= GONE_S);
  const held = step(live, dt, keep.gap, keep.eps);
  for (const c of live) {
    if (c.s >= c.len) c.done = (c.done || 0) + dt;
    if (c.el) c.el.classList.toggle("is-waiting", !!held[c.id]);
    place(c);
  }
  const on = thrown(stands.length, live, keep.T * 2.5, keep.T * 0.5);
  stands.forEach((el, i) => { if (el) el.dataset.thrown = on[i] ? "1" : ""; });
  raf = live.length || stands.some((el) => el && el.dataset.thrown) ? requestAnimationFrame(frame) : 0;
  if (!raf) last = 0;
}
const wake = () => { if (!raf && typeof requestAnimationFrame === "function") raf = requestAnimationFrame(frame); };

/** A switch stand beside the track (§4c rule 6): its lever and target arm say the way it is set, by position
 *  (c3's `track/switch-0.png` still, `switch-1.png` thrown). */
export function Switches({ L }) {
  const S = L.step.s, T = L.T;
  stands = stands.slice(0, L.switches.length);
  // drawn at twice the track's zoom (32 × 48 at the default), so the arm's position reads from across the camp
  const K = 2 * S;
  const at = (w) => ({ n: [T * 0.8, 6 * S], s: [T * 0.2, T + 16 * S], w: [-12 * S, T * 0.95], e: [T + 12 * S, T * 0.95] }[w]);
  return html`<div class="gui-camp__layer is-switches">${L.switches.map((w, i) => {
    const [dx, dy] = at(w.side), s = (sizeOf("track/switch-0.png") || [16, 24]).map((v) => v * K / S);
    return html`<div key=${`${w.x},${w.y}`} class="gui-camp__switch" data-i=${i} data-ret=${w.ret ? "1" : ""}
        ref=${(el) => { stands[i] = el; }} title=${say(w.ret ? "Switch: on to the buffer stop, or round again" : "Switch")}
        style=${`left:${Math.round(w.x + dx - (s[0] * S) / 2)}px;top:${Math.round(w.y + dy - s[1] * S)}px;width:${s[0] * S}px;height:${s[1] * S}px`}>
      <img class="gui-camp__px is-still" src=${`${V3}track/switch-0.png`} alt="" draggable="false" />
      <img class="gui-camp__px is-thrown" src=${`${V3}track/switch-1.png`} alt="" draggable="false" />
    </div>`;
  })}</div>`;
}

function Rolling({ c, way, B }) {
  const ref = useRef(null);
  const m = moving.get(c.id);
  useEffect(() => {
    const e = moving.get(c.id);
    if (e) { e.el = ref.current; place(e); wake(); }
    return () => { const x = moving.get(c.id); if (x && x.el === ref.current) x.el = null; };
  }, [c.id]);
  const p = m ? pointAt(m.pts, m.s) : { x: way.pts[0][0], y: way.pts[0][1], face: 1 };
  return html`<div ref=${ref} class=${cls("gui-camp__cart is-driven", { "is-west": p.face < 0, "is-back": !!c.back })} data-load=${loadOf(c)}
      data-road=${c.road} data-id=${c.id}
      title=${say(c.back ? `${chipOf(c)} · sent back: ${roundWord(c)}` : chipOf(c))} role="button" aria-label=${say(`${chipOf(c)}: its history`)}
      onClick=${(e) => { e.stopPropagation(); waybillOf.value = { cart: c.id }; }}
      style=${`transform:translate(${Math.round(p.x)}px,${Math.round(p.y)}px)`}>
    <${Bin} c=${c} B=${B} />
    ${c.back && html`<span class="gui-camp__launch-chip is-round" style=${`top:${-48 * B - 30}px`}>${roundWord(c)}</span>`}
  </div>`;
}

/** A cart going round again wears its round and what the round before cost (§4c rule 8): `round 2 · 🪵 18k`, `$` on an
 *  API key; only what was recorded. */
export function roundWord(c) {
  const t = tokensWord(c.round_tokens), m = c.round_cost === null || c.round_cost === undefined ? "" : `$${Number(c.round_cost).toFixed(2)}`;
  return [`round ${c.round || 2}`, t ? `🪵 ${t}` : "", m].filter(Boolean).join(" · ");
}

/** Where a building's stopped carts stand, never on the main line (§4c rule 7): in its pocket, close together (more
 *  than three are the pile there), or with no pocket (layout.js POCKET "none") on its path's end just off the line; on its weighbridge (the Review gate) or its shaft (the mine); at the buffer stop.
 *  And how far apart. */
function standOf(p, B, T) {
  if (p.type === "loot" && p.spur) return { x: p.cx, y: p.y + p.h * 0.69, dx: 0 };
  if (p.depot) return { x: p.bays[0], y: p.rail + T * 0.3, dx: p.bays[1] - p.bays[0] };          // in its bays
  if (p.spur) return { x: p.cx, y: p.feet - T * 0.45, dx: 0 };
  if (p.wall === "out") return { x: p.stop.x - T * 0.2, y: p.stop.y + T * 0.3, dx: -44 * B };
  if (!p.pocket && p.waitAt) return { x: p.waitAt.x, y: p.waitAt.y - 2 * B, dx: -12 * B };   // on its path's end
  return { x: p.stop.x, y: p.stop.y + T * 0.3, dx: -12 * B };
}

function Standing({ list, p, L }) {
  const B = L.step.b, at = standOf(p, B, L.T);
  const loud = LOUD.find((s) => list.some((c) => c.state === s)) || "moving";
  const lead = list.find((c) => c.state === loud) || list[0];
  const pile = list.length > SHOWN;
  const pileS = sizeOf("carts/pile.png");
  // on the Review gate's weighbridge it stands in front of the gate's own sprite (a building's z: 10 + its feet / 8)
  const z = p.type === "loot" && p.spur ? `;z-index:${12 + Math.round(p.feet / 8)}` : "";
  return html`<div class=${cls("gui-camp__stand", `is-${loud}`)} data-id=${p.id} style=${`left:${at.x}px;top:${at.y}px${z}`}>
    ${pile && pileS ? html`<img class="gui-camp__px" src=${`${V3}carts/pile.png`} alt="" style=${`left:${-pileS[0] * B / 2}px;top:${-pileS[1] * B}px;width:${pileS[0] * B}px;height:${pileS[1] * B}px`} />`
      : list.slice(0, SHOWN).map((c, i) => html`<div key=${c.id} class="gui-camp__cart" data-load=${loadOf(c)} style=${`left:${i * at.dx}px;top:0;z-index:${SHOWN - i}`}
          role="button" title=${say(chipOf(c))} aria-label=${say(`${chipOf(c)}: its history`)}
          onClick=${(e) => { e.stopPropagation(); waybillOf.value = { cart: c.id }; }}><${Bin} c=${c} B=${B} /></div>`)}
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
    const r = roadOf(byId, c);
    if (!r || c.stands || c.state === "back") continue;
    const pts = L.route(r.from, r.to);
    if (!pts || pts.length < 2) continue;
    const at = tripOf(L, pts, travel) - c.age;
    if (at > -2.5) (out[r.to] = out[r.to] || []).push(at);
  }
  return out;
}

/** A cart the catapult launches flies over the wall with its cost (the-score.md, v3-prompts §13.4): only what was
 *  recorded — its wood, and its $ where its AI tool bills by an API key (its share of the window is not measured yet:
 *  Later); green when the cart cost less than the town's average per result (`avg`). It leaves the moment the cart
 *  reaches the buffer stop. With nothing recorded it flies with no chip. */
function Launch({ c, p, at, avg, B }) {
  const t = c.tokens, lean = t !== null && t !== undefined && avg !== null && avg !== undefined && t < avg;
  const has = t !== null && t !== undefined, money = c.cost !== null && c.cost !== undefined;
  const word = [has ? `🪵 ${tokensWord(t)}` : "", money ? `$${Number(c.cost).toFixed(2)}` : ""].filter(Boolean).join(" · ");
  const title = say(`${chipOf(c)} · ${has ? `${tokensWord(t)} tokens` : "its tokens were not recorded"}`
    + (avg ? ` · the town's average per result is ${tokensWord(Math.round(avg))}` : "") + " · its share of the window is not measured yet");
  return html`<div class=${cls("gui-camp__launch", { "is-lean": lean })} title=${title} aria-label=${title}
      style=${`left:${p.x + p.w * 0.3}px;top:${p.y + p.h * 0.15}px;animation-delay:${at}s;--fly-x:${260 * B}px;--fly-y:${-170 * B}px`}>
    <img class="gui-camp__px" src=${`${V3}carts/${loadOf(c)}.png`} alt="" style=${`left:-${20 * B}px;top:-${24 * B}px;width:${40 * B}px;height:${48 * B}px`} />
    ${word && html`<span class="gui-camp__launch-chip">${word}</span>`}
  </div>`;
}

/** A cart for the depot (§4d) rolls in at its west gateway to its first free bay and stops there, on the through track
 *  (a cart behind it waits, §4c rule 7); with every bay busy it stops on the line before the west gateway. */
export function intoDepot(pts, p, busy, B) {
  const last = pts[pts.length - 1], y = last[1];
  const x = busy < p.bays.length ? p.bays[busy] : p.gates[0] - Math.round(36 * B);
  const out = pts.slice(0, -1);
  while (out.length > 1 && out[out.length - 1][1] === y && out[out.length - 1][0] > x) out.pop();
  return [...out, [x, y]];
}

/** Where a cart first seen starts: at its share of the way, but never within a cart's distance of one already on it
 *  (two sent at once would otherwise stand on one another): back behind it, never before its start. */
function behind(m, k) {
  let s = m.s;
  for (const o of moving.values()) {
    if (o === m || !o.pts) continue;
    const p = pointAt(o.pts, o.s), d = aheadOn(m.pts, 0, p.x, p.y, k.eps);
    if (d !== Infinity && Math.abs(d - s) < k.gap) s = Math.max(0, d - k.gap);
  }
  return s;
}

/** A cart's road: its own, or for a cart handed straight back (a rework, `back`) its two ends: it goes round again. */
export const roadOf = (byId, c) => byId[c.road] || (c.back && c.from && c.to ? { id: c.road, from: c.from, to: c.to } : null);

export function CampCarts({ L, roads, carts = [], travel = 0, avg = null, bays = {} }) {
  const B = L.step.b, T = L.T;
  keep = { gap: 88 * B, eps: T * 0.25, T };              // a cart apart: one cart's length between two
  const byId = Object.fromEntries(roads.map((r) => [r.id, r]));
  const rolling = [], standing = new Map(), seen = new Set();
  const now = (typeof performance !== "undefined" ? performance.now() : Date.now()) / 1000;
  for (const c of carts) {
    const r = roadOf(byId, c);
    if (!r) continue;
    if (c.stands) {
      const p = L.buildings[r.to];
      if (!p || p.service) continue;                    // a service is consulted: no track, no cart stands there
      if (!standing.has(r.to)) standing.set(r.to, []);
      standing.get(r.to).push(c);
      continue;
    }
    if (c.state === "back") continue;                  // filtered: it never left its source
    const way = L.route(r.from, r.to);
    if (!way || way.length < 2) continue;
    const feet = T * 0.3, to = L.buildings[r.to];
    let pts = way.map(([x, y]) => [Math.round(x), Math.round(y + feet)]);
    if (to.depot) pts = intoDepot(pts, to, bays[r.to] || 0, L.step.b);
    const dur = tripOf(L, pts, travel), len = lengthOf(pts);
    let m = moving.get(c.id);
    if (!m && c.age > dur + 2.5) continue;               // gone before it was seen (a launched one has flown by then)
    if (!m) {
      m = { id: c.id, el: null, s: Math.min(1, Math.max(0, c.age / dur)) * len, rank: now - c.age, done: null, L: null };
      moving.set(c.id, m);
    } else if (m.L !== L) m.s = (m.s / (m.len || 1)) * len;   // the zoom changed: the same share of the way
    const fresh = m.L === null;
    Object.assign(m, { pts, len, v: len / dur, L, parks: !!(to.pocket || to.depot), throws: way.throws || [] });
    if (fresh) m.s = behind(m, keep);
    if (m.done !== null && m.done > GONE_S + 1.5) continue;
    seen.add(c.id);
    rolling.push({ c, way: m, dur, out: L.buildings[r.to].wall === "out" ? r.to : "" });
  }
  for (const id of [...moving.keys()]) if (!seen.has(id)) moving.delete(id);
  wake();
  return html`<div class="gui-camp__layer is-carts">
    ${rolling.map(({ c, way }) => html`<${Rolling} key=${c.id} c=${c} way=${way} B=${B} />`)}
    ${rolling.filter((x) => x.out).map(({ c, dur, out }) => html`<${Launch} key=${`fly-${c.id}`} c=${c} p=${L.buildings[out]}
      at=${launchAt(c, dur)} avg=${avg} B=${B} />`)}
    ${[...standing].map(([id, list]) => html`<${Standing} key=${id} list=${list} p=${L.buildings[id]} L=${L} />`)}
  </div>`;
}

const finaleAt = new Map();              // a finale's id → its animation-delay, fixed when first seen (as `started`)

/** Mission 1's finale (first-mission.md §9.2): the drill cart the person passed rolls off the Review gate's weighbridge
 *  along the line, "Drill · free" above it where a launched cart shows its cost; the Publisher launches it if the town
 *  has one, else it leaves along the line at its buffer stop. Drawn only: a drill goes on no road, nothing leaves. */
export function Finale({ L, f }) {
  const B = L.step.b, g = L.buildings[f.gate], out = f.out && L.buildings[f.out];
  const way = g && (out ? L.route(f.gate, f.out) : L.routeOut(f.gate));
  if (!way || way.length < 1) return null;
  const feet = L.T * 0.3;
  const pts = [[g.cx, Math.round(g.y + g.h * 0.69 - feet)], ...way].map(([x, y]) => [Math.round(x), Math.round(y + feet)]);
  const dur = tripOf(L, pts);
  if (!finaleAt.has(f.id)) finaleAt.set(f.id, -Math.min(f.age || 0, 30));
  const delay = finaleAt.get(f.id);
  const d = `M ${pts.map((p) => p.join(" ")).join(" L ")}`;
  const title = say(`${f.chip}: a drill, nothing left the town`);
  return html`<div class="gui-camp__finale" data-out=${out ? "publisher" : "line"}>
    <div class="gui-camp__cart is-rolling is-drill" title=${title} aria-label=${title}
        style=${`offset-path:path("${d}");animation-duration:${dur}s;animation-delay:${delay}s`}>
      <${Bin} c=${{ load: "doc" }} B=${B} />
      <span class="gui-camp__launch-chip is-drill" style=${`top:${-48 * B - 30}px`}>${say(f.chip)}</span>
    </div>
    ${out && html`<div class="gui-camp__launch is-drill" style=${`left:${out.x + out.w * 0.3}px;top:${out.y + out.h * 0.15}px;`
      + `animation-delay:${(dur + delay).toFixed(2)}s;--fly-x:${260 * B}px;--fly-y:${-170 * B}px`}>
      <img class="gui-camp__px" src=${`${V3}carts/doc.png`} alt="" style=${`left:-${20 * B}px;top:-${24 * B}px;width:${40 * B}px;height:${48 * B}px`} />
      <span class="gui-camp__launch-chip">${say(f.chip)}</span>
    </div>`}
  </div>`;
}
