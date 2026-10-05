// 🌲 File Forest: a folder of the project as a tree that opens folder by folder in place. The files git
// sees changed are marked; a click picks the target, Send sends it down its roads; a file's mark (or a
// double-click) opens it in Lake. The work is the worker's (core/workers/forest.py).
import { signal } from "@preact/signals";
import { useEffect } from "preact/hooks";
import { html, cls } from "../html.js";
import { act, say } from "../link.js";
import { openInLake } from "../lake.js";

const opened = signal({});         // building id → {folder path: its rows, or null while they come}
const thumbs = signal({});         // "<building>|<path>" → a data: URL, "" when there is none

const CSS = `
.gui-forest { display: flex; flex-direction: column; gap: var(--space-2); min-height: 0; }
.gui-forest .gui-tree ul { margin: 0; }
.gui-forest__row { display: flex; align-items: center; gap: var(--space-1); }
.gui-forest__fold { width: var(--space-4); flex: none; text-align: center; color: var(--ink-muted); }
.gui-forest__name { overflow: hidden; text-overflow: ellipsis; }
.gui-forest__mark { margin-left: auto; flex: none; padding: 0 var(--space-1); }
.gui-forest__lake { flex: none; appearance: none; border: 0; background: none; color: var(--info); cursor: pointer; padding: 0 var(--space-1); }
.gui-forest__thumb { height: calc(var(--space-8) + var(--space-4)); max-width: calc(var(--space-8) * 3); flex: none;
  object-fit: contain; background: var(--panel-inset); box-shadow: var(--bevel-sunken); }
.gui-forest__changed { color: var(--warning); }
`;
if (typeof document !== "undefined" && !document.getElementById("gui-css-forest")) {
  const style = document.createElement("style");
  style.id = "gui-css-forest";
  style.textContent = CSS;
  document.head.append(style);
}

function list(id, path) {
  const was = opened.value[id] || {};
  opened.value = { ...opened.value, [id]: { ...was, [path]: was[path] || null } };
  act(id, "list", { path }).then(
    (rows) => { opened.value = { ...opened.value, [id]: { ...(opened.value[id] || {}), [path]: rows } }; },
    () => fold(id, path));
}

function fold(id, path) {
  const { [path]: _gone, ...rest } = opened.value[id] || {};
  opened.value = { ...opened.value, [id]: rest };
}

function thumb(id, path) {
  const key = `${id}|${path}`;
  if (key in thumbs.value) return thumbs.value[key];
  thumbs.value = { ...thumbs.value, [key]: "" };
  act(id, "thumb", { path }).then((url) => { thumbs.value = { ...thumbs.value, [key]: url || "" }; }, () => {});
  return "";
}

const pick = (id, path) => act(id, "pick", { path }).catch(() => {});
const toLake = (id, path) => openInLake({ path, title: path.split("/").pop(), from: id });

function Thumb({ id, row }) {
  const url = thumb(id, row.path);
  if (!url) return null;
  return row.media === "video"
    ? html`<video class="gui-forest__thumb" src=${url} muted loop preload="metadata"
        onMouseEnter=${(e) => e.target.play().catch(() => {})} onMouseLeave=${(e) => e.target.pause()}></video>`
    : html`<img class="gui-forest__thumb" src=${url} alt="" loading="lazy" />`;
}

