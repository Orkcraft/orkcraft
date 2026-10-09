// 🕳️ The Pit (docs/design/building-views.md §3). Closed, its card is the drop zone — a file, a link or a
// text dropped on it goes in — with how many were dropped and the newest. Open, made for the half panel:
// one line to drop or paste into (the whole window takes a file held over it), the drops as one-line
// rows, newest first; a row opens its drop over the rows (← back): where its carts went and what the
// chain cost. A drop opens in the Inspector. The sorting and sending are the worker's (core/workers/pit.py).
import { signal } from "@preact/signals";
import { useEffect, useRef, useState } from "preact/hooks";
import { html, cls } from "../html.js";
import { act, say, toast } from "../link.js";
import { openInLake } from "../lake.js";

const chosen = signal({});         // building id → the drop shown in full
const LIMIT = 5 * 1024 * 1024;     // gui/views/pit.py FILE_LIMIT: a file comes over the socket

const when = (at) => (at || "").slice(5, 16).replace("T", " ");
/** A time as a card says it: today's as 09:21, an older one as 10-06. */
function stamp(at) {
  if (!at) return "";
  const d = new Date();
  const today = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
  return at.slice(0, 10) === today ? at.slice(11, 16) : at.slice(5, 10);
}
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
    const el = (whole && ref.current && ref.current.closest(whole)) || ref.current;
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

// -- closed: the whole card is the drop zone -----------------------------------------------------------
// A tray with an arrow over it beside how many were dropped; while a file is held over the card the arrow
// drops into the tray, the tray lights up and the card's edge turns to the focus colour (pit.css).

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
  const c = b.card || { n: 0 };
  return html`<div ref=${ref} class=${cls("gui-hut__body-in gui-pit__card", { "is-over": over })}
      title=${say("Drop a file, a link or a text on the card")}>
    <div class="gui-pit__zone">
      <${TrayIcon} />
      <div class="gui-pit__say">
        ${over ? html`<div class="gui-hut__big">${say("Let go")}<small>${say("it goes in")}</small></div>`
          : c.n ? html`<div class="gui-hut__big">${c.n}<small>${say("dropped")}</small></div>`
          : html`<div class="gui-hut__big">${say("Drop here")}</div>`}
        <div class="gui-hut__text ok-tone-muted">${c.spent ? html`${say("the chains spent")} <b>${money(c.spent)}</b>`
          : say("a file, a link or a text")}</div>
      </div>
    </div>
    ${c.last && html`<div class="gui-hut__foot"><span>${c.last.kind} · ${c.last.title}</span>
      <span class="gui-hut__when">${stamp(c.last.at)}</span></div>`}
  </div>`;
}

/** No view of its own: in Camp it stands with no card, its house and its name alone (js/hut.js bareOf); a file
 *  dropped on the building lands as on a card. */
export const bare = true;

export function card(b) {
  return html`<${DropCard} b=${b} />`;
}

/** Folded: how many were dropped. */
export function mark(b) {
  const n = (b.card && b.card.n) || 0;
  return n ? { text: `${n} dropped` } : null;
}

// -- open: one line to drop into, the drops, a drop over them --------------------------------------------

/** Drop: one line — a link, a path or a text written in, Drop it; Paste takes the clipboard. A file held
 *  anywhere over the window goes in too. */
function Drop({ id }) {
  const ref = useRef(null);
  const [over, setOver] = useState(false);
  const [text, setText] = useState("");
  useDropZone(ref, id, setOver, ".gui-win__body");
  const send = () => act(id, "drop", { text }).then(() => setText(""), () => {});
  return html`<div ref=${ref} class=${cls("gui-pit__drop", { "is-over": over })}>
    <${TrayIcon} />
    <input class="ok-input" value=${text} aria-label=${say("A link, a path or a text to drop")}
      placeholder=${over ? say("Let go: it goes in") : say("Drop a file here, or write a link, a path or a text")}
      onInput=${(e) => setText(e.target.value)} onKeyDown=${(e) => e.key === "Enter" && text.trim() && send()} />
    <button class="ok-btn primary" disabled=${!text.trim()} onClick=${send}>Drop it</button>
    <button class="ok-btn" title=${say("Take what is in the clipboard")} onClick=${() => act(id, "paste").catch(() => {})}>Paste</button>
  </div>`;
}

