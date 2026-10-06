// 🕳️ The Pit (docs/design/building-views.md §3): closed, its card is the drop zone — a file, a link or
// a text dropped on it goes in; command, the history of what was dropped; full, that history with what
// each drop's chain of processing cost and what it left in the other buildings. A drop opens in Lake.
// The sorting and sending are the worker's (core/workers/pit.py).
import { signal } from "@preact/signals";
import { useEffect, useRef, useState } from "preact/hooks";
import { html, cls } from "../html.js";
import { act, say, toast } from "../link.js";
import { openInLake } from "../lake.js";

const chosen = signal({});         // building id → the drop shown in full
const LIMIT = 5 * 1024 * 1024;     // gui/views/pit.py FILE_LIMIT: a file comes over the socket

const when = (at) => (at || "").slice(5, 16).replace("T", " ");
const money = (usd) => (usd ? `$${usd < 0.01 ? usd.toFixed(4) : usd.toFixed(2)}` : "");

function base64(file) {
  return new Promise((resolve, reject) => {
    const r = new FileReader();
    r.onload = () => resolve(String(r.result).split(",", 2)[1] || "");
    r.onerror = () => reject(r.error);
    r.readAsDataURL(file);
  });
}

/** What a drop brought: its files (their bytes), else the link or the text dragged. */
async function take(id, dt) {
  const files = Array.from(dt.files || []);
  if (files.length) {
    for (const f of files) {
      if (f.size > LIMIT) { toast(`${f.name}: larger than 5 MB — put it in the project and drop its path`, "warning"); continue; }
      try {
        await act(id, "drop_file", { name: f.name, data: await base64(f) });
      } catch (e) { /* toasted */ }
    }
    return;
  }
  const text = dt.getData("text/uri-list") || dt.getData("text/plain");
  if (text && text.trim()) act(id, "drop", { text }).catch(() => {});
}

const carries = (e) => Array.from(e.dataTransfer?.types || []).some((t) => t === "Files" || t.startsWith("text/"))
  && !Array.from(e.dataTransfer.types).includes("text/x-ork-card");

/** Makes `el` (a hut, a pane) a drop zone of building `id`; `setOver` says when something is over it. */
function useDropZone(ref, id, setOver, whole = null) {
  useEffect(() => {
    const el = whole ? ref.current && ref.current.closest(whole) : ref.current;
    if (!el) return undefined;
    const over = (e) => { if (carries(e)) { e.preventDefault(); e.dataTransfer.dropEffect = "copy"; setOver(true); } };
    const leave = (e) => { if (!el.contains(e.relatedTarget)) setOver(false); };
    const drop = (e) => {
      if (!carries(e)) return;
      e.preventDefault(); e.stopPropagation(); setOver(false);
      take(id, e.dataTransfer);
    };
    el.addEventListener("dragover", over);
    el.addEventListener("dragleave", leave);
    el.addEventListener("drop", drop);
    return () => { el.removeEventListener("dragover", over); el.removeEventListener("dragleave", leave);
                   el.removeEventListener("drop", drop); };
  }, [id]);
}

function open(id, it) {
  if (it.link) openInLake({ url: it.value, title: it.title, from: id });
  else openInLake({ path: it.value, title: it.title, from: id });
}

// -- closed: the whole card is the drop zone, only an icon in it ---------------------------------------
// A tray with an arrow over it; while a file is held over the card the arrow drops into the tray, the
// tray lights up and the card's edge turns to the focus colour (pit.css): it takes the file.

const sheet = new URL("./pit.css", import.meta.url).href;
if (!document.querySelector(`link[href="${sheet}"]`)) {
  const link = document.createElement("link");
  link.rel = "stylesheet";
  link.href = sheet;
  document.head.appendChild(link);
}

function TrayIcon() {
  return html`<svg class="gui-pit__icon" viewBox="0 0 32 32" width="32" height="32" aria-hidden="true">
    <path class="gui-pit__arrow" d="M16 3v13M10.5 10.5 16 16l5.5-5.5" />
    <path class="gui-pit__tray" d="M4 18v8.5h24V18M4 18h6.5l2 3.5h7l2-3.5H28" />
  </svg>`;
}

function DropCard({ b }) {
  const ref = useRef(null);
  const [over, setOver] = useState(false);
  useDropZone(ref, b.id, setOver, ".gui-hut");
  return html`<div ref=${ref} class=${cls("gui-pit__zone", { "is-over": over })}
      title=${say("Drop a file, a link or a text on the card")}>
    <${TrayIcon} /></div>`;
}

export function card(b) {
  return html`<${DropCard} b=${b} />`;
}

// -- command: what was dropped ---------------------------------------------------------------------------

