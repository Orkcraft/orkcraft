// The stewards on Camp's town (design-system-v3.md §4.3, v3-prompts §5): a building that takes work from the line has
// its steward, called by its orkish name (the Taskmaster, a Grunt, the Quartermaster…), where its state says — at the
// stop looking down the line, waiting for work; lifting the load off a cart that just stopped there; inside (not seen)
// while it works, its thought bubble over the roof; at its door with ❓ when it asks the person. Orks are drawn at the
// orks' own zoom (step.o, about ×1.3 the track's), never pushing or riding a cart. The building under the mouse or selected has its steward
// out of the door instead (js/camp/steward.js).
import { html, cls } from "../html.js";
import { say } from "../link.js";
import { busy as busyOf } from "../fold.js";
import { PATH_W } from "./layout.js";
import { V3, sizeOf, orkSprite, dev } from "./sprites.js";
import { Bubble, thought } from "./steward.js";

const LIFT_S = 2.5;                        // a load lifted off and carried in

/** Where a building's steward stands, and in what pose: null when the building has none on the line. */
export function stewardAt(b, p, L, takesWork) {
  if (!p || p.wall || !takesWork) return null;
  const B = L.step.b, S = L.step.s, lineTop = p.service ? p.feet + 6 * L.step.b : p.stop.y - L.T / 2;   // a service: by its door
  if (p.depot) return { x: p.gates[0] - 18 * B, y: p.door.y - 2 * S, pose: b.alert ? "asks" : "waits" };   // by the west doors (§4d)
  if (b.alert) return { x: p.door.x + 14 * B, y: p.feet + 2 * B, pose: "asks" };
  if (busyOf(b)) return { x: p.cx, y: p.y + 10 * B, pose: "inside" };
  const side = p.spur ? p.w * 0.36 : (PATH_W / 2) * B + 18 * (L.step.o || S);   // clear of its path, at the orks' own step
  return { x: p.cx + side, y: lineTop - 2 * S, pose: "waits" };
}

function Ork({ name, file, at, S, cl = "", style = "", onClick = null }) {
  const s = sizeOf(file);
  if (!s) return null;
  const w = dev(s[0] * S), h = dev(s[1] * S);
  return html`<span class=${cls("gui-camp__ork", `is-${at.pose}${cl ? ` ${cl}` : ""}`)} title=${say(name)} aria-label=${say(name)}
      role=${onClick ? "button" : "img"} onClick=${onClick ? (e) => { e.stopPropagation(); onClick(); } : undefined}
      style=${`left:${dev(at.x - w / 2)}px;top:${dev(at.y - h)}px;width:${w}px;height:${h}px;z-index:${10 + Math.round(at.y / 8)};`
        + `background:url(${V3 + file}) 0 0 / auto ${h}px no-repeat;--w:${w}px;${style}`}></span>`;
}

/** One steward. Waiting at the stop, it lifts the load off a cart the moment one arrives (`soon`: in how many seconds
 *  each cart rolling in gets there): the waiting ork gives way to the carrying one for a moment, by CSS alone. */
function Steward({ b, at, S, soon, onOrk, onBubble }) {
  const name = b.ork_name || "";
  if (at.pose === "inside") return html`<${Bubble} x=${at.x} y=${at.y} text=${thought(b)} onClick=${onBubble ? () => onBubble(b) : null} />`;
  if (at.pose === "asks") {
    const file = sizeOf("orks/states/asks.png") ? "orks/states/asks.png" : orkSprite(name);
    return html`<${Ork} name=${name} file=${file} at=${at} S=${S} onClick=${onOrk ? () => onOrk(b) : null} />`;
  }
  const lift = (soon || []).filter((t) => t > -LIFT_S).map((t) => Math.max(t, -LIFT_S + 0.1));
  const carry = sizeOf("orks/inside/carry.png") && lift.length ? lift[0] : null;
  return html`<${Ork} name=${name} file=${orkSprite(name)} at=${at} S=${S} cl=${carry !== null ? "is-giving-way" : ""}
      style=${carry !== null ? `animation-delay:${carry}s` : ""} onClick=${onOrk ? () => onOrk(b) : null} />
    ${carry !== null && html`<${Ork} name=${name} file="orks/inside/carry.png" at=${{ ...at, pose: "lifts" }} S=${S} cl="is-lifting"
      style=${`animation-delay:${carry}s, ${carry}s`} />`}`;
}

