// 🗑️ Scroll Dump: the librarian's state, the wiki and its sources as a tree, and the page open,
// rendered (core/workers/scrolls.py does the work).
import { signal } from "@preact/signals";
import { useState } from "preact/hooks";
import { html, cls } from "../html.js";
import { act } from "../link.js";
import { Dialog } from "../dialog.js";

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
  const [adding, setAdding] = useState(false);
  return html`<div class="gui-head">
    <span class=${cls("gui-head__what", { "ok-tone-error": data.error, "ok-tone-wait": !!data.running })}>
      <b>${data.topic}</b> · ${data.pages_count} page${data.pages_count === 1 ? "" : "s"} ·
      ${data.sources.length} source${data.sources.length === 1 ? "" : "s"} · ${data.state_plain}</span>
    <span class="gui-head__spacer"></span>
    ${data.running
      ? html`<button class="ok-act" onClick=${() => act(id, "stop")}><span class="ok-act__label">Stop</span></button>`
      : html`<button class="ok-act" onClick=${() => act(id, "ingest")}><span class="ok-act__label">Take in</span></button>
             <button class="ok-act" onClick=${() => act(id, "lint")}><span class="ok-act__label">Check the wiki</span></button>`}
    <button class="ok-act" onClick=${() => setAdding(true)}><span class="ok-act__label">Add a folder</span></button>
    ${adding && html`<${FolderDialog} id=${id} onClose=${() => setAdding(false)} />`}
  </div>`;
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
          p.locked ? html` <span class="ok-word ok-tone-muted">people's</span>` : ""))
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

function Page({ id }) {
  const page = open.value[id];
  if (!page) return html`<p class="ok-tone-muted">Pick a page in the tree.</p>`;
  return html`<div class="gui-prose" dangerouslySetInnerHTML=${{ __html: page.html }}></div>`;
}

export function panes(id, data) {
  return {
    head: () => html`<${Head} id=${id} data=${data} />`,
    tree: () => html`<${Tree} id=${id} data=${data} />`,
    page: () => html`<${Page} id=${id} />`,
  };
}
