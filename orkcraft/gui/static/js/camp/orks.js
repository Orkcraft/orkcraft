// The stewards on Camp's town (design-system-v3.md §4.3, v3-prompts §5): a building that takes work from the line has
// its steward, called by its orkish name (the Taskmaster, a Grunt, the Quartermaster…), where its state says — at the
// stop looking down the line, waiting for work; lifting the load off a cart that just stopped there; inside (not seen)
// while it works, its thought bubble over the roof; at its door with ❓ when it asks the person. Orks are drawn at the
// small layer's zoom (step.s), never pushing or riding a cart. The building under the mouse or selected has its steward
// out of the door instead (js/camp/steward.js).
import { html, cls } from "../html.js";
import { say } from "../link.js";
import { busy as busyOf } from "../fold.js";
import { PATH_W } from "./layout.js";
import { V3, sizeOf, orkSprite } from "./sprites.js";
import { Bubble, thought } from "./steward.js";

const LIFT_S = 2.5;                        // a load lifted off and carried in

/** Where a building's steward stands, and in what pose: null when the building has none on the line. */
export function stewardAt(b, p, L, takesWork) {
  if (!p || p.wall || !takesWork) return null;
  const B = L.step.b, S = L.step.s, lineTop = p.stop.y - L.T / 2;
  if (b.alert) return { x: p.door.x + 14 * B, y: p.feet + 2 * B, pose: "asks" };
  if (busyOf(b)) return { x: p.cx, y: p.y + 10 * B, pose: "inside" };
  const side = p.spur ? p.w * 0.36 : (PATH_W / 2) * B + 14 * S;
  return { x: p.cx + side, y: lineTop - 2 * S, pose: "waits" };
}

function Ork({ name, file, at, S, cl = "", style = "", onClick = null }) {
  const s = sizeOf(file);
  if (!s) return null;
  const w = s[0] * S, h = s[1] * S;
  return html`<span class=${cls("gui-camp__ork", `is-${at.pose}`, cl)} title=${say(name)} aria-label=${say(name)}
      role=${onClick ? "button" : "img"} onClick=${onClick ? (e) => { e.stopPropagation(); onClick(); } : undefined}
      style=${`left:${at.x - w / 2}px;top:${at.y - h}px;width:${w}px;height:${h}px;z-index:${10 + Math.round(at.y / 8)};`
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

export function Stewards({ L, buildings, roads, out = null, soon = {}, onOrk = null, onBubble = null }) {
  const into = new Set((roads || []).map((r) => r.to));
  return html`<div class="gui-camp__layer is-orks">${buildings.map((b) => {
    if (b.id === out) return null;                          // out of its door instead (js/camp/steward.js)
    const at = stewardAt(b, L.buildings[b.id], L, into.has(b.id) || b.type === "fields");
    return at && html`<${Steward} key=${b.id} b=${b} at=${at} S=${L.step.s} soon=${soon[b.id]} onOrk=${onOrk} onBubble=${onBubble} />`;
  })}</div>`;
}
