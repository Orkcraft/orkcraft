// 📦 Loot Vault: the review checkpoint. Closed: how many carts wait, what passed, what the waiting
// carts cost. Command: the queue (what, from where, what the chain cost) with Accept / Rework per
// cart; Accept all and Accept files are the quick actions. Full: the queue, the changed files and what
// passed; the chosen cart with the chain it came through, step by step. A cart opens in Lake and is
// edited there (its draft file) before it is accepted; the rules are the keeper's. The decisions are
// the worker's (core/workers/loot.py).
import { signal } from "@preact/signals";
import { useEffect, useState } from "preact/hooks";
import { html, cls } from "../html.js";
import { act, say } from "../link.js";
import { Dialog } from "../dialog.js";
import { openInLake } from "../lake.js";
import { KeeperDialog } from "../keeper.js";

const chosen = signal({});        // building id → {kind: item | file | rejected | stored, key}
const reworking = signal({});     // building id → the item sent back, while its dialog is open

const MARK = { held: "⏸", needs_you: "🔥", rework: "↩" };
const WORD = { held: "held", needs_you: "needs you", rework: "in rework" };
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
  return html`<button class="ok-act" onClick=${() => act(id, "accept", { item: it.id }).catch(() => {})}>
      <span class="ok-act__label">${it.edited ? "Accept your version" : "Accept"}</span></button>
    ${it.status === "held" && html`<button class="ok-act" onClick=${() => { reworking.value = { ...reworking.value, [id]: it.id }; }}>
      <span class="ok-act__label">Rework</span></button>`}`;
}

function Row({ id, it, sel }) {
  return html`<li key=${it.id} class=${cls("ok-item", { "is-selected": sel, "is-alert": it.status === "needs_you" })}
      onClick=${() => choose(id, "item", it.id)}>
    <span>${MARK[it.status]}</span><span>${it.label}</span>
    <span class="meta">${it.source}${it.spent && ` · ${it.spent}`}${it.attempts > 0 ? ` · ↩${it.attempts}` : ""}</span>
  </li>`;
}

function headLine(data) {
  if (data.error) return data.error;
  const c = data.counts;
  const bits = [];
  if (c.held) bits.push(`${c.held} held`);
  if (c.needs_you) bits.push(`${c.needs_you} need you`);
  if (c.rework) bits.push(`${c.rework} in rework`);
  if (!bits.length) bits.push("nothing held");
  if (data.waiting_cost) bits.push(`waiting carts cost ${data.waiting_cost}`);
  const files = data.files.filter((f) => !f.reviewed).length;
  bits.push(files ? `${files} files to review in ${data.scope}` : data.files.length ? "all files reviewed ✓" : "no changed files");
  bits.push(`passed: ${data.passed}`);
  return say(bits.join(" · "));
}

function Head({ id, data }) {
  const [rules, setRules] = useState(false);
  const held = data.counts.held > 0, files = data.files.some((f) => !f.reviewed);
  return html`<div class="gui-head">
    <span class=${cls("gui-head__what", { "ok-tone-error": !!data.error, "ok-tone-fire": data.counts.needs_you > 0 })}>${headLine(data)}</span>
    <span class="gui-head__spacer"></span>
    ${held && html`<button class="ok-act" onClick=${() => act(id, "accept_all").catch(() => {})}><span class="ok-act__label">Accept all</span></button>`}
    ${files && html`<button class="ok-act" onClick=${() => act(id, "accept_files").catch(() => {})}><span class="ok-act__label">Accept files</span></button>`}
    <button class="ok-act" title=${`Review: ${data.review}`} onClick=${() => setRules(true)}><span class="ok-act__label">Rules</span></button>
    ${rules && html`<${KeeperDialog} id=${id} title="The rules: what passes by itself, what waits for you" onClose=${() => setRules(false)} />`}
    <${ReworkDialog} id=${id} data=${data} />
  </div>`;
}

function Section({ title, children }) {
  return html`<li class="ok-item is-disabled"><b>${title}</b></li>${children}`;
}

