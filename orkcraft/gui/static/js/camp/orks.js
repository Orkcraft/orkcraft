// The stewards on Camp's town (design-system-v3.md §4.3, v3-prompts §5): a building that takes work from the line has
// its steward, called by its orkish name (the Taskmaster, a Grunt, the Quartermaster…), where its state says — at the
// stop looking down the line, waiting for work; inside (not seen) while it works; at its door with ❓ when it asks the
// person. Orks are drawn at the small layer's zoom (step.s), never pushing or riding a cart.
import { html, cls } from "../html.js";
import { say } from "../link.js";
import { busy as busyOf } from "../fold.js";
import { PATH_W } from "./layout.js";
import { V3, sizeOf, orkSprite } from "./sprites.js";

/** Where a building's steward stands, and in what pose: null when it is inside or the building has none on the line. */
export function stewardAt(b, p, L, takesWork) {
  if (!p || p.wall || !takesWork) return null;
  const B = L.step.b, S = L.step.s, lineTop = p.stop.y - L.T / 2;
  if (b.alert) return { x: p.door.x + 14 * B, y: p.feet + 2 * B, pose: "asks" };
  if (busyOf(b)) return null;                               // inside, at work
  const side = p.spur ? p.w * 0.36 : (PATH_W / 2) * B + 14 * S;
  return { x: p.cx + side, y: lineTop - 2 * S, pose: "waits" };
}

function Ork({ name, at, S }) {
  const file = at.pose === "asks" && sizeOf("orks/states/asks.png") ? "orks/states/asks.png" : orkSprite(name);
  const s = sizeOf(file);
  if (!s) return null;
  const strip = file.startsWith("orks/body/");               // a strip of frames: the first one
  const w = s[0] * S, h = s[1] * S;
  return html`<span class=${cls("gui-camp__ork", `is-${at.pose}`)} title=${say(name)} aria-label=${say(name)}
      style=${`left:${at.x - w / 2}px;top:${at.y - h}px;width:${w}px;height:${h}px;z-index:${10 + Math.round(at.y / 8)};`
        + `background:url(${V3 + file}) 0 0 / ${strip ? "auto" : `${w}px`} ${h}px no-repeat`}></span>`;
}

export function Stewards({ L, buildings, roads }) {
  const into = new Set((roads || []).map((r) => r.to));
  return html`<div class="gui-camp__layer is-orks">${buildings.map((b) => {
    const at = stewardAt(b, L.buildings[b.id], L, into.has(b.id) || b.type === "fields");
    return at && html`<${Ork} key=${b.id} name=${b.ork_name || ""} at=${at} S=${L.step.s} />`;
  })}</div>`;
}
