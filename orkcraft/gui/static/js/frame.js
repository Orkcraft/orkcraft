// A frame round several buildings, as a strategy game selects its units (docs/design/improve-buildings.md §5.1): a
// Test bench's setup asks for one, the person drags it on the map, the buildings it touches are picked. And what a
// Test bench tests, framed on the map with the environment its runs stand in, as scaffolding is drawn.
import { signal } from "@preact/signals";
import { useEffect } from "preact/hooks";
import { html } from "./html.js";
import { say } from "./link.js";

export const framing = signal(null);   // {by: the Test bench's id, rect: the frame being dragged, ids: what it picked}
const PAD = 14;                        // px round the buildings a scheme's frame keeps clear

const touches = (a, r) => a.x < r.x + r.w && a.x + a.w > r.x && a.y < r.y + r.h && a.y + a.h > r.y;

/** Over the map while a setup asks for a frame: a drag draws it, letting go picks what it touches; Esc lets it go. */
export function FrameSelect({ rects }) {
  const f = framing.value;
  useEffect(() => {
    if (!f) return undefined;
    const key = (e) => { if (e.key === "Escape") framing.value = null; };
    window.addEventListener("keydown", key);
    return () => window.removeEventListener("keydown", key);
  }, [!!f]);
  if (!f) return null;
  const down = (e) => {
    if (e.button !== 0) return;
    e.preventDefault();
    e.stopPropagation();
    const box = e.currentTarget.getBoundingClientRect();
    const at = (ev) => ({ x: ev.clientX - box.left, y: ev.clientY - box.top });
    const start = at(e);
    const rectOf = (p) => ({ x: Math.min(start.x, p.x), y: Math.min(start.y, p.y), w: Math.abs(p.x - start.x), h: Math.abs(p.y - start.y) });
    const move = (ev) => { framing.value = { ...framing.value, rect: rectOf(at(ev)) }; };
    const up = (ev) => {
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerup", up);
      const r = rectOf(at(ev));
      const ids = Object.keys(rects).filter((id) => id !== framing.value.by && touches(rects[id], r));
      framing.value = { ...framing.value, rect: null, ids };
    };
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", up);
  };
  return html`<div class="gui-frame-select" onPointerDown=${down} onClick=${(e) => e.stopPropagation()}
      aria-label=${say("Drag a frame round the buildings to test")}>
    ${f.rect && html`<div class="gui-frame-select__rect" style=${`left:${f.rect.x}px;top:${f.rect.y}px;width:${f.rect.w}px;height:${f.rect.h}px`}></div>`}
    ${(f.ids || []).filter((id) => rects[id]).map((id) => html`<div key=${id} class="gui-frame-select__picked"
        style=${`left:${rects[id].x - 4}px;top:${rects[id].y - 4}px;width:${rects[id].w + 8}px;height:${rects[id].h + 8}px`}></div>`)}
  </div>`;
}

/** What each Test bench tests, framed round its buildings, the environment's name on the frame. */
export function Schemes({ buildings, rects }) {
  return html`${buildings.filter((b) => b.card && b.card.scheme).map((b) => {
    const ids = b.card.scheme.ids.filter((id) => rects[id]);
    if (!ids.length) return null;
    const x = Math.min(...ids.map((id) => rects[id].x)) - PAD, y = Math.min(...ids.map((id) => rects[id].y)) - PAD;
    const w = Math.max(...ids.map((id) => rects[id].x + rects[id].w)) + PAD - x;
    const h = Math.max(...ids.map((id) => rects[id].y + rects[id].h)) + PAD - y;
    return html`<div key=${b.id} class="gui-test-frame" style=${`left:${x}px;top:${y}px;width:${w}px;height:${h}px`}>
      <span class="gui-test-frame__label ok-font-status">${say(b.card.scheme.env)} · ${say(b.title)}</span></div>`;
  })}`;
}
