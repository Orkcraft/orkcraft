// 🗑️ Scroll Dump: the librarian's state, the wiki and its sources as a tree, and the page open,
// rendered (core/workers/scrolls.py does the work). A page's mark opens it in Lake; the Command Card
// shows the librarian's state and the last changed pages.
import { signal } from "@preact/signals";
import { useState } from "preact/hooks";
import { html, cls } from "../html.js";
import { act, say } from "../link.js";
import { Dialog } from "../dialog.js";
import { openInLake } from "../lake.js";

const CSS = `
.gui-scrolls__lake { appearance: none; border: 0; background: none; color: var(--info); cursor: pointer; padding: 0 var(--space-1); }
.gui-scrolls__recent { list-style: none; margin: 0; padding: 0; }
.gui-scrolls__recent li { display: flex; gap: var(--space-2); align-items: baseline; }
.gui-scrolls__recent .gui-tree__item { flex: 1; min-width: 0; }
`;
if (typeof document !== "undefined" && !document.getElementById("gui-css-scrolls")) {
  const style = document.createElement("style");
  style.id = "gui-css-scrolls";
  style.textContent = CSS;
  document.head.append(style);
}

const adding = signal(null);       // the building whose "Add a folder" dialog is open
const toLake = (id, path, title) => openInLake({ path, title: title || path.split("/").pop(), from: id });

function LakeMark({ id, path, title }) {
  return html`<button class="gui-scrolls__lake" title=${say("Open in Lake")} aria-label=${say("Open in Lake")}
    onClick=${(e) => { e.stopPropagation(); toLake(id, path, title); }}>↗</button>`;
}

const open = signal({});           // building id → {path, html}

function read(id, path, page) {
  act(id, "read", { path, page }).then((r) => { open.value = { ...open.value, [id]: r }; }, () => {});
}

function FolderDialog({ id, onClose }) {
  const [path, setPath] = useState("");
  const add = () => act(id, "add_folder", { path }).then(onClose, () => {});
  return html`<${Dialog} title="Connect a folder of notes" text="A folder in the project: the librarian reads it, never writes it."
      onCancel=${onClose}
      actions=${html`<button class="ok-btn" onClick=${onClose}>Cancel</button>
        <button class="ok-btn primary" disabled=${!path.trim()} onClick=${add}>Connect it</button>`}>
    <input class="ok-input" placeholder="docs/handbook" value=${path} autofocus
      onInput=${(e) => setPath(e.target.value)} onKeyDown=${(e) => e.key === "Enter" && path.trim() && add()} />
  </${Dialog}>`;
}

function Head({ id, data }) {
  return html`<div class="gui-head">
    <span class=${cls("gui-head__what", { "ok-tone-error": data.error, "ok-tone-wait": !!data.running })}>
      <b>${data.topic}</b> · ${data.pages_count} page${data.pages_count === 1 ? "" : "s"} ·
      ${data.sources.length} source${data.sources.length === 1 ? "" : "s"} · ${data.state_plain}</span>
    <span class="gui-head__spacer"></span>
    ${data.running
      ? html`<button class="ok-act" onClick=${() => act(id, "stop")}><span class="ok-act__label">Stop</span></button>`
      : html`<button class="ok-act" onClick=${() => act(id, "ingest")}><span class="ok-act__label">Take in</span></button>
             <button class="ok-act" onClick=${() => act(id, "lint")}><span class="ok-act__label">Check the wiki</span></button>`}
    <button class="ok-act" onClick=${() => { adding.value = id; }}><span class="ok-act__label">Add a folder</span></button>
    <${Adding} id=${id} />
  </div>`;
}

function Adding({ id }) {
  return adding.value === id ? html`<${FolderDialog} id=${id} onClose=${() => { adding.value = null; }} />` : null;
}

