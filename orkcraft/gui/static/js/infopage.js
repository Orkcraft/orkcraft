// A page of a building's own over its Info (docs/design/calendar-import.md §3): a setup in steps, drawn in
// the Info tab instead of a dialog. A type opens one (`openInfoPage(id, page)`) and exports `infoPage(b, page)`
// to draw it (js/types.js); while one is open the Info tab shows it alone. Every step after the first has
// ← Back in the window's top right; Cancel (on the first step) or the last step's end closes it, and the Info
// is the usual one again.
import { signal } from "@preact/signals";
import { html, cls } from "./html.js";
import { say } from "./link.js";
import { openBuilding } from "./windows.js";

export const infoPages = signal({});      // building id → {kind, step: [..names], ...the type's own}

/** Show the type's page `page` ({kind, ...}) in the building's Info, the panel opened on it. */
export function openInfoPage(id, page) {
  infoPages.value = { ...infoPages.value, [id]: { steps: [], ...page } };
  openBuilding(id, "info");
}

/** The usual Info again. */
export function closeInfoPage(id) {
  const { [id]: _, ...rest } = infoPages.value;
  infoPages.value = rest;
}

/** The page open in the building's Info, or null. */
export function infoPage(id) {
  return infoPages.value[id] || null;
}

/** Go on to `step` (its state merged in): Back comes back here. */
export function nextStep(id, step, more = {}) {
  const p = infoPages.value[id];
  if (!p) return;
  infoPages.value = { ...infoPages.value, [id]: { ...p, ...more, steps: [...p.steps, step] } };
}

/** One step back; on the first step, the usual Info. */
export function stepBack(id) {
  const p = infoPages.value[id];
  if (!p || !p.steps.length) { closeInfoPage(id); return; }
  infoPages.value = { ...infoPages.value, [id]: { ...p, steps: p.steps.slice(0, -1) } };
}

/** The step the page is on ("" for its first). */
export function stepOf(page) {
  return page && page.steps.length ? page.steps[page.steps.length - 1] : "";
}

/** A step's frame: its title, ← Back at the top right after the first step, the step, then its actions. */
export function InfoSteps({ id, title, sub, children, actions }) {
  const page = infoPages.value[id];
  const first = !page || !page.steps.length;
  return html`<section class="gui-infopage" aria-label=${say(title)}
      onKeyDown=${(e) => { if (e.key === "Escape") { e.stopPropagation(); stepBack(id); } }}>
    <div class="gui-infopage__head">
      <div class="gui-infopage__titles">
        <h3 class="ok-font-heading gui-infopage__title">${title}</h3>
        ${sub && html`<p class="ok-font-status ok-tone-muted gui-infopage__sub">${sub}</p>`}
      </div>
      ${!first && html`<button class="ok-btn gui-infopage__back" title=${say("The step before")}
        onClick=${() => stepBack(id)}>← ${say("Back")}</button>`}
    </div>
    <div class=${cls("gui-infopage__body")}>${children}</div>
    ${actions && html`<div class="gui-infopage__acts">${actions}</div>`}
  </section>`;
}
