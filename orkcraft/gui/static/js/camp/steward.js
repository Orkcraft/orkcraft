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
import { V3, sizeOf, orkSprite } from "./sprites.js";

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
export function Bubble({ x, y, text, onClick = null }) {
  return html`<button type="button" class=${cls("gui-camp__bubble", { "is-button": !!onClick })} style=${`left:${x}px;top:${y}px`}
      onClick=${onClick ? (e) => { e.stopPropagation(); onClick(); } : undefined} tabindex=${onClick ? 0 : -1} aria-label=${text}>
    <span class="gui-camp__bubble-box">${text}</span>
    <span class="gui-camp__bubble-dot is-1"></span><span class="gui-camp__bubble-dot is-2"></span>
  </button>`;
}

/** The steward stepping out of its door (o6-door, four frames, shown at one device pixel an art pixel where the screen
 *  is dense enough; else its role ork beside the door). */
function OutOfDoor({ b, p, S, onOrk }) {
  const click = onOrk ? (e) => { e.stopPropagation(); onOrk(b); } : undefined;
  const dense = (window.devicePixelRatio || 1) >= 2, door = sizeOf("orks/body/door.png");
  if (dense && door) {
    const k = S / 2, w = door[0] * k, h = door[1] * k;
    return html`<span class="gui-camp__door" data-id=${b.id} role="button" title=${say(`${b.ork_name}: its terminal`)} onClick=${click} style=${`left:${p.door.x - w / 2}px;top:${p.feet - h}px;width:${w}px;height:${h}px;`
      + `background-image:url(${V3}orks/body/door.png);background-size:${w * 4}px ${h}px;--w:${w}px`}></span>`;
  }
  const file = orkSprite(b.ork_name), s = sizeOf(file);
  if (!s) return null;
  const w = s[0] * S, h = s[1] * S;
  return html`<span class="gui-camp__ork is-out" role="button" title=${say(`${b.ork_name}: its terminal`)} onClick=${click} style=${`left:${p.door.x - w / 2}px;top:${p.feet - h}px;width:${w}px;height:${h}px;`
    + `background:url(${V3 + file}) 0 0 / auto ${h}px no-repeat`}></span>`;
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
  const S = L.step.s, B = L.step.b;
  const head = p.feet - 64 * S;
  return html`<div class="gui-camp__layer is-out">
    <${OutOfDoor} b=${b} p=${p} S=${S} onOrk=${onOrk} />
    ${!grown && html`<${Bubble} x=${p.door.x + 6 * B} y=${head - 4} text=${thought(b)}
      onClick=${onBubble ? () => onBubble(b) : null} />`}
    <${Scroll} b=${b} p=${p} grown=${grown} seen=${seen} />
  </div>`;
}