function Tree({ id, data }) {
  const current = (open.value[id] || {}).path;
  const row = (path, page, label, extra) => html`<li key=${path}
      class=${cls("gui-tree__item", { "is-selected": path === current })} onClick=${() => read(id, path, page)}>
    ${label}${extra}</li>`;
  return html`<div class="gui-tree">
    <details open>
      <summary><b>${data.root}</b> <span class="ok-tone-muted">${data.pages_count}</span></summary>
      <ul>${data.pages.length ? data.pages.map((p) => row(p.path, true,
          html`<span style=${`padding-left:${p.depth}em`}>${p.title}</span>`,
          html`${p.locked && html` <span class="ok-word ok-tone-muted">people's</span>`}<${LakeMark} id=${id} path=${p.path} title=${p.title} />`))
        : html`<li class="ok-tone-muted">No wiki yet — the first take-in makes it.</li>`}</ul>
    </details>
    ${data.sources.map((b) => html`<details key=${b.path}>
      <summary><b>${b.path}</b> <span class="ok-tone-muted">${b.count}</span>
        ${b.todo > 0 && html` <span class="ok-tone-wait">● ${b.todo}</span>`}
        ${b.error && html` <span class="ok-tone-wait">⚠ ${b.error}</span>`}</summary>
      <ul>${b.items.map((n) => row(n.path, false, n.title,
          n.fresh ? html` <span class="ok-tone-wait">●</span>` : ""))}</ul>
    </details>`)}
  </div>`;
}

function Page({ id, data }) {
  const page = open.value[id];
  if (!page) return html`<p class="ok-tone-muted">Pick a page in the tree.</p>`;
  const isPage = data.pages.some((p) => p.path === page.path);
  return html`<div>
    ${isPage && html`<div class="gui-head"><span class="gui-head__what ok-tone-muted">${page.path}</span>
      <span class="gui-head__spacer"></span>
      <button class="ok-act" onClick=${() => toLake(id, page.path)}><span class="ok-act__label">Open in Lake</span></button></div>`}
    <div class="gui-prose" dangerouslySetInnerHTML=${{ __html: page.html }}></div>
  </div>`;
}

function ago(mtime) {
  const s = Math.max(0, Date.now() / 1000 - mtime);
  return s < 90 ? "just now" : s < 5400 ? `${Math.round(s / 60)} min ago`
    : s < 129600 ? `${Math.round(s / 3600)} h ago` : `${Math.round(s / 86400)} d ago`;
}

/** Closed: the pages and what waits to be taken in, nothing more (docs/design/building-views.md). */
export function card(b) {
  const c = b.card;
  if (!c) return null;
  return html`<div><b>${c.pages}</b> page${c.pages === 1 ? "" : "s"}</div>
    <div class=${c.error ? "ok-tone-fire" : c.running || c.pending ? "ok-tone-wait" : "ok-tone-muted"}>
      ${c.running ? `${c.running}…` : c.pending ? `${c.pending} pending` : "nothing pending"}</div>`;
}

/** Command: the librarian's state, the last changed pages (each opens in Lake); Add base. Ingest and
 * Lint are the type's quick actions, below. */
export function preview(id, data) {
  return html`<div class="gui-scrolls">
    <div class="gui-head">
      <span class=${cls("gui-head__what", { "ok-tone-error": data.error, "ok-tone-wait": !!data.running })}>
        <b>${data.topic}</b> · ${data.pages_count} page${data.pages_count === 1 ? "" : "s"} · ${data.state_plain}</span>
      <span class="gui-head__spacer"></span>
      ${data.running && html`<button class="ok-act" onClick=${() => act(id, "stop")}><span class="ok-act__label">Stop</span></button>`}
      <button class="ok-act" onClick=${() => { adding.value = id; }}><span class="ok-act__label">Add base</span></button>
    </div>
    ${data.note && html`<p class="ok-font-status ok-tone-muted">${data.note}</p>`}
    ${data.recent.length ? html`<ul class="gui-scrolls__recent">${data.recent.map((p) => html`<li key=${p.path}>
        <span class="gui-tree__item" title=${p.path} onClick=${() => toLake(id, p.path, p.title)}>${p.title}</span>
        <span class="ok-font-status ok-tone-muted">${ago(p.mtime)}</span></li>`)}</ul>`
      : html`<p class="ok-tone-muted">No pages yet — Ingest makes them.</p>`}
    <${Adding} id=${id} />
  </div>`;
}

/** The type's quick actions on the Command Card (realm/catalog.py). */
const QUICK = {
  "wiki.ingest": (id) => act(id, "ingest").catch(() => {}),
  "wiki.lint": (id) => act(id, "lint").catch(() => {}),
  "knowledge.add": (id) => { adding.value = id; },
};

/** Does one of its quick actions (js/types.js); true when it did. */
export function quick(id, action) {
  const f = QUICK[action];
  if (!f) return false;
  f(id);
  return true;
}

export function panes(id, data) {
  return {
    head: () => html`<${Head} id=${id} data=${data} />`,
    tree: () => html`<${Tree} id=${id} data=${data} />`,
    page: () => html`<${Page} id=${id} data=${data} />`,
  };
}
