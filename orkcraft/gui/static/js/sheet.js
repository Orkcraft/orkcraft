// The card as a building on the phone (color-pass.md §6c, docs/design/design-system-v2.md §2.5; backlog C3): the
// covers never lift by zooming — a building's inside does not fit a 390-point screen. The camp's core buildings
// stand at the top of the narrow town as covers (js/cover.js), and a tap on one, or on its line in the list, opens
// its card as a sheet from the bottom, headed by its crest, over the dimmed town; ✕, a tap on the dimmed town, Esc
// or a swipe down puts it back. Office draws the same strip and the same sheet with no art.
import { signal } from "@preact/signals";
import { useEffect, useRef } from "preact/hooks";
import { html, cls } from "./html.js";
import { say } from "./link.js";
import { openBuilding } from "./windows.js";
import { Card, QuickTray } from "./hut.js";
import { CORE, Cover, Crest, coverOf } from "./cover.js";

export const sheetOf = signal(null);          // the building id whose card is open as a sheet
const DOWN_PX = 72;                            // a swipe down this long puts the sheet back

const camp = () => document.documentElement.dataset.look !== "office";

/** The core buildings of the orkspace, in the line's order (v2 §6: the work runs left to right), as covers to tap. */
export function CampStrip({ buildings }) {
  const order = Object.keys(CORE);
  const core = buildings.map((b, i) => ({ b, n: i + 1 })).filter((x) => coverOf(x.b))
    .sort((x, y) => order.indexOf(x.b.type) - order.indexOf(y.b.type));
  if (!core.length) return null;
  return html`<nav class="gui-strip" aria-label=${say("The camp")}>
    ${core.map(({ b, n }) => {
      const kit = coverOf(b);
      return html`<button key=${b.id} data-sheet-tap class=${cls(`gui-strip__one is-kit-${kit.kind}`, { "is-alert": !!b.alert })}
          title=${say(b.title)} onClick=${() => { sheetOf.value = b.id; }}>
        ${camp() ? html`<${Cover} b=${b} kit=${kit} number=${n} lvl="a" />`
          : html`<span class="gui-strip__plain">${b.alert ? html`<b class="gui-cover__q">?</b> ` : ""}${say(b.title)}</span>`}
      </button>`;
    })}
  </nav>`;
}

/** The open sheet: the crest and the name, the card's inside, its quick actions and Open. */
export function CoverSheet({ buildings }) {
  const b = buildings.find((x) => x.id === sheetOf.value);
  const drag = useRef(null);
  const panel = useRef(null);
  useEffect(() => {
    if (!b) return undefined;
    const key = (e) => { if (e.key === "Escape") sheetOf.value = null; };
    window.addEventListener("keydown", key);
    return () => window.removeEventListener("keydown", key);
  }, [!!b]);
  if (!b) return null;
  const kit = coverOf(b);
  const close = () => { sheetOf.value = null; };
  const down = (e) => { drag.current = { y: e.clientY, id: e.pointerId }; };
  const move = (e) => {
    const d = drag.current;
    if (!d || d.id !== e.pointerId || !panel.current) return;
    panel.current.style.transform = `translateY(${Math.max(0, e.clientY - d.y)}px)`;
  };
  const up = (e) => {
    const d = drag.current;
    drag.current = null;
    if (panel.current) panel.current.style.transform = "";
    if (d && e.clientY - d.y >= DOWN_PX) close();
  };
  return html`<div class="gui-sheet" role="dialog" aria-modal="true" aria-label=${say(b.title)}>
    <div class="gui-sheet__dim" onClick=${close}></div>
    <section ref=${panel} class=${cls("gui-sheet__panel ok-hut", { "is-alert": !!b.alert })}>
      <header class="gui-sheet__head" onPointerDown=${down} onPointerMove=${move} onPointerUp=${up} onPointerCancel=${up}>
        <span class="gui-sheet__grip" aria-hidden="true"></span>
        ${kit && camp() && html`<${Crest} b=${b} kit=${kit} />`}
        <h2 class="gui-sheet__name">${say(b.title)}</h2>
        <button class="gui-toolerr__close gui-sheet__close" title=${say("Close")} aria-label=${say("Close")} onClick=${close}>×</button>
      </header>
      <div class="gui-sheet__body"><${Card} b=${b} level="m" /></div>
      <div class="gui-sheet__acts">
        <${QuickTray} b=${b} />
        <button class="ok-btn primary" onClick=${() => { close(); openBuilding(b.id); }}>${say("Open")}</button>
      </div>
    </section>
  </div>`;
}
