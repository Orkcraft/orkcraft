// 📦 Loot Vault: the review checkpoint. Closed: how many carts wait (the ones that need you first), the
// changed files, what the waiting carts cost, what passed last and when. Open, made for the half panel:
// the counters on one line with Accept all, Accept files and the rules; a cart that needs you as a strip
// with Look; the waiting carts as one flow of cards, the changed files as rows, what passed and what was
// rejected folded to a line each; a cart or a file opens over them (← back) with its acts, why it waits
// and the chain it came through. A cart opens in Lake and is edited there (its draft file) before it is
// accepted; the rules are the keeper's. The decisions are the worker's (core/workers/loot.py).
import { signal } from "@preact/signals";
import { useEffect, useState } from "preact/hooks";
import { html, cls } from "../html.js";
import { act, say } from "../link.js";
import { Dialog } from "../dialog.js";
import { openInLake } from "../lake.js";
import { KeeperDialog } from "../keeper.js";

const sheet = new URL("./loot.css", import.meta.url).href;
if (!document.querySelector(`link[href="${sheet}"]`)) {
  const link = document.createElement("link");
  link.rel = "stylesheet";
  link.href = sheet;
  document.head.appendChild(link);
}

const chosen = signal({});        // building id → {kind: item | file | rejected | stored, key}
const reworking = signal({});     // building id → the item sent back, while its dialog is open

const MARK = { held: "", needs_you: "! ", rework: "↩ " };
const WORD = { held: "held", needs_you: "needs you", rework: "in rework" };
const TONE = { needs_you: "ok-tone-fire", rework: "ok-tone-wait" };
const ORDER = { needs_you: 0, held: 1, rework: 2 };
const CHANGE = { A: "+", M: "~", D: "−" };

function choose(id, kind, key) {
  chosen.value = { ...chosen.value, [id]: { kind, key } };
}

/** A cart in Lake: a text cart as its text, a file cart as the file. */
function openCart(id, it) {
  if (it.kind === "file") openInLake({ path: it.value, title: it.title, from: id });
  else openInLake({ text: it.value, title: it.title, from: id });
}

function edit(id, it) {
  act(id, "edit", { item: it.id }).then((d) => openInLake({ path: d.path, title: d.title, from: id }), () => {});
}

/** The quick actions in its Info (catalog: Accept all, Accept files). */
export function quick(id, action) {
  if (action === "loot.accept_all") { act(id, "accept_all").catch(() => {}); return true; }
  if (action === "generator.accept_all") { act(id, "accept_files").catch(() => {}); return true; }
  return false;
}

function ReworkDialog({ id, data }) {
  const iid = reworking.value[id];
  const it = iid && data.queue.find((x) => x.id === iid);
  const [tag, setTag] = useState("");
  const [note, setNote] = useState("");
  useEffect(() => { setTag(""); setNote(""); }, [iid]);
  if (!it) return null;
  const close = () => { reworking.value = { ...reworking.value, [id]: null }; };
  const send = () => act(id, "rework", { item: it.id, tag, reason: note }).then(close, () => {});
  return html`<${Dialog} title=${`Send back to ${it.source} — why?`} text=${`Round ${it.attempts + 1}: ${it.label}`} onCancel=${close}
      actions=${html`<button class="ok-btn" onClick=${close}>Cancel</button>
        <button class="ok-btn primary" disabled=${!tag && !note.trim()} onClick=${send}>Send back</button>`}>
    <div class="gui-counters">${data.reasons.map((r) => html`<span key=${r.tag} class=${cls("ok-chip", { "is-on": tag === r.tag })}
      onClick=${() => setTag(tag === r.tag ? "" : r.tag)}>${r.label}</span>`)}</div>
    <p class="ok-dialog__section">What to fix</p>
    <textarea class="ok-input gui-textarea" rows="4" value=${note} onInput=${(e) => setNote(e.target.value)}></textarea>
  </${Dialog}>`;
}

function Acts({ id, it }) {
  if (it.status === "rework") return html`<span class="ok-tone-muted">with ${it.source} for rework</span>`;
  return html`<button class="ok-btn primary" onClick=${() => act(id, "accept", { item: it.id }).catch(() => {})}>
      ${it.edited ? "Accept your version" : "Accept"}</button>
    ${it.status === "held" && html`<button class="ok-btn" onClick=${() => { reworking.value = { ...reworking.value, [id]: it.id }; }}>Rework…</button>`}`;
}

