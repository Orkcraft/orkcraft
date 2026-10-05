// Lake, the town's one viewer (docs/design/building-views.md §2): a window, not a building. Any building
// opens a document or a file here with a click on its mark (`openInLake`); documents stand in tabs. The
// window takes the right half of the town by default and the whole of it with a click (between the HUD
// and the status bar); hidden, it waits as a handle at the right edge. The host keeps the tabs
// (gui/views/lake.py): the snapshot carries their heads, the page asks for the one it shows when its
// `rev` moved. What each document draws, and asking its keeper on a selection, is js/buildings/lake.js.
import { signal, effect } from "@preact/signals";
import { html, cls } from "./html.js";
import { town, command, say } from "./link.js";
import { Document, takeText, forget } from "./buildings/lake.js";

// shown: the window is up; full: over the whole town; active: the tab shown
export const lake = signal({ shown: false, full: false, active: null });
const docs = signal({});          // tab id → what the host said of it (gui/views/lake.py `doc`)
const asked = new Map();          // tab id → the rev asked for last

/** Open a document in Lake: `{path}` a file of the project, `{url}` a page, `{text}` text as it is; `from`
 *  is the building it came from (its keeper answers on a selection). Resolves with the tab's id (null when refused). */
export function openInLake({ path, url, text, title = "", from = "" } = {}) {
  const kind = path ? "file" : url ? "url" : "text";
  const value = path || url || text || "";
  return command("lake.open", { kind, value, title, from }).then((tab) => {
    lake.value = { ...lake.value, shown: true, active: tab };
    return tab;
  }, () => null);
}

function tabs() {
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
    if (fresh.length) lake.value = { ...lake.value, shown: true, active: fresh[fresh.length - 1].id };
    for (const id of known) if (!ids.has(id)) { forget(`tab:${id}`); asked.delete(id); }
  }
  known = town.value ? ids : known;
  const l = lake.value;
  const active = list.find((t) => t.id === l.active) || list[list.length - 1];
  if (active && active.id !== l.active) lake.value = { ...l, active: active.id };
  if (!active || !l.shown) return;
  const had = docs.value[active.id];
  if ((had && had.rev === active.rev) || asked.get(active.id) === active.rev) return;
  asked.set(active.id, active.rev);
  command("lake.doc", { tab: active.id }).then((d) => { docs.value = { ...docs.value, [active.id]: d }; }, () => {});
});

function closeTab(id) {
  const text = takeText(`tab:${id}`);
  return command("lake.close", text === null ? { tab: id } : { tab: id, text }).then((closed) => {
    if (closed) docs.value = Object.fromEntries(Object.entries(docs.value).filter(([k]) => k !== id));
  }, () => {});
}

const toggleFull = () => { lake.value = { ...lake.value, full: !lake.value.full }; };
const hide = () => { lake.value = { ...lake.value, shown: false, full: false }; };

function Tab({ t, active }) {
  const dirty = t.conflict || (t.note || "").startsWith("●");
  return html`<div class=${cls("ok-tab gui-lake__tab", { "is-active": active })} role="tab" aria-selected=${active}
      title=${say(t.title)} onClick=${() => { lake.value = { ...lake.value, active: t.id }; }}
      onAuxClick=${(e) => { if (e.button === 1) closeTab(t.id); }}>
    <span class="gui-lake__tabtitle">${t.title}</span>
    ${dirty && html`<span class="gui-lake__dirty" title=${say(t.conflict ? "Changed on disk" : "Not saved yet")}>●</span>`}
    <button class="gui-tab__close" title=${say("Close")} aria-label=${say(`Close ${t.title}`)}
      onClick=${(e) => { e.stopPropagation(); closeTab(t.id); }}>×</button>
  </div>`;
}

/** The Lake window over the town (nothing while no document is open). */
export function LakeWindow() {
  const list = tabs();
  if (!list.length) return null;
  const l = lake.value;
  if (!l.shown) {
    return html`<button class="ok-btn gui-lake__handle" title=${say("Show Lake")}
      onClick=${() => { lake.value = { ...l, shown: true }; }}>${say("Lake")} · ${list.length}</button>`;
  }
  const active = list.find((t) => t.id === l.active) || list[list.length - 1];
  const doc = docs.value[active.id];
  const send = (name, args = {}) => command("lake.act", { tab: active.id, act: name, args });
  return html`<section class=${cls("ok-win is-active gui-win gui-lake", { "is-full": l.full })} aria-label=${say("Lake")}>
    <div class="ok-head is-banner"></div>
    <div class="ok-win__frame">
      <div class="ok-win__bar" onDblClick=${toggleFull}>
        <span class="ok-win__title">${say("Lake")}</span>
        <span class="gui-head__spacer"></span>
        <button class="ok-btn" onClick=${toggleFull}>${l.full ? say("Half") : say("Full")}</button>
        <button class="gui-tab__close gui-win__close" title=${say("Hide Lake")} aria-label=${say("Hide Lake")} onClick=${hide}>−</button>
      </div>
      <div class="ok-tabs gui-lake__tabs" role="tablist">${list.map((t) => html`<${Tab} key=${t.id} t=${t} active=${t.id === active.id} />`)}</div>
      <div class="ok-win__body gui-win__body gui-lake__win">
        ${doc ? html`<${Document} key=${active.id} k=${`tab:${active.id}`} doc=${doc} send=${send} title=${active.title} />`
              : html`<p class="ok-tone-muted">Opening…</p>`}
      </div>
    </div>
  </section>`;
}
