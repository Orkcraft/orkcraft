// A building's steward and its scroll (decisions-2026-10.md §13.1, v3-prompts §5–§7): the mouse on a building brings
// its steward out of the door, a thought bubble over its head (what it does, in two or three words), and a small scroll
// over the building with its status in one or two lines; a click grows the scroll (its status, Enter, Answer when it
// asks) while the building's quick actions stand in the bottom bar, its command card (js/warchief.js), never twice; a
// second click enters the building (for now its window or its large card: A5, until I2). On a touch
// screen the first tap is the mouse and the click at once. The steward is called by its orkish name (`ork_name`).
import { signal } from "@preact/signals";
import { html, cls } from "../html.js";
import { say } from "../link.js";
import { typeModule } from "../types.js";
import { busy as busyOf } from "../fold.js";
import { brokenOf } from "../hut.js";
import { openBuilding } from "../windows.js";
import { openOrders } from "../orders.js";
import { V3, sizeOf, orkSprite, doorwayOf } from "./sprites.js";

export const hovered = signal(null);       // the building under the mouse
const WORDS = 3;

const cut = (s, n = WORDS) => {
  const w = String(s || "").replace(/\s+/g, " ").trim().split(" ");
  return w.length > n ? `${w.slice(0, n).join(" ")}…` : w.join(" ");
};

/** What the steward thinks: its task in two or three words, or what it waits for. */
export function thought(b) {
  if (b.alert) return say(`Asks: ${cut(b.alert.title)}`);
  if (b.signal) return say(b.signal.kind === "held" ? "Held for a limit" : "Stopped on an error");
  if (b.paused) return say("Paused");
  if (busyOf(b)) return say(b.status_plain[0] ? `At work: ${cut(b.status_plain[0])}` : "At work");
  return say(b.yard ? "Waits for its carts" : "Waiting for a cart");
}

/** The building's status in one or two lines: what it asks, what its card says first, its own status line. */
export function statusLines(b) {
  const mod = b.page ? typeModule(b.type) : null;
  const mark = mod && mod.mark ? mod.mark(b) : null;
  const broken = brokenOf(b);
  const lines = [
    b.alert && `❓ ${b.alert.title}`,
    broken && `! ${broken}`,
    b.signal && b.signal.line,
    b.paused && "Paused: takes no work until resumed",
    mark && mark.text && String(mark.text),
    ...(b.status_plain || []),
  ].filter(Boolean).map((x) => say(String(x)));
  const out = [...new Set(lines)].slice(0, 2);
  return out.length ? out : [say(busyOf(b) ? "At work" : "Quiet")];
}

/** The thought bubble: u1's nine pieces round 2–3 words, its two dots trailing to the head under it. */
export function Bubble({ x, y, text, onClick = null, through = false }) {
  // `through`: the hover's bubble lets the mouse through to the building under it (a click on the building selects it)
  return html`<button type="button" class=${cls("gui-camp__bubble", { "is-button": !!onClick && !through })}
      style=${`left:${x}px;top:${y}px${through ? ";pointer-events:none" : ""}`}
      onClick=${onClick ? (e) => { e.stopPropagation(); onClick(); } : undefined} tabindex=${onClick ? 0 : -1} aria-label=${text}>
    <span class="gui-camp__bubble-box">${text}</span>
    <span class="gui-camp__bubble-dot is-1"></span><span class="gui-camp__bubble-dot is-2"></span>
  </button>`;
}

/** The steward stepping out of its building (the PM, 15 October: no drawn door leaf). With a doorway (tools/doorways.py)
 *  it steps out of that dark opening, seen only inside it and below its sill, so it appears from the real door; with
 *  none it walks out from behind the building's foot. */
