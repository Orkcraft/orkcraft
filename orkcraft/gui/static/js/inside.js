// The inside of a building (interiors.md §1, decisions-2026-10.md §13.2, §31, §33): a screen of its own, entered by the
// second click on a building in Camp (js/windows.js `openBuilding`, which I1's steward and its Enter call). The camp
// goes away entirely: a black screen, and on it the building in the middle, roof off, as large as the screen allows,
// lit like a stage. A type whose module draws its room (`inside(b)`, js/types.js — the Task board first) sizes it
// itself to the stage, on whole device pixels; a type whose room is not drawn yet but which does its work on its large
// card (`work = false`) gets a plain room — its floor and walls in the kit — with that card in it, so every building
// enters the same way. No permanent settings panel: a gear at the room's top right slides its settings in (the
// building's Info as it is today, js/console.js) and out again. Exit, always at the top right, and Esc go back to the
// camp where it was. Office keeps the card: a look changes how things are drawn, and Office draws no rooms.
import { useLayoutEffect, useRef, useState } from "preact/hooks";
import { html, cls } from "./html.js";
import { town, say } from "./link.js";
import { typeModule } from "./types.js";
import { inside, leaveInside, usePeek, workless } from "./windows.js";
import { InfoTab } from "./console.js";
import { Card } from "./hut.js";

/** The entered building's screen, or null (nothing entered, or it was demolished meanwhile). */
export function Inside() {
  const id = inside.value;
  const b = id && town.value && town.value.buildings.find((x) => x.id === id);
  const mod = b && b.page ? typeModule(b.type) : null;
  if (!b || !mod || !(mod.inside || workless(b))) {
    queueMicrotask(leaveInside);              // gone, or nothing to enter: back to the camp
    return null;
  }
  return html`<${Screen} key=${b.id} b=${b} mod=${mod} />`;
}

function Screen({ b, mod }) {
  usePeek(b.id);                              // its state comes while it is entered
  const [open, setOpen] = useState(false);    // the settings, slid in behind the gear
  const gear = say(open ? "Hide the settings" : "Settings");
  return html`<section class=${cls("gui-inside", { "is-settings": open })} data-id=${b.id} data-type=${b.type}
      data-room=${mod.inside ? "drawn" : "plain"} aria-label=${say(`${b.title}, inside`)}>
    <div class="gui-inside__stage">
      <div class="gui-inside__room">
        ${mod.inside ? mod.inside(b) : html`<${Plain} b=${b} />`}
        <button type="button" class="ok-btn gui-inside__gear" title=${gear} aria-label=${gear} aria-expanded=${open ? "true" : "false"}
          onClick=${() => setOpen(!open)}><img class="ok-sprite" src="/ds/sprites/icons/settings.png"
          srcset="/ds/sprites/icons/settings@2x.png 2x" width="20" height="20" alt="" draggable="false" /></button>
      </div>
    </div>
    <aside class="gui-inside__shop" aria-label=${say(`${b.title} settings`)} aria-hidden=${open ? "false" : "true"} inert=${!open}>
      <div class="gui-inside__shop-frame">
        <h2 class="gui-inside__shop-title"><span>${say(b.title)}</span><small>${say("Settings")}</small></h2>
        <div class="gui-inside__shop-body"><${InfoTab} b=${b} /></div>
      </div>
    </aside>
    <button type="button" class="ok-btn gui-inside__exit" title=${say("Back to the camp (Esc)")} onClick=${leaveInside}>
      ${say("Exit")}</button>
  </section>`;
}

// The plain room in art pixels: its back wall above the floor line, the floor below; drawn at a whole number of
// device pixels per art pixel, as large as the stage allows.
const PLAIN = { w: 200, h: 120, floor: 84 };

/** The whole number of device pixels per art pixel that fits `room` in the stage `el` stands in, never under ×2. */
export function useStageScale(ref, room) {
  const [s, setS] = useState(4);
  useLayoutEffect(() => {
    const el = ref.current;
    const box = el && (el.closest(".gui-inside__stage") || el.parentElement);
    if (!box || typeof ResizeObserver === "undefined") return undefined;
    const fit = () => {
      const cs = getComputedStyle(box), dpr = window.devicePixelRatio || 1;
      const w = box.clientWidth - parseFloat(cs.paddingLeft) - parseFloat(cs.paddingRight);
      const h = box.clientHeight - parseFloat(cs.paddingTop) - parseFloat(cs.paddingBottom);
      if (w > 0 && h > 0) setS(Math.max(2 * dpr, Math.floor(Math.min((w * dpr) / room.w, (h * dpr) / room.h))) / dpr);
    };
    const ro = new ResizeObserver(fit);
    ro.observe(box);
    fit();
    return () => ro.disconnect();
  }, []);
  return s;
}

/** A building whose room is not drawn yet: kit walls and floor, its large card standing in the middle. */
function Plain({ b }) {
  const ref = useRef(null);
  const s = useStageScale(ref, PLAIN);
  return html`<div class="gui-inside__plain" ref=${ref}
      style=${`width:${PLAIN.w * s}px;height:${PLAIN.h * s}px;--floor:${(PLAIN.h - PLAIN.floor) * s}px`}>
    <div class="ok-hut gui-camp__card gui-inside__card l" data-id=${b.id}>
      <div class="ok-hut__card"><span class="ok-hut__label gui-hut__title"><span class="gui-hut__name">${say(b.title)}</span></span>
        <${Card} b=${b} level="l" /></div>
    </div>
  </div>`;
}