/** A waiting cart as a card: how it is, its title, where it came from and what its chain cost. */
function CartCard({ id, it }) {
  return html`<button class=${cls("loot-card", { "is-asks": it.status === "needs_you" })} title=${it.title}
      onClick=${() => choose(id, "item", it.id)}>
    <span class=${`loot-card__state ${TONE[it.status] || ""}`}>${MARK[it.status]}${say(WORD[it.status])}${it.edited ? ` · ${say("edited")}` : ""}</span>
    <span class="loot-card__title">${it.label}</span>
    <span class="loot-card__foot"><span class="loot-card__from">${it.source}</span>
      ${it.attempts > 0 && html`<span>↩${it.attempts}</span>`}
      ${it.spent && html`<span class="loot-card__cost">${it.spent}</span>`}</span>
  </button>`;
}

/** The head: the counters on one line, Accept all, Accept files and the rules; a cart that needs you as a strip. */
function Head({ id, data }) {
  const [rules, setRules] = useState(false);
  const c = data.counts;
  const files = data.files.filter((f) => !f.reviewed).length;
  const asks = data.queue.find((x) => x.status === "needs_you");
  return html`<div>
    <div class="loot-head">
      ${data.error ? html`<span class="ok-tone-error loot-head__err" title=${data.error}>✗ ${data.error}</span>` : html`
        <span><b>${c.held + c.needs_you}</b> ${say("to review")}</span>
        ${c.rework > 0 && html`<span><b>${c.rework}</b> ${say("in rework")}</span>`}
        ${data.waiting_cost && html`<span><b>${data.waiting_cost}</b> ${say("waiting")}</span>`}
        <span><b>${files}</b> ${say(files === 1 ? "file to review" : "files to review")}</span>
        <span><b>${data.passed}</b> ${say("passed")}</span>`}
      <span class="gui-head__spacer"></span>
      <button class="ok-btn" title=${`${say("Review")}: ${data.review}`} onClick=${() => setRules(true)}>${say("Rules")}</button>
      ${files > 0 && html`<button class="ok-btn" onClick=${() => act(id, "accept_files").catch(() => {})}>${say("Accept files")}</button>`}
      ${c.held > 0 && html`<button class="ok-btn primary" onClick=${() => act(id, "accept_all").catch(() => {})}>${say("Accept all")}</button>`}
    </div>
    ${asks && html`<div class="loot-ask">
      <span class="loot-ask__who">! ${say("Needs you")}${c.needs_you > 1 ? ` · ${c.needs_you}` : ""}</span>
      <span class="loot-ask__what" title=${asks.why.join(" · ")}>${asks.label}${asks.why[0] ? ` — ${asks.why[0]}` : ""}</span>
      <button class="ok-btn primary" onClick=${() => choose(id, "item", asks.id)}>${say("Look")}</button>
    </div>`}
    ${rules && html`<${KeeperDialog} id=${id} title="The rules: what passes by itself, what waits for you" onClose=${() => setRules(false)} />`}
    <${ReworkDialog} id=${id} data=${data} />
  </div>`;
}

/** The waiting carts as one flow, the one that needs you first; the changed files as rows; what passed and
 *  what was rejected folded to a line each. */
function Queue({ id, data }) {
  const open = data.queue.map((it, i) => ({ it, i }))
    .sort((a, b) => (ORDER[a.it.status] ?? 1) - (ORDER[b.it.status] ?? 1) || a.i - b.i).map((x) => x.it);
  const empty = !data.queue.length && !data.files.length && !data.rejected.length && !data.stored.length;
  if (empty) return html`<p class="loot-empty">${say("Nothing waits: a road brings carts here, and the files agents change show up too.")}</p>`;
  const files = data.files.filter((f) => !f.reviewed).length;
  return html`<div class="loot-queue">
    ${open.length ? html`<div class="loot-flow">${open.map((it) => html`<${CartCard} key=${it.id} id=${id} it=${it} />`)}</div>`
      : html`<p class="loot-empty">${say("No cart waits.")}</p>`}
    ${data.files.length > 0 && html`<div>
      <h3 class="ok-detail__section">${say("Changed files")} · ${files ? `${files} ${say("to review in")} ${data.scope}` : say("all reviewed ✓")}</h3>
      <ul class="loot-files">${data.files.map((f) => html`<li key=${f.path}>
        <button class=${cls("loot-file", { "is-done": f.reviewed })} title=${f.path} onClick=${() => choose(id, "file", f.path)}>
          <span class="loot-file__mark">${f.reviewed ? "✓" : CHANGE[f.change] || "~"}</span><span class="loot-file__path">${f.path}</span></button></li>`)}</ul>
    </div>`}
    ${data.stored.length > 0 && html`<details class="loot-fold">
      <summary><span class="ok-tone-ok">✓ ${data.passed} ${say("passed")}</span>${data.passed_spent && html`<span>${data.passed_spent}</span>`}
        <span class="loot-fold__last">${say("last:")} ${data.stored[0].title} · ${data.stored[0].at}</span></summary>
      <ul class="loot-files">${data.stored.map((x) => html`<li key=${x.index}>
        <button class="loot-file" title=${x.path} onClick=${() => choose(id, "stored", x.index)}>
          <span class="loot-file__path">${x.title}</span><span class="loot-file__meta">${x.at} · ${x.source}${x.spent && ` · ${x.spent}`}</span></button></li>`)}</ul>
    </details>`}
    ${data.rejected.length > 0 && html`<details class="loot-fold">
      <summary><span class="ok-tone-error">✗ ${data.rejected.length} ${say("rejected")}</span>
        <span class="loot-fold__last">${say("kept aside, can be brought back")}</span></summary>
      <ul class="loot-files">${data.rejected.map((r) => html`<li key=${r.index}>
        <button class="loot-file" title=${r.path} onClick=${() => choose(id, "rejected", r.index)}>
          <span class="loot-file__mark">✗</span><span class="loot-file__path">${r.path}</span><span class="loot-file__meta">${r.at}</span></button></li>`)}</ul>
    </details>`}
  </div>`;
}