function OutOfDoor({ b, p, S, O = S, B, onOrk }) {
  const click = onOrk ? (e) => { e.stopPropagation(); onOrk(b); } : undefined;
  const file = orkSprite(b.ork_name), s = sizeOf(file);
  if (!s) return null;
  const w = s[0] * O, h = s[1] * O, d = p.file ? doorwayOf(p.file) : null;
  // the opening in world px; without one, a slot at the building's foot (nothing of the ork shows above it)
  const R = d ? { x: p.x + d[0] * B, y: p.y + d[1] * B, w: d[2] * B, h: d[3] * B } : { x: p.door.x - w / 2, y: p.feet, w, h: 0 };
  const side = w, W = R.w + 2 * side, H = h + R.h + 24 * O, sill = h + R.h;
  const clip = `polygon(${side}px ${h}px, ${side + R.w}px ${h}px, ${side + R.w}px ${sill}px, ${W}px ${sill}px, ${W}px ${H}px, 0 ${H}px, 0 ${sill}px, ${side}px ${sill}px)`;
  return html`<span class="gui-camp__exit" role="button" title=${say(`${b.ork_name}: its terminal`)} onClick=${click}
      style=${`left:${Math.round(R.x - side)}px;top:${Math.round(R.y - h)}px;width:${Math.round(W)}px;height:${Math.round(H)}px;clip-path:${clip}`}>
    <span class=${cls("gui-camp__ork is-out", { "is-behind": !d })} style=${`left:${Math.round(side + R.w / 2 - w / 2)}px;top:${Math.round(sill - h)}px;`
      + `width:${w}px;height:${h}px;--out:${Math.round((d ? 14 : 18) * O + (d ? 0 : h * 0.6))}px;background:url(${V3 + file}) 0 0 / auto ${h}px no-repeat`}></span>
  </span>`;
}

/** The scroll over a building: small on the mouse, grown with the quick actions when it is selected. */
function Scroll({ b, p, grown, seen }) {
  const lines = statusLines(b);
  const banner = sizeOf("ui/scroll/banner.png");
  // over the building, its whole height inside the part of the window seen (its foot lower when the roof is near the top)
  const tall = 84 + (grown ? 24 * lines.length + 92 : 0);
  const top = Math.max(p.y - 8, seen.top + tall);
  const x = Math.min(Math.max(p.cx, seen.left + 244), seen.right - 244);
  return html`<div class=${cls("gui-camp__scroll", { "is-grown": grown })} data-id=${b.id} style=${`left:${x}px;top:${top}px`}
      onClick=${(e) => e.stopPropagation()} onPointerDown=${(e) => grown && e.stopPropagation()}>
    <div class="gui-camp__scroll-head" style=${banner ? `background-image:url(${V3}ui/scroll/banner.png)` : ""}>
      <b class="gui-camp__scroll-title">${say(b.title)}</b>
      ${!grown && html`<span class="gui-camp__scroll-line">${lines[0]}</span>`}
    </div>
    ${grown && html`<div class="gui-camp__scroll-body">
      ${lines.map((l, i) => html`<p key=${i} class="gui-camp__scroll-line">${l}</p>`)}
      <p class="gui-camp__scroll-who">${say(`${b.ork_name || "Steward"}: ${thought(b)}`)}</p>
      <div class="gui-camp__scroll-acts" role="group" aria-label=${say(`${b.title}: enter`)}>
        ${b.alert && html`<button type="button" class="ok-btn primary" onClick=${() => openOrders(b.alert.id)}>${say("Answer")}</button>`}
        <button type="button" class=${cls("ok-btn", { primary: !b.alert })} onClick=${() => openBuilding(b.id)}>${say("Enter")}</button>
      </div>
    </div>`}
  </div>`;
}

/** The steward out, its bubble, and the scroll, for the building under the mouse or the selected one. `seen`: the part
 *  of the world in the window, {left, top, right} in its own px. */
export function StewardOut({ b, p, L, grown, seen, onOrk = null, onBubble = null }) {
  const S = L.step.s, O = L.step.o || S, B = L.step.b;
  const ork = sizeOf(orkSprite(b.ork_name)), head = p.feet - ((ork ? ork[1] : 38) + 6) * O;   // over its head, whatever its size
  // the mouse on the steward out of its door, its bubble or its scroll still means its building: hovered stays, no flicker
  const keep = (e) => { if (e.pointerType === "mouse" && hovered.value !== b.id && !grown) hovered.value = b.id; };
  const gone = () => { if (hovered.value === b.id && !grown) hovered.value = null; };
  return html`<div class="gui-camp__layer is-out" onPointerOver=${keep} onPointerLeave=${gone}>
    <${OutOfDoor} b=${b} p=${p} S=${S} O=${O} B=${B} onOrk=${onOrk} />
    ${!grown && html`<${Bubble} x=${p.door.x + 6 * B} y=${head - 4} text=${thought(b)} through=${true}
      onClick=${onBubble ? () => onBubble(b) : null} />`}
    <${Scroll} b=${b} p=${p} grown=${grown} seen=${seen} />
  </div>`;
}