function Row({ id, it, onClick, selected = false, full = false }) {
  return html`<li class=${cls("ok-item", { "is-selected": selected })} onClick=${onClick}
      title=${it.link ? it.value : it.file ? `${it.value} — a click opens it in Lake` : it.title}>
    <span class="ok-tone-muted">${when(it.at)}</span>
    <span class="ok-tone-muted">${it.kind}</span>
    <span class="gui-head__what">${it.title || it.value}</span>
    ${it.copied && html`<span class="ok-tone-muted">copied in</span>`}
    ${full && html`<span class="meta">${it.followed ? `${it.stops.length} stop${it.stops.length === 1 ? "" : "s"}` : ""}
      ${it.cost ? html` · <b>${money(it.cost)}</b>` : ""}</span>`}
  </li>`;
}

export function preview(id, data) {
  if (!data.items.length) return html`<p class="ok-font-status ok-tone-muted">Nothing dropped yet — drop a file, a link or a text on its card.</p>`;
  return html`<ul class="ok-list__items gui-rows ok-font-status">
    ${data.items.slice(0, 8).map((it) => html`<${Row} key=${it.id} id=${id} it=${it} onClick=${() => open(id, it)} />`)}
  </ul>
  ${data.count > 8 && html`<p class="ok-font-status ok-tone-muted">${data.count - 8} more — Open shows them all</p>`}`;
}

// -- full: the history, each drop's chain and its cost ------------------------------------------------------

function Drop({ id }) {
  const ref = useRef(null);
  const [over, setOver] = useState(false);
  const [text, setText] = useState("");
  useDropZone(ref, id, setOver);
  const send = () => act(id, "drop", { text }).then(() => setText(""), () => {});
  return html`<div ref=${ref} class="gui-head" style=${over ? "box-shadow: inset 0 0 0 1px var(--frame-focus)" : ""}>
    <span class=${over ? "ok-tone-accent" : "ok-tone-muted"}>Drag & drop a file here, or paste a link or a text</span>
    <input class="ok-input" style="flex: 1; min-width: 12em" placeholder=${say("a link, a path or a text")} value=${text}
      onInput=${(e) => setText(e.target.value)} onKeyDown=${(e) => e.key === "Enter" && text.trim() && send()} />
    <button class="ok-act" disabled=${!text.trim()} onClick=${send}><span class="ok-act__label">Drop it</span></button>
    <button class="ok-act" title=${say("Take what is in the clipboard")} onClick=${() => act(id, "paste").catch(() => {})}>
      <span class="ok-act__label">Paste</span></button>
  </div>`;
}

function History({ id, data }) {
  const sel = chosen.value[id];
  if (!data.items.length) return html`<p class="ok-tone-muted">Nothing dropped yet.</p>`;
  const spent = data.items.reduce((s, it) => s + (it.cost || 0), 0);
  return html`<div>
    <p class="ok-font-status ok-tone-muted">${data.count} dropped${spent ? html` · the chains spent <b>${money(spent)}</b>` : ""}</p>
    <ul class="ok-list__items gui-rows">
      ${data.items.map((it) => html`<${Row} key=${it.id} id=${id} it=${it} full selected=${it.id === sel}
        onClick=${() => { chosen.value = { ...chosen.value, [id]: it.id }; }} />`)}
    </ul></div>`;
}

function Chain({ id, data }) {
  const it = data.items.find((x) => x.id === chosen.value[id]) || data.items[0];
  if (!it) return html`<p class="ok-tone-muted">Pick a drop.</p>`;
  return html`<div class="ok-detail">
    <div class="ok-detail__head">${it.title || it.value}</div>
    <p class="ok-detail__meta">${when(it.at)} · ${it.kind}${it.copied ? " · copied in" : ""}
      ${it.cost ? html` · the chain spent <b>${money(it.cost)}</b>` : ""}</p>
    <div class="ok-detail__actions">
      <button class="ok-act" onClick=${() => open(id, it)}><span class="ok-act__label">Open in Lake</span></button></div>
    <p class="ok-detail__section">Where it went</p>
    ${!it.followed ? html`<p class="ok-tone-muted">Dropped before its carts were followed.</p>`
      : !it.stops.length ? html`<p class="ok-tone-muted">No road took it yet — lay one from this building.</p>`
      : html`<ul class="ok-list__items gui-rows">${it.stops.map((s, n) => html`<li key=${n} class="ok-item"
          title=${say("Open what arrived in Lake")}
          onClick=${() => (s.kind === "file" ? openInLake({ path: s.value, title: s.title, from: s.building })
                                             : openInLake({ text: s.value, title: s.title, from: s.building }))}>
          <span class="ok-tone-muted">${when(s.at)}</span> <b>${s.building_title_plain}</b>
          <span class="gui-head__what">${s.title}</span>
          <span class="meta">${s.event === "output" ? say("an ork's result") : s.event}</span></li>`)}</ul>`}
  </div>`;
}

export function panes(id, data) {
  return {
    drop: () => html`<${Drop} id=${id} />`,
    history: () => html`<${History} id=${id} data=${data} />`,
    chain: () => html`<${Chain} id=${id} data=${data} />`,
  };
}