const stops = (n) => `${n} stop${n === 1 ? "" : "s"}`;

function Row({ it, onClick }) {
  return html`<li><button class="gui-pit__row" onClick=${onClick}
      title=${it.link ? it.value : it.file ? say(`${it.value} — opens its chain`) : it.title}>
    <span class="gui-pit__at">${when(it.at)}</span>
    <span class="gui-pit__kind">${it.kind}</span>
    <span class="gui-pit__title">${it.title || it.value}${it.copied && html` <span class="ok-tone-muted">· ${say("copied in")}</span>`}</span>
    <span class="gui-pit__meta">${it.followed && it.stops.length ? stops(it.stops.length) : ""}${it.cost ? html` · <b>${money(it.cost)}</b>` : ""}</span>
  </button></li>`;
}

function History({ id, data }) {
  if (!data.items.length) return html`<p class="ok-tone-muted">${say("Nothing dropped yet — drop a file on the line above or on the card.")}</p>`;
  const it = data.items.find((x) => x.id === chosen.value[id]);
  if (it) return html`<${Chain} key=${it.id} id=${id} data=${data} it=${it} />`;
  const spent = data.items.reduce((s, x) => s + (x.cost || 0), 0);
  return html`<div class="gui-pit__history">
    <p class="gui-pit__sum"><b>${data.count}</b> ${say("dropped")}${spent ? html` · ${say("the chains spent")} <b>${money(spent)}</b>` : ""}</p>
    <ul class="gui-pit__rows">
      ${data.items.map((x) => html`<${Row} key=${x.id} it=${x} onClick=${() => { chosen.value = { ...chosen.value, [id]: x.id }; }} />`)}
    </ul></div>`;
}

/** A drop open over the rows: ← back, what it is, Open in the Inspector, where its carts went. */
function Chain({ id, data, it }) {
  const back = () => { chosen.value = { ...chosen.value, [id]: null }; };
  return html`<div class="gui-pit__chain" onKeyDown=${(e) => { if (e.key === "Escape") { e.stopPropagation(); back(); } }}>
    <button class="ok-btn gui-pit__back" onClick=${back}>← ${say("All drops")} · ${data.items.length}</button>
    <h3 class="ok-detail__head gui-pit__name" title=${it.title || it.value}>${it.title || it.value}</h3>
    <p class="ok-detail__meta">${when(it.at)} · ${it.kind}${it.copied ? ` · ${say("copied in")}` : ""}
      ${it.cost ? html` · ${say("the chain spent")} <b>${money(it.cost)}</b>` : ""}</p>
    ${!it.link && html`<p class="gui-pit__path ok-font-mono" title=${it.value}>${it.value}</p>`}
    <div class="ok-detail__actions"><button class="ok-btn primary" onClick=${() => open(id, it)}>${say("Open in the Inspector")}</button></div>
    <p class="ok-detail__section">${say("Where it went")}</p>
    ${!it.followed ? html`<p class="ok-tone-muted">${say("Dropped before its carts were followed.")}</p>`
      : !it.stops.length ? html`<p class="ok-tone-muted">${say("No road took it yet — lay one from this building.")}</p>`
      : html`<ul class="gui-pit__rows">${it.stops.map((s, n) => html`<li key=${n}><button class="gui-pit__row is-stop"
          title=${say("Open what arrived in the Inspector")}
          onClick=${() => (s.kind === "file" ? openInLake({ path: s.value, title: s.title, from: s.building })
                                             : openInLake({ text: s.value, title: s.title, from: s.building }))}>
          <span class="gui-pit__at">${when(s.at)}</span>
          <span class="gui-pit__kind"><b>${s.building_title_plain}</b></span>
          <span class="gui-pit__title">${s.title}</span>
          <span class="gui-pit__meta">${s.event === "output" ? say("an ork's result") : s.event}</span></button></li>`)}</ul>`}
  </div>`;
}

/** The window by its UI document (design/buildings/pit.json): a drop opens over the rows, in `history`;
 *  `chain` shows nothing of its own (an older document that still has the pane loses nothing). */
export function panes(id, data) {
  return {
    drop: () => html`<${Drop} id=${id} />`,
    history: () => html`<${History} id=${id} data=${data} />`,
    chain: () => null,
  };
}