function Queue({ id, data }) {
  const c = chosen.value[id] || {};
  const is = (kind, key) => c.kind === kind && c.key === key;
  const empty = !data.queue.length && !data.files.length && !data.rejected.length && !data.stored.length;
  if (empty) return html`<p class="ok-tone-muted">Nothing held, changed or passed yet.</p>`;
  return html`<ul class="ok-list__items">
    ${data.queue.length > 0 && html`<${Section} title=${`Queue · ${data.queue.length}`}>
      ${data.queue.map((it) => html`<${Row} key=${it.id} id=${id} it=${it} sel=${is("item", it.id)} />`)}</${Section}>`}
    ${data.files.length > 0 && html`<${Section} title=${`Files · ${data.files.length}`}>
      ${data.files.map((f) => html`<li key=${f.path} class=${cls("ok-item", { "is-selected": is("file", f.path), "is-disabled": f.reviewed })}
          onClick=${() => choose(id, "file", f.path)}>
        <span>${f.reviewed ? "✓" : "*"}</span><span>${CHANGE[f.change] || "~"} ${f.path}</span></li>`)}</${Section}>`}
    ${data.rejected.length > 0 && html`<${Section} title=${`Rejected · ${data.rejected.length}`}>
      ${data.rejected.map((r) => html`<li key=${r.index} class=${cls("ok-item", { "is-selected": is("rejected", r.index) })}
          onClick=${() => choose(id, "rejected", r.index)}><span>✗</span><span>${r.path}</span></li>`)}</${Section}>`}
    ${data.stored.length > 0 && html`<${Section} title=${`Passed · ${data.passed}${data.passed_spent ? ` · ${data.passed_spent}` : ""}`}>
      ${data.stored.map((x) => html`<li key=${x.index} class=${cls("ok-item", { "is-selected": is("stored", x.index) })}
          onClick=${() => choose(id, "stored", x.index)}>
        <span>${x.title}</span><span class="meta">${x.at} · ${x.source}${x.spent && ` · ${x.spent}`}</span></li>`)}</${Section}>`}
  </ul>`;
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
    <div class="ok-detail__head">${it.title}</div>
    <p class=${cls("ok-detail__meta", { "ok-tone-fire": it.status === "needs_you" })}>${WORD[it.status]} · from ${it.source} · ${it.at}
      ${it.attempts > 0 ? ` · reworked ${it.attempts}×` : ""}</p>
    <div class="ok-detail__actions">
      <${Acts} id=${id} it=${it} />
      ${it.status !== "rework" && it.kind !== "file" && html`<button class="ok-act" onClick=${() => edit(id, it)}>
        <span class="ok-act__label">Edit in Lake</span></button>`}
      ${it.edited && html`<button class="ok-act" onClick=${() => act(id, "discard_edit", { item: it.id }).catch(() => {})}>
        <span class="ok-act__label">Forget your edit</span></button>`}
      <button class="ok-act" onClick=${() => openCart(id, it)}><span class="ok-act__label">Open in Lake</span></button>
      <button class="ok-act" onClick=${() => act(id, "drop", { item: it.id }).catch(() => {})}><span class="ok-act__label">Drop</span></button>
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

function Cart({ id, data }) {
  const c = chosen.value[id];
  if (c && c.kind === "item") {
    const it = data.queue.find((x) => x.id === c.key);
    if (it) return html`<${ItemDetail} id=${id} it=${it} />`;
  }
  if (c && c.kind === "file" && data.files.some((f) => f.path === c.key)) {
    const f = data.files.find((x) => x.path === c.key);
    return html`<div class="ok-detail">
      <div class="ok-detail__head">${f.path}</div>
      <div class="ok-detail__actions">
        ${!f.reviewed && html`<button class="ok-act" onClick=${() => act(id, "file_accept", { path: f.path }).catch(() => {})}>
          <span class="ok-act__label">Accept</span></button>`}
        <button class="ok-act" onClick=${() => act(id, "file_reject", { path: f.path }).catch(() => {})}><span class="ok-act__label">Reject</span></button>
        ${f.change !== "D" && html`<button class="ok-act" onClick=${() => openInLake({ path: f.path, title: f.path, from: id })}>
          <span class="ok-act__label">Open in Lake</span></button>`}
      </div>
      <${Preview} id=${id} path=${f.path} />
    </div>`;
  }
  if (c && c.kind === "rejected") {
    const r = data.rejected.find((x) => x.index === c.key);
    if (r) return html`<div class="ok-detail"><div class="ok-detail__head">${r.path}</div>
      <p class="ok-detail__meta">rejected ${r.at}: rolled back, its content kept aside.</p>
      <div class="ok-detail__actions"><button class="ok-act" onClick=${() => act(id, "file_restore", { index: r.index }).catch(() => {})}>
        <span class="ok-act__label">Bring it back</span></button></div></div>`;
  }
  if (c && c.kind === "stored") {
    const x = data.stored.find((s) => s.index === c.key);
    if (x) return html`<div class="ok-detail"><div class="ok-detail__head">${x.title}</div>
      <p class="ok-detail__meta">passed ${x.at} · from ${x.source} · ${x.path}</p>
      <div class="ok-detail__actions"><button class="ok-act" onClick=${() => openInLake({ path: x.path, title: x.title, from: id })}>
        <span class="ok-act__label">Open in Lake</span></button></div>
      <p class="ok-detail__section">The chain it came through</p>
      <${Chain} chain=${x.chain} total=${""} /></div>`;
  }
  return html`<p class="ok-tone-muted">Pick a cart, a file or what passed.</p>`;
}

/** Closed: what came of the newest cart that passed; `N to review` or `all reviewed ✓`, `passed: N` and
 * what the waiting carts cost. */
export function card(b) {
  const c = b.card;
  if (!c) return null;
  if (c.error) return html`<span class="ok-tone-error">${c.error}</span>`;
  const first = c.to_review
    ? html`<b>${c.to_review}</b> to review${c.needs_you ? html` · <span class="ok-tone-fire">${c.needs_you} need you</span>` : ""}`
    : c.files ? html`<b>${c.files}</b> files to review` : html`all reviewed <span class="ok-tone-ok">✓</span>`;
  return html`${c.latest && html`<div class="ok-tone-ok"><b>✓ ${c.latest}</b></div>`}<div>${first}</div>
    <div>passed: <b>${c.passed}</b>${c.cost && html` · <span class="ok-tone-wait">${c.cost}</span> waiting`}</div>`;
}

/** Command: the queue with Accept / Rework per cart; a click on a cart opens it in Lake. */

export function panes(id, data) {
  return {
    head: () => html`<${Head} id=${id} data=${data} />`,
    queue: () => html`<${Queue} id=${id} data=${data} />`,
    cart: () => html`<${Cart} id=${id} data=${data} />`,
  };
}
