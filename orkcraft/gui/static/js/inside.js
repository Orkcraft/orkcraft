// The inside of a building (decisions-2026-10.md §13.2, I2): a screen of its own, entered by the second click on a
// building in Camp (js/windows.js `openBuilding`, which I1's steward and its Enter call) for a type whose module draws
// its room (`inside(b)`, js/types.js) — the Task board first; the others keep A5's large card until theirs are drawn.
// Left (~60 %): the building from inside, its type's room, scrolled when large. Right (~40 %): its settings — the
// building's Info as it is today (js/console.js), on a merchant's window: cream parchment in a walnut frame with teal
// accents, in plain words. Exit, always at the top right, and Esc go back to the camp. Office keeps the card: a look
// changes how things are drawn, and Office draws no rooms.
import { html } from "./html.js";
import { town, say } from "./link.js";
import { typeModule } from "./types.js";
import { inside, leaveInside, usePeek } from "./windows.js";
import { InfoTab } from "./console.js";

/** The entered building's screen, or null (nothing entered, or it was demolished meanwhile). */
export function Inside() {
  const id = inside.value;
  const b = id && town.value && town.value.buildings.find((x) => x.id === id);
  const mod = b && b.page ? typeModule(b.type) : null;
  if (!b || !mod || !mod.inside) {
    queueMicrotask(leaveInside);              // gone, or not a room: back to the camp
    return null;
  }
  return html`<${Screen} b=${b} mod=${mod} />`;
}

function Screen({ b, mod }) {
  usePeek(b.id);                              // its state comes while it is entered
  return html`<section class="gui-inside" data-id=${b.id} data-type=${b.type} aria-label=${say(`${b.title}, inside`)}>
    <div class="gui-inside__room">${mod.inside(b)}</div>
    <aside class="gui-inside__shop" aria-label=${say(`${b.title} settings`)}>
      <div class="gui-inside__shop-frame">
        <h2 class="gui-inside__shop-title"><span>${say(b.title)}</span><small>${say("Settings")}</small></h2>
        <div class="gui-inside__shop-body"><${InfoTab} b=${b} /></div>
      </div>
    </aside>
    <button type="button" class="ok-btn gui-inside__exit" title=${say("Back to the camp (Esc)")} onClick=${leaveInside}>
      ${say("Exit")}</button>
  </section>`;
}
