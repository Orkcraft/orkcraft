// Lake, the town's one viewer (docs/design/building-views.md §2): not a building but tabs of documents in
// the town's panel on the right (js/windows.js, docs/design/calm-town.md §2), beside the open building's
// Work and Info. Any building opens a document or a file here with a click on its mark (`openInLake`).
// The host keeps the tabs (gui/views/lake.py): the snapshot carries their heads, the page asks for the one
// it shows when its `rev` moved. What each document draws, and asking its keeper on a selection, is
// js/buildings/lake.js.
import { signal, effect } from "@preact/signals";
import { html, cls } from "./html.js";
import { town, command, say } from "./link.js";
import { Document, takeText, forget } from "./buildings/lake.js";

// shown: its tabs are in the panel; front: a document is the panel's tab shown (not the building's);
// active: the document shown
export const lake = signal({ shown: false, front: false, active: null });
const docs = signal({});          // tab id → what the host said of it (gui/views/lake.py `doc`)
const asked = new Map();          // tab id → the rev asked for last

/** Open a document in Lake: `{path}` a file of the project, `{url}` a page, `{text}` text as it is; `from`
 *  is the building it came from (its keeper answers on a selection). Resolves with the tab's id (null when refused). */
export function openInLake({ path, url, text, title = "", from = "" } = {}) {
  const kind = path ? "file" : url ? "url" : "text";
  const value = path || url || text || "";
  return command("lake.open", { kind, value, title, from }).then((tab) => {
    lake.value = { ...lake.value, shown: true, front: true, active: tab };
    return tab;
  }, () => null);
}

export function tabs() {
  return (town.value && town.value.lake && town.value.lake.tabs) || [];
}

// A tab that opened by itself (a building that once had a road into a Lake) shows the window; the one
// shown is asked for again whenever the host says it changed.
let known = null;
effect(() => {
  const list = tabs();
  const ids = new Set(list.map((t) => t.id));
  if (known !== null) {
    const fresh = list.filter((t) => !known.has(t.id));
    if (fresh.length) lake.value = { ...lake.value, shown: true, front: true, active: fresh[fresh.length - 1].id };
    for (const id of known) if (!ids.has(id)) { forget(`tab:${id}`); asked.delete(id); }
  }
  known = town.value ? ids : known;
  const l = lake.value;
  const active = list.find((t) => t.id === l.active) || list[list.length - 1];
  if (active && active.id !== l.active) lake.value = { ...l, active: active.id };
  if (!list.length && l.front) lake.value = { ...l, front: false };
  if (!active || !l.shown) return;
  const had = docs.value[active.id];
  if ((had && had.rev === active.rev) || asked.get(active.id) === active.rev) return;
  asked.set(active.id, active.rev);
  command("lake.doc", { tab: active.id }).then((d) => { docs.value = { ...docs.value, [active.id]: d }; }, () => {});
});

export function closeTab(id) {
  const text = takeText(`tab:${id}`);
  return command("lake.close", text === null ? { tab: id } : { tab: id, text }).then((closed) => {
    if (closed) docs.value = Object.fromEntries(Object.entries(docs.value).filter(([k]) => k !== id));
  }, () => {});
}

/** A document's tab in the panel's tab row. */
export function DocTab({ t, active, onPick }) {
  const dirty = t.conflict || (t.note || "").startsWith("●");
  return html`<div class=${cls("ok-tab gui-lake__tab", { "is-active": active })} role="tab" aria-selected=${active}
      title=${say(t.title)} onClick=${onPick} onAuxClick=${(e) => { if (e.button === 1) closeTab(t.id); }}>
    <span class="gui-lake__tabtitle">${t.title}</span>
    ${dirty && html`<span class="gui-lake__dirty" title=${say(t.conflict ? "Changed on disk" : "Not saved yet")}>●</span>`}
    <button class="gui-tab__close" title=${say("Close")} aria-label=${say(`Close ${t.title}`)}
      onClick=${(e) => { e.stopPropagation(); closeTab(t.id); }}>×</button>
  </div>`;
}

/** The document shown, in the panel's body. */
export function DocBody() {
  const list = tabs();
  const l = lake.value;
  const active = list.find((t) => t.id === l.active) || list[list.length - 1];
  if (!active) return null;
  const doc = docs.value[active.id];
  const send = (name, args = {}) => command("lake.act", { tab: active.id, act: name, args });
  return html`<div class="ok-win__body gui-win__body gui-lake__win">
    ${doc ? html`<${Document} key=${active.id} k=${`tab:${active.id}`} doc=${doc} send=${send} title=${active.title} />`
          : html`<p class="ok-tone-muted">Opening…</p>`}
  </div>`;
}