function Rows({ id, rows, picked, media }) {
  const open = opened.value[id] || {};
  if (!rows.length) return html`<li class="ok-tone-muted">empty folder</li>`;
  return rows.map((r) => {
    const isOpen = r.dir && r.path in open;
    const click = () => {
      if (r.dir) {
        if (isOpen) fold(id, r.path); else list(id, r.path);
      }
      pick(id, r.path);
    };
    return html`<li key=${r.path}>
      <div class=${cls("gui-tree__item gui-forest__row", { "is-selected": r.path === picked })} title=${r.path}
          onClick=${click} onDblClick=${() => !r.dir && toLake(id, r.path)}>
        <span class="gui-forest__fold">${r.dir ? (isOpen ? "▾" : "▸") : ""}</span>
        ${media && r.media && html`<${Thumb} id=${id} row=${r} />`}
        <span class=${cls("gui-forest__name", { "gui-forest__changed": !!r.status })}>${r.name}${r.dir ? "/" : ""}</span>
        ${r.path === picked && html`<span><i class="ok-ico">🎯</i><span class="ok-word">target</span></span>`}
        ${r.status && html`<span class="gui-forest__mark ok-font-status ok-tone-wait" title=${say("changed")}>${r.status}</span>`}
        ${!r.dir && html`<button class="gui-forest__lake" title=${say("Open in Lake")} aria-label=${say("Open in Lake")}
          onClick=${(e) => { e.stopPropagation(); toLake(id, r.path); }}>↗</button>`}
      </div>
      ${isOpen && html`<ul>${open[r.path] ? html`<${Rows} id=${id} rows=${open[r.path]} picked=${picked} media=${media} />`
                                         : html`<li class="ok-tone-muted">…</li>`}</ul>`}
    </li>`;
  });
}

function Tree({ id, data, media }) {
  // the worker said it changed (git looked again): the open folders are read again too
  useEffect(() => { Object.keys(opened.value[id] || {}).forEach((p) => list(id, p)); }, [id, data]);
  if (data.error && !data.top.length) return html`<p class="ok-tone-fire">⚠ ${data.error}</p>`;
  return html`<div class="gui-tree"><ul>
    <${Rows} id=${id} rows=${data.top} picked=${data.picked} media=${media} /></ul></div>`;
}

function Head({ id, data }) {
  const name = data.picked ? data.picked.split("/").pop() : "";
  return html`<div class="gui-head">
    <span class="gui-head__what"><b>${data.folder}</b>
      ${data.error ? html`<span class="ok-tone-fire"> · ⚠ ${data.error}</span>`
        : html`<span class="ok-tone-muted"> · ${data.changed ? `changed: ${data.changed} files` : "nothing changed"}</span>`}</span>
    <span class="gui-head__spacer"></span>
    ${name ? html`<span class="gui-head__what" title=${data.picked}><i class="ok-ico">🎯</i><span class="ok-word">target:</span> ${name}</span>`
           : html`<span class="ok-tone-muted">click a file to pick it</span>`}
    <button class="ok-act" disabled=${!name} title=${say("The picked file goes down its roads")}
      onClick=${() => act(id, "send").catch(() => {})}><span class="ok-act__label">Send</span></button>
  </div>`;
}

/** Closed: `./<folder>`, how many files changed, the target (docs/design/building-views.md). */
export function card(b) {
  const c = b.card;
  if (!c) return null;
  if (c.error) return html`<span class="ok-tone-fire">⚠ ${c.error}</span>`;
  return html`<div>${c.folder}</div>
    <div class=${c.changed ? "ok-tone-wait" : "ok-tone-muted"}>${c.changed ? `changed: ${c.changed} files` : "changed: nothing"}</div>
    ${c.picked && html`<div><i class="ok-ico">🎯</i><span class="ok-word">target:</span> ${c.picked}</div>`}`;
}

/** Command: the top of the tree (folders open in place), the changed marked, a click picks; Send. */
export function preview(id, data) {
  return html`<div class="gui-forest"><${Head} id=${id} data=${data} /><${Tree} id=${id} data=${data} media=${false} /></div>`;
}

/** Full: only the tree, with small previews of images and video. */
export function panes(id, data) {
  return { main: () => html`<div class="gui-forest"><${Head} id=${id} data=${data} />
    <${Tree} id=${id} data=${data} media=${true} /></div>` };
}

/** The type's quick actions on the Command Card (realm/catalog.py). */
const QUICK = { "files.open": (id) => act(id, "open").catch(() => {}) };

/** Does one of its quick actions (js/types.js); true when it did. */
export function quick(id, action) {
  const f = QUICK[action];
  if (!f) return false;
  f(id);
  return true;
}