function Chain({ chain, total }) {
  if (!chain.length) return html`<p class="ok-detail__meta">No ork worked on it.</p>`;
  return html`<table class="gui-diff">
    <tbody>${chain.map((h, i) => html`<tr key=${i}><td>${i + 1}</td><td>${h.building}</td><td>${h.who}</td>
      <td>${h.outcome}</td><td>${h.spent || "—"}</td></tr>`)}</tbody>
  </table>${total && chain.length > 1 && html`<p class="ok-detail__meta">The chain: ${total}</p>`}`;
}

function Preview({ id, item, path }) {
  const [shown, setShown] = useState(null);
  useEffect(() => {
    setShown(null);
    act(id, "preview", item ? { item, path } : { path }).then(setShown, () => setShown({ text: "" }));
  }, [id, item, path]);
  if (!shown) return html`<p class="ok-tone-muted">Looking…</p>`;
  return html`<pre class="gui-pre">${shown.text}</pre>`;
}

function ItemDetail({ id, it }) {
  const [file, setFile] = useState(null);
  useEffect(() => setFile(null), [it.id]);
  return html`<div class="ok-detail">
    <div class="ok-detail__head loot-open__title" title=${it.title}>${it.title}</div>
    <p class=${cls("ok-detail__meta", { "ok-tone-fire": it.status === "needs_you" })}>${WORD[it.status]} · from ${it.source} · ${it.at}${it.spent ? ` · ${it.spent}` : ""}
      ${it.attempts > 0 ? ` · reworked ${it.attempts}×` : ""}</p>
    <div class="ok-detail__actions">
      <${Acts} id=${id} it=${it} />
      ${it.status !== "rework" && it.kind !== "file" && html`<button class="ok-btn" onClick=${() => edit(id, it)}>${say("Edit in Lake")}</button>`}
      <span class="gui-head__spacer"></span>
      ${it.edited && html`<button class="ok-btn" onClick=${() => act(id, "discard_edit", { item: it.id }).catch(() => {})}>Forget your edit</button>`}
      <button class="ok-btn" onClick=${() => openCart(id, it)}>${say("Open in Lake")}</button>
      <button class="ok-btn danger" onClick=${() => act(id, "drop", { item: it.id }).catch(() => {})}>Drop</button>
    </div>
    ${it.edited && html`<p class="ok-detail__meta ok-tone-wait">Edited in Lake: Accept takes your version.</p>`}
    <p class="ok-detail__section">Why it waits</p>
    <ul class="gui-rows">${it.why.map((w, i) => html`<li key=${i} class="ok-font-status">${w}</li>`)}
      ${it.notes.map((n, i) => html`<li key=${`n${i}`} class="ok-font-status ok-tone-muted">↩ ${n}</li>`)}</ul>
    <p class="ok-detail__section">The chain it came through</p>
    <${Chain} chain=${it.chain} total=${it.total} />
    ${it.branch && html`<p class="ok-detail__section">On ${it.branch.name} · ${it.branch.files.length} files</p>
      <ul class="ok-files">${it.branch.files.map((g) => html`<li key=${g.path} class=${cls("ok-file gui-tree__item", { "is-selected": file === g.path })}
        onClick=${() => setFile(g.path)}><span>${CHANGE[g.change] || "~"} ${g.path}</span></li>`)}</ul>
      ${file && html`<${Preview} id=${id} item=${it.id} path=${file} />`}`}
    <p class="ok-detail__section">${say(it.kind === "file" ? "The file" : "The cart")}</p>
    <pre class="gui-pre">${it.value}${it.cut ? "\n… (the rest in Lake)" : ""}</pre>
  </div>`;
}

