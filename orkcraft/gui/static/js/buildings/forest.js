// 🌲 File Forest: a folder of the project as a tree that opens folder by folder in place. Closed: how many
// files changed and their names, the target. Open, made for the half panel: the counters on one line, the
// target as a strip with Send beside it, the changed files listed over the tree; a click picks the target,
// a file's mark (or a double-click) opens it in Lake. The work is the worker's (core/workers/forest.py).
import { signal } from "@preact/signals";
import { useEffect } from "preact/hooks";
import { html, cls } from "../html.js";
import { act, say } from "../link.js";
import { openInLake } from "../lake.js";

const opened = signal({});         // building id → {folder path: its rows, or null while they come}
const thumbs = signal({});         // "<building>|<path>" → a data: URL, "" when there is none

const sheet = new URL("./forest.css", import.meta.url).href;
if (typeof document !== "undefined" && !document.querySelector(`link[href="${sheet}"]`)) {
  const link = document.createElement("link");
  link.rel = "stylesheet";
  link.href = sheet;
  document.head.appendChild(link);
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
        ${r.path === picked && html`<span class="gui-forest__target">${say("target")}</span>`}
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

/** The head: the folder, how many files changed, Open the folder quiet; the target picked as a strip under
 *  it with Send beside it (and Open in Lake for a file). */
function Head({ id, data }) {
  const name = data.picked ? data.picked.split("/").pop() : "";
  const file = !!name && !data.top.some((r) => r.path === data.picked && r.dir);
  return html`<div>
    <div class="forest-head">
      <span title=${data.root}><b>${data.folder}</b></span>
      ${data.error ? html`<span class="ok-tone-fire">⚠ ${data.error}</span>`
        : data.changed ? html`<span class="ok-tone-wait"><b>${data.changed}</b> ${say(data.changed === 1 ? "file changed" : "files changed")}</span>`
        : html`<span class="ok-tone-ok">✓ ${say("nothing changed")}</span>`}
      <span class="forest-head__spacer"></span>
      <button class="ok-act" title=${say("Open the folder in the system's file manager")}
        onClick=${() => act(id, "open").catch(() => {})}><span class="ok-act__label">${say("Open the folder")}</span></button>
    </div>
    <div class="forest-target">
      ${name ? html`<span class="forest-target__what" title=${data.picked}><span>${say("Target")}:</span> <b>${name}</b>
          <span> · ${data.picked}</span></span>
          ${file && html`<button class="ok-act" onClick=${() => toLake(id, data.picked)}><span class="ok-act__label">${say("Open in Lake")}</span></button>`}`
        : html`<span class="forest-target__what"><span>${say("Click a file to pick it as the target")}</span></span>`}
      <button class="ok-btn primary" disabled=${!name} title=${say("The picked file goes down its roads")}
        onClick=${() => act(id, "send").catch(() => {})}>Send</button>
    </div>
  </div>`;
}

/** The changed files, the ones looked at most: a click picks one, its mark opens it in Lake. */
function Changed({ id, data }) {
  const rows = data.changes || [];
  if (!rows.length) return null;
  return html`<section class="forest-changed">
    <h3 class="ok-font-heading">${say("Changed")} <small>${data.changed}</small></h3>
    <ul>${rows.map((r) => html`<li key=${r.path}>
      <div class=${cls("gui-tree__item gui-forest__row", { "is-selected": r.path === data.picked })} title=${r.path}
          onClick=${() => pick(id, r.path)} onDblClick=${() => toLake(id, r.path)}>
        <span class="gui-forest__mark ok-font-status ok-tone-wait" title=${say("changed")}>${r.status || "M"}</span>
        <span class="gui-forest__name">${r.name}</span>
        <span class="gui-forest__dir">${r.path.slice(0, -r.name.length - 1)}</span>
        <button class="gui-forest__lake" title=${say("Open in Lake")} aria-label=${say("Open in Lake")}
          onClick=${(e) => { e.stopPropagation(); toLake(id, r.path); }}>↗</button>
      </div></li>`)}</ul>
    ${data.changed > rows.length && html`<p class="ok-tone-muted">+${data.changed - rows.length} ${say("more in the tree")}</p>`}
  </section>`;
}

/** Closed: the headline is how many files changed (or ✓ nothing changed), the folder and their names
 *  under it; the foot the target (docs/design/building-views.md). */
export function card(b) {
  const c = b.card;
  if (!c) return null;
  if (c.error) return html`<div class="gui-hut__body-in">
    <div class="gui-hut__big ok-tone-error">✗ ${say("Unread")}<small>${c.folder}</small></div>
    <div class="gui-hut__text ok-tone-error" title=${c.error}>${c.error}</div></div>`;
  const files = c.files || [];
  return html`<div class="gui-hut__body-in">
    ${c.changed ? html`<div class="gui-hut__big"><span class="ok-tone-wait">${c.changed}</span><small>${say(c.changed === 1 ? "file changed" : "files changed")}</small></div>`
      : html`<div class="gui-hut__big"><span class="ok-tone-ok">✓</span><small>${say("nothing changed")}</small></div>`}
    <div class="gui-hut__text">${c.folder}</div>
    ${files.length > 0 && html`<div class="gui-hut__text ok-tone-muted">${files.join(" · ")}${c.changed > files.length ? ` +${c.changed - files.length}` : ""}</div>`}
    <div class="gui-hut__foot"><span>${c.picked ? html`${say("target")}: <b>${c.picked}</b>` : say("no target picked")}</span></div>
  </div>`;
}

/** The head with the target, the changed files over the tree, the tree with small previews of images and
 *  video (design/buildings/forest.json). */
export function panes(id, data) {
  return {
    head: () => html`<${Head} id=${id} data=${data} />`,
    tree: () => html`<div class="gui-forest"><${Changed} id=${id} data=${data} /><${Tree} id=${id} data=${data} media=${true} /></div>`,
  };
}

/** The type's quick actions in its Info (realm/catalog.py). */
const QUICK = { "files.open": (id) => act(id, "open").catch(() => {}) };

/** Does one of its quick actions (js/types.js); true when it did. */
export function quick(id, action) {
  const f = QUICK[action];
  if (!f) return false;
  f(id);
  return true;
}
