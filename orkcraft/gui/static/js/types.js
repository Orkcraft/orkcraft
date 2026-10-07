// A type's own page code, `js/buildings/<type>.js`, loaded the first time a building of the type is
// drawn (the snapshot says which types have one: `page`). A type exports what it draws of a building
// (docs/design/building-views.md §4, docs/design/calm-town.md §2), all optional:
//
//   card(b)          the inside of its hut card on the town (closed), from `b.card`
//   panes(id, d)     the panes of its Work tab in the panel, by its UI document
//   quick(id, a)     does its quick action `a` on the page — from its Info or from its closed card, so it never
//                    needs the panel open: what asks for words opens its own small window (`overlay`); true
//                    when it did, else the host does it (`building.quick`)
//   overlay()        the type's own small windows, drawn over the town whether its building is open or not
//
// A type that exports none of them still draws: its status lines in Work, its Info.
import { signal } from "@preact/signals";
import { html } from "./html.js";
import { command, town } from "./link.js";

const modules = signal({});                // type → its module (false: it has none, or it failed)
const loading = new Set();

/** The type's module, or null while it loads or when it has none (a signal: the caller redraws). */
export function typeModule(type, page = true) {
  const have = modules.value[type];
  if (have !== undefined || !page || !/^[a-z_]+$/.test(type || "")) return have || null;
  if (!loading.has(type)) {
    loading.add(type);
    import(`./buildings/${type}.js`).then(
      (m) => { modules.value = { ...modules.value, [type]: m }; },
      () => { modules.value = { ...modules.value, [type]: false }; });
  }
  return null;
}

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