/** The cart, file or passed one chosen, over the queue: ← back to it; null when nothing is chosen. */
function Open({ id, data }) {
  const body = Cart({ id, data });
  if (!body) return null;
  const back = () => { chosen.value = { ...chosen.value, [id]: null }; };
  return html`<div class="loot-open" onKeyDown=${(e) => { if (e.key === "Escape") { e.stopPropagation(); back(); } }}>
    <button class="ok-btn loot-open__back" onClick=${back}>← ${say("All carts")} · ${data.queue.length}</button>
    ${body}
  </div>`;
}

function QueuePane({ id, data }) {
  return Open({ id, data }) || html`<${Queue} id=${id} data=${data} />`;
}

function Cart({ id, data }) {
  const c = chosen.value[id];
  if (c && c.kind === "item") {
    const it = data.queue.find((x) => x.id === c.key);
    if (it) return html`<${ItemDetail} id=${id} it=${it} />`;
  }
  if (c && c.kind === "file" && data.files.some((f) => f.path === c.key)) {
    const f = data.files.find((x) => x.path === c.key);
    return html`<div class="ok-detail">
      <div class="ok-detail__head loot-open__title" title=${f.path}>${f.path}</div>
      <div class="ok-detail__actions">
        ${!f.reviewed && html`<button class="ok-btn primary" onClick=${() => act(id, "file_accept", { path: f.path }).catch(() => {})}>Accept</button>`}
        <button class="ok-btn" onClick=${() => act(id, "file_reject", { path: f.path }).catch(() => {})}>Reject</button>
        ${f.change !== "D" && html`<button class="ok-btn" onClick=${() => openInLake({ path: f.path, title: f.path, from: id })}>${say("Open in Lake")}</button>`}
      </div>
      <${Preview} id=${id} path=${f.path} />
    </div>`;
  }
  if (c && c.kind === "rejected") {
    const r = data.rejected.find((x) => x.index === c.key);
    if (r) return html`<div class="ok-detail"><div class="ok-detail__head loot-open__title" title=${r.path}>${r.path}</div>
      <p class="ok-detail__meta">rejected ${r.at}: rolled back, its content kept aside.</p>
      <div class="ok-detail__actions"><button class="ok-btn primary" onClick=${() => act(id, "file_restore", { index: r.index }).catch(() => {})}>Bring it back</button></div></div>`;
  }
  if (c && c.kind === "stored") {
    const x = data.stored.find((s) => s.index === c.key);
    if (x) return html`<div class="ok-detail"><div class="ok-detail__head loot-open__title" title=${x.title}>${x.title}</div>
      <p class="ok-detail__meta">passed ${x.at} · from ${x.source} · ${x.path}</p>
      <div class="ok-detail__actions"><button class="ok-btn" onClick=${() => openInLake({ path: x.path, title: x.title, from: id })}>${say("Open in Lake")}</button></div>
      <p class="ok-detail__section">The chain it came through</p>
      <${Chain} chain=${x.chain} total=${""} /></div>`;
  }
  return null;
}

/** Closed: the headline is how many carts wait (fire when one needs you), else that all is reviewed; under it
 *  the changed files and what the waiting carts cost; the foot what passed last and when. */
export function card(b) {
  const c = b.card;
  if (!c) return null;
  if (c.error) return html`<div class="gui-hut__body-in"><div class="gui-hut__big ok-tone-error">✗<small>${say("cannot read the vault")}</small></div>
    <div class="gui-hut__text" title=${c.error}>${c.error}</div></div>`;
  return html`<div class="gui-hut__body-in">
    ${c.to_review ? html`<div class="gui-hut__big">${c.to_review}<small>${say("to review")}${c.needs_you ? html` · <span class="ok-tone-fire">! ${c.needs_you} ${say("need you")}</span>` : ""}</small></div>`
      : html`<div class="gui-hut__big ok-tone-ok">✓<small>${say("nothing waits for you")}</small></div>`}
    ${(c.files > 0 || c.cost) && html`<div class="gui-hut__text">${c.files > 0 && html`<b>${c.files}</b> ${say(c.files === 1 ? "file to review" : "files to review")}`}
      ${c.files > 0 && c.cost ? " · " : ""}${c.cost && html`<b>${c.cost}</b> ${say("waiting")}`}</div>`}
    ${c.latest ? html`<div class="gui-hut__foot"><span><span class="ok-tone-ok">✓</span> ${c.latest}</span>
        ${c.at && html`<span class="gui-hut__when">${c.at}</span>`}</div>`
      : html`<div class="gui-hut__foot"><span>${say("Nothing passed yet")}</span></div>`}
  </div>`;
}

/** The window by its UI document (design/buildings/loot.json). `cart` shows nothing of its own: a cart opens
 *  over the queue (an older document that still has the pane loses nothing). */
export function panes(id, data) {
  return {
    head: () => html`<${Head} id=${id} data=${data} />`,
    queue: () => html`<${QueuePane} id=${id} data=${data} />`,
    cart: () => null,
  };
}
