// A type's own page code, `js/buildings/<type>.js`, loaded the first time a building of the type is
// drawn (the snapshot says which types have one: `page`). A type exports what it draws of a building
// (docs/design/building-views.md §4, docs/design/calm-town.md §2), all optional:
//
//   card(b)          the inside of its hut card on the town (closed), from `b.card`
//   mark(b)          {text, tone} in its title bar while the hut is folded: what its card says first
//                    (docs/design/folded-cards.md), or null
//   panes(id, d)     the panes of its Work tab in the panel, by its UI document
//   quick(id, a)     does its quick action `a` on the page — from its Info or from its closed card, so it never
//                    needs the panel open: what asks for words opens its own small window (`overlay`); true
//                    when it did, else the host does it (`building.quick`)
//   overlay()        the type's own small windows, drawn over the town whether its building is open or not
//   infoActs(b)      [{id, label, title, run}]: actions its Info offers beside the quick ones (a setup)
//   infoPage(b, p)   a page of its own drawn over its Info while one is open (js/infopage.js)
//   work = false     no Work window (docs/design/lighter-buildings.md §2): `card(b, "l")` does its everyday job,
//                    opening it grows its card in place (js/windows.js); on the phone its panel shows that card
//   grown = {w, h}   the size its card grows to when opened, when the large size (js/hut.js LEVEL_L) is too small
//   settings(id, d)  its own settings drawn in its Info, from its state `d` (what its Work held)
//   inside(b)        its room, when it has one: in Camp the second click enters it as a screen of its own, its Info
//                    beside it (js/inside.js, decisions-2026-10.md §13.2); else its large card as above
//
// A type that exports none of them still draws: its status lines in Work, its Info.
import { signal } from "@preact/signals";
import { html } from "./html.js";
import { command, town } from "./link.js";

const modules = signal({});                // type → its module (false: it has none, or it failed)
const loading = new Map();                 // type → the promise of its module, settled once

/** The type's module, or null while it loads or when it has none (a signal: the caller redraws). */
export function typeModule(type, page = true) {
  const have = modules.value[type];
  if (have !== undefined || !page || !/^[a-z_]+$/.test(type || "")) return have || null;
  typeReady(type);
  return null;
}

/** The type's module once it has loaded (null when it has none): what a decision that reads the module awaits — opening
 *  a building grows its card or enters its inside only by what its module says, never by how fast it came. */
export function typeReady(type) {
  if (modules.value[type] !== undefined) return Promise.resolve(modules.value[type] || null);
  if (!/^[a-z_]+$/.test(type || "")) return Promise.resolve(null);
  if (!loading.has(type)) {
    loading.set(type, import(`./buildings/${type}.js`).then(
      (m) => { modules.value = { ...modules.value, [type]: m }; return m; },
      () => { modules.value = { ...modules.value, [type]: false }; return null; }));
  }
  return loading.get(type);
}

/** Whether the type's module has settled (loaded, or known to be none). */
export const typeSettled = (type) => modules.value[type] !== undefined;

/** A quick action of a building: its type does it on the page when it can, else the host. */
export function runQuick(b, action) {
  const mod = b.page ? typeModule(b.type) : null;
  if (mod && mod.quick && mod.quick(b.id, action)) return;
  command("building.quick", { id: b.id, action }).catch(() => {});
}

/** Every loaded type's own small windows (a New note asked from a closed card), over the town. */
export function Overlays() {
  const loaded = Object.values(modules.value).filter((m) => m && m.overlay);
  void town.value;                         // they redraw with the town
  return html`${loaded.map((m, i) => html`<${m.overlay} key=${i} />`)}`;
}
