// A herald's notice (design-system-v3.md §4f; the V4 kit's .kit-notice): over the herald on the back wall (the lookout,
// the Calendar), opening upwards over the wall and the wilderness, never over a building. One at a time a herald; more
// behind it a "+N" plate; folded, a small count chip. When the person is at the default view and has not dragged it,
// the view eases down just enough for the notice's top to clear the HUD, and back when it folds (js/camp/town.js).
// What raises a notice is the heralds' own (later); this module only places and draws it.
import { signal } from "@preact/signals";
import { html, cls } from "../html.js";
import { say } from "../link.js";
import { HALL, hallTab } from "../tent.js";
import { openBuilding } from "../windows.js";

export const isHall = (id) => id === "town_hall" || id === HALL;

export function openCouncil() {
  hallTab.value = "hall";
  openBuilding(HALL, "work");
}

/** Open notices by building id: { title, when?, lines: [text | { text, small }], acts: [{ label, primary?, run? }],
 *  ask? (a question: its mark alone yellow), more? (how many behind it), folded? (only the count chip) }. */
export const notices = signal({});

export const showNotice = (id, n) => { notices.value = { ...notices.value, [id]: n }; };
export const foldNotice = (id) => { const n = { ...notices.value }; delete n[id]; notices.value = n; };

function Notice({ id, n }) {
  if (n.folded) {
    return html`<button type="button" class="kit-notice-chip" onClick=${(e) => { e.stopPropagation(); showNotice(id, { ...n, folded: false }); }}>
      ${say(`${n.count || 1} new`)}</button>`;
  }
  const hall = isHall(id);
  const acts = n.acts || (hall ? [{ label: "Open", primary: true, run: openCouncil }, { label: "Dismiss" }] : [{ label: "Dismiss" }]);
  const onAct = (a) => {
    if (a.run) a.run();
    else if (hall && (a.primary || a.label === "Open")) openCouncil();
    else foldNotice(id);
  };
  return html`<div class=${cls("kit-notice", { "is-stacked": n.more > 0 })} role="dialog" aria-label=${say(n.title)}
      onClick=${hall ? (e) => { e.stopPropagation(); openCouncil(); } : undefined}>
    ${n.more > 0 && html`<span class="kit-notice__more">+${n.more}</span>`}
    <div class="kit-notice__head">${n.ask && html`<span class="kit-notice__ask">?</span>`}
      <span class="kit-notice__title">${say(n.title)}</span>${n.when && html`<span class="kit-notice__when">${say(n.when)}</span>`}</div>
    ${(n.lines || []).map((l) => html`<p class=${cls("kit-notice__line", { "is-small": l && l.small })}>${say(typeof l === "string" ? l : l.text)}</p>`)}
    <div class="kit-notice__acts">${acts.map((a) => html`<button type="button"
        class=${cls("kit-btn", { "is-teal": a.primary })} onClick=${(e) => { e.stopPropagation(); onAct(a); }}>${say(a.label)}</button>`)}</div>
  </div>`;
}

const HALF = 190;         // half the widest notice (the kit's 360 px and its frame)
const RAIL = 104;         // the camp's tools down the left edge (the Workchief, Items): a notice stays right of them
const SWAY = 150;         // how far a notice may stand aside of its herald, its tail still over the herald

/** The open notices, each over its herald's top, its tail pointing down at it; one by the window's edge stands aside
 *  into the window, its tail still at the herald. `seen`: the part of the world in the window, {left, right}. */
export function Notices({ L, seen }) {
  const open = Object.entries(notices.value).filter(([id]) => (L.buildings[id] && L.buildings[id].wall) || (isHall(id) && L.home));
  if (!open.length) return null;
  return html`<div class="gui-camp__layer is-notices">${open.map(([id, n]) => {
    const p = isHall(id) ? L.home : L.buildings[id];
    const x = Math.min(Math.max(p.cx, seen.left + RAIL + HALF), seen.right - HALF - 16);
    const dx = Math.max(-SWAY, Math.min(SWAY, p.cx - x));
    return html`<div key=${id} class="gui-camp__notice" data-id=${id} style=${`left:${p.cx - dx}px;top:${p.y - 6}px;--tail:${dx}px`}
        onClick=${(e) => { e.stopPropagation(); if (isHall(id)) openCouncil(); }} onPointerDown=${(e) => e.stopPropagation()}><${Notice} id=${id} n=${n} /></div>`;
  })}</div>`;
}
