// A type's own page code, `js/buildings/<type>.js`, loaded the first time a building of the type is
// drawn (the snapshot says which types have one: `page`). A type exports what it draws in each of a
// building's three views (docs/design/building-views.md §4), all optional:
//
//   card(b)          the inside of its hut card on the town (closed), from `b.card`
//   preview(id, d)   the top of the Command Card while it is selected (command), from its detail
//   panes(id, d)     the panes of its whole window, by its UI document (full)
//   quick            {action id: fn(id)}: what its quick actions on the Command Card do
//
// A type that exports none of them still draws: its status lines, the buttons only, the old body.
import { signal } from "@preact/signals";

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