/** The Prospector, the mine's keeper (Research, §4.11), in its own moves (o7-moves, `orks/prospector/`): digging by the
 *  shaft while Research runs; carrying a sack from the door to the stop as a result leaves (`left`: seconds since the
 *  last cart left it); else pacing its path beside the shaft. Six frames a move. Its ❓ as any steward's. */
function Prospector({ b, p, L, left, onOrk }) {
  const B = L.step.b, S = L.step.s, O = L.step.o || S, name = b.ork_name || "Prospector", click = onOrk ? () => onOrk(b) : null;
  // beside the headframe, just off its east side, on the ground before the line; drawn in front of the mine
  const shaft = { x: Math.round(p.x + p.w + 10 * S), y: Math.round(p.stop.y - L.T / 2 - 2 * S) };
  const front = `z-index:${12 + Math.round(p.feet / 8)};`;
  const move = (m) => (sizeOf(`orks/prospector/${m}.png`) ? `orks/prospector/${m}.png` : null);
  if (b.alert) return html`<${Ork} name=${name} file=${sizeOf("orks/states/asks.png") ? "orks/states/asks.png" : orkSprite(name)}
    at=${{ x: p.door.x + 14 * B, y: p.feet + 2 * B, pose: "asks" }} S=${O} onClick=${click} />`;
  const dig = busyOf(b) && move("dig"), carry = left !== null && left !== undefined && left < LIFT_S && move("carry");
  if (dig) return html`<${Ork} name=${`${name}: digging`} file=${dig} at=${{ ...shaft, pose: "digs" }} S=${O} cl="is-moving" style=${front} onClick=${click} />`;
  if (carry) {
    const dx = Math.round(p.stop.x - shaft.x);                      // from beside the shaft to its stop
    return html`<${Ork} name=${`${name}: a result leaves`} file=${carry} at=${{ ...shaft, pose: "carries" }} S=${O} cl="is-moving is-carrying"
      style=${`${front}--dx:${dx}px;--n:${Math.max(1, Math.abs(dx))};animation-delay:0s, ${-left}s`} onClick=${click} />`;
  }
  const walk = move("walk");
  return walk ? html`<${Ork} name=${name} file=${walk} at=${{ ...shaft, pose: "walks" }} S=${O} cl="is-moving is-pacing"
      style=${`${front}--dx:${Math.round(20 * S)}px;--n:${Math.round(20 * S)}`} onClick=${click} />`
    : html`<${Ork} name=${name} file=${orkSprite(name)} at=${{ ...shaft, pose: "waits" }} S=${O} style=${front} onClick=${click} />`;
}

export function Stewards({ L, buildings, roads, out = null, soon = {}, left = {}, onOrk = null, onBubble = null }) {
  const into = new Set((roads || []).map((r) => r.to));
  return html`<div class="gui-camp__layer is-orks">${buildings.map((b) => {
    if (b.id === out) return null;                          // out of its door instead (js/camp/steward.js)
    const p = L.buildings[b.id];
    if (b.type === "mine" && p && !p.wall) return html`<${Prospector} key=${b.id} b=${b} p=${p} L=${L} left=${left[b.id]} onOrk=${onOrk} />`;
    const at = stewardAt(b, L.buildings[b.id], L, into.has(b.id) || b.type === "fields");
    return at && html`<${Steward} key=${b.id} b=${b} at=${at} S=${L.step.o || L.step.s} soon=${soon[b.id]} onOrk=${onOrk} onBubble=${onBubble} />`;
  })}</div>`;
}
