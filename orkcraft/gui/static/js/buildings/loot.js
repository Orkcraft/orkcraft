// 📦 Loot Vault: the review checkpoint. Closed: how many carts wait (the ones that need you first), the
// changed files, what the waiting carts cost, what passed last and when. Open, made for the half panel:
// the counters on one line with Accept all (or Accept files) and the rules; a cart that needs you as a
// strip with Look; two tabs — the carts as one flow of cards with what passed folded under them, and the
// changed files of the working tree with what was rejected; a cart or a file opens over them (← back)
// with its acts, what it is first, why it waits and the chain it came through, and a decision opens the
// next cart. In the whole town's width the list stays on the left and the chosen one opens beside it.
// A cart opens in Lake and is edited there (its draft file) before it is accepted; the rules are the
// keeper's, read out in plain words. The decisions are the worker's (core/workers/loot.py).
// Every cart says what it is before it is opened (realm/content.py): a message, a doc, a ticket, code,
// an image, data or text — with where it goes and its first line, or a thumbnail of its picture, which
// the closed card shows too.
import { signal } from "@preact/signals";
import { useEffect, useState } from "preact/hooks";
import { html, cls } from "../html.js";
import { act, say, toast } from "../link.js";
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
const accepting = signal({});     // building id → what Accept all would accept, while it waits for a yes
const dropping = signal({});      // building id → the cart to drop, while it waits for a yes
const tabs = signal({});          // building id → "carts" | "files", the one the person picked

const MARK = { held: "", needs_you: "! ", rework: "↩ " };
const WORD = { held: "held", needs_you: "needs you", rework: "in rework" };
const TONE = { needs_you: "ok-tone-fire", rework: "ok-tone-wait" };
const ORDER = { needs_you: 0, held: 1, rework: 2 };
const CHANGE = { A: "+", M: "~", D: "−" };

/** What a cart is (realm/content.py TYPES): its word and a line pictogram on the 16px grid of js/icons.js. */
const KIND = {
  message: { word: "Message", d: "M2 3h12v8H7l-3 2.5V11H2z" },                                              // speech bubble
  doc: { word: "Doc", d: "M3.5 1.5h6l3 3v10h-9zM9.5 1.5v3h3M5.5 8h5M5.5 10.5h5" },                            // page
  ticket: { word: "Ticket", d: "M1.5 4h13v2.5a1.5 1.5 0 0 0 0 3V12h-13V9.5a1.5 1.5 0 0 0 0-3zM10 4v8" },      // ticket stub
  code: { word: "Code", d: "M5 4.5 1.5 8 5 11.5M11 4.5 14.5 8 11 11.5M9.2 3 6.8 13" },                         // brackets
  image: { word: "Image", d: "M1.5 3h13v10h-13zM1.5 11l4-4 3.5 3.5 2-2 3.5 3.5M10.5 6.2v.1" },               // picture
  data: { word: "Data", d: "M3 3.5C3 2.5 5.2 2 8 2s5 .5 5 1.5v9c0 1-2.2 1.5-5 1.5s-5-.5-5-1.5zM3 3.5C3 4.5 5.2 5 8 5s5-.5 5-1.5M3 8c0 1 2.2 1.5 5 1.5S13 9 13 8" }, // cylinder
  text: { word: "Text", d: "M2.5 4h11M2.5 7h11M2.5 10h11M2.5 13h7" },                                         // lines
};
const kindOf = (t) => KIND[t] || KIND.text;

function KindIcon({ type }) {
  return html`<svg class="gui-type-icon" viewBox="0 0 16 16" width="14" height="14" aria-hidden="true"><path d=${kindOf(type).d} /></svg>`;
}

/** What it is and where it goes: `[icon] MESSAGE · Slack #release`. */
function Kind({ what, className = "" }) {
  const where = what.type === "code" && what.files ? `${what.where ? `${what.where} · ` : ""}${what.files} ${say(what.files === 1 ? "file" : "files")}` : what.where;
  return html`<span class=${cls("loot-kind", `loot-kind--${what.type}`, className)}>
    <${KindIcon} type=${what.type} /><span class="loot-kind__word">${say(kindOf(what.type).word)}</span>
    ${where && html`<span class="loot-kind__where" title=${where}>${where}</span>`}</span>`;
}

const thumbs = signal({});         // "<building>|<cart>|<path>" → a data: URL, "" when there is none

/** A cart's picture, fetched once (`act thumb`); "" while it comes or when there is none. */
function thumb(id, item, path) {
  const key = `${id}|${item}|${path}`;
  if (key in thumbs.value) return thumbs.value[key];
  thumbs.value = { ...thumbs.value, [key]: "" };
  act(id, "thumb", { item, path }).then((url) => { thumbs.value = { ...thumbs.value, [key]: url || "" }; }, () => {});
  return "";
}

function Thumb({ id, item, path, className }) {
  const url = thumb(id, item, path);
  return url ? html`<img class=${className} src=${url} alt=${path} title=${path} loading="lazy" />`
    : html`<span class=${cls(className, "is-empty")} title=${path}><${KindIcon} type="image" /></span>`;
}

function choose(id, kind, key) {
  chosen.value = { ...chosen.value, [id]: { kind, key } };
}

/** The waiting carts in the order the list shows them: the ones that need you first. */
function ordered(queue) {
  return queue.map((it, i) => ({ it, i }))
    .sort((a, b) => (ORDER[a.it.status] ?? 1) - (ORDER[b.it.status] ?? 1) || a.i - b.i).map((x) => x.it);
}

/** After a decision on the open cart, the next one that waits for the person opens; none: back to the list. */
function advance(id, data, done) {
  const list = ordered(data.queue);
  const waits = (x) => x.id !== done && x.status !== "rework";
  const next = list.slice(list.findIndex((x) => x.id === done) + 1).find(waits) || list.find(waits);
  chosen.value = { ...chosen.value, [id]: next ? { kind: "item", key: next.id } : null };
}

/** After a changed file is accepted or rejected, the next one still to review opens; none: back to the list. */
function advanceFile(id, data, done) {
  const list = data.files;
  const waits = (f) => f.path !== done && !f.reviewed;
  const next = list.slice(list.findIndex((f) => f.path === done) + 1).find(waits) || list.find(waits);
  chosen.value = { ...chosen.value, [id]: next ? { kind: "file", key: next.path } : null };
}

/** A cart in Lake: a text cart as its text, a file cart as the file. */
function openCart(id, it) {
  if (it.kind === "file") openInLake({ path: it.value, title: it.title, from: id });
  else openInLake({ text: it.value, title: it.title, from: id });
}

function edit(id, it) {
  act(id, "edit", { item: it.id }).then((d) => openInLake({ path: d.path, title: d.title, from: id }), () => {});
}

/** Accept all asks first, with what it would accept: it lists the held carts, the ones that go out of the town
 *  as soon as they are accepted and the person's edits. */
function askAcceptAll(id) {
  act(id, "accept_all_plan").then((plan) => {
    if (!plan.items.length) { toast(say("No cart waits to be accepted")); return; }
    accepting.value = { ...accepting.value, [id]: plan };
  }, () => {});
}

function AcceptAllDialog({ id }) {
  const plan = accepting.value[id];
  if (!plan) return null;
  const close = () => { accepting.value = { ...accepting.value, [id]: null }; };
  const yes = () => { close(); act(id, "accept_all", { items: plan.items.map((x) => x.id) }).catch(() => {}); };
  const n = plan.items.length;
  const out = plan.items.filter((x) => x.out).length;
  const warn = out > 0 || plan.leaves;
  return html`<${Dialog} title=${`${say("Accept")} ${n} ${say(n === 1 ? "cart" : "carts")}?`} warn=${warn}
      meta=${say("The held carts; not the ones that need you.")}
      text=${out ? `${out} ${say(out === 1 ? "goes out as soon as you accept it: its ork posts it." : "go out as soon as you accept them: their orks post them.")}`
        : plan.leaves ? say("What passes here leaves the town.") : ""}
      onCancel=${close}
      actions=${html`<button class="ok-btn" onClick=${close}>${say("Cancel")}</button>
        <button class="ok-btn primary" onClick=${yes}>${say("Accept")} ${n}</button>`}>
    <ul class="loot-plan">${plan.items.map((x) => html`<li key=${x.id} class="loot-plan__row">
      <${Kind} what=${{ type: x.type, where: "", files: 0 }} />
      <span class="loot-plan__label" title=${x.label}>${x.label}</span>
      ${x.out && html`<span class="loot-plan__mark ok-tone-fire" title=${x.where}>↗ ${x.where || say("goes out")}</span>`}
      ${x.edited && html`<span class="loot-plan__mark ok-tone-wait">${say("your edit")}</span>`}
    </li>`)}</ul>
  </${Dialog}>`;
}

function DropDialog({ id, data }) {
  const iid = dropping.value[id];
  const it = iid && data.queue.find((x) => x.id === iid);
  if (!it) return null;
  const close = () => { dropping.value = { ...dropping.value, [id]: null }; };
  const yes = () => { close(); act(id, "drop", { item: it.id }).then(() => advance(id, data, it.id), () => {}); };
  return html`<${Dialog} title=${`${say("Drop")} “${it.label}”?`} warn=${true} onCancel=${close}
      text=${say("It leaves the queue for good: it is not sent on, nor back to its maker, who hears it was not wanted.")}
      actions=${html`<button class="ok-btn" onClick=${close}>${say("Cancel")}</button>
        <button class="ok-btn danger" onClick=${yes}>${say("Drop")}</button>`} />`;
}

/** Its own small windows over the town: Accept all asked from the closed card waits for its yes there. */
export function overlay() {
  return html`${Object.keys(accepting.value).filter((id) => accepting.value[id]).map((id) => html`<${AcceptAllDialog} key=${id} id=${id} />`)}`;
}

/** The quick actions in its Info (catalog: Accept all, Accept files). */
export function quick(id, action) {
  if (action === "loot.accept_all") { askAcceptAll(id); return true; }
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
  const send = () => act(id, "rework", { item: it.id, tag, reason: note }).then(() => { close(); advance(id, data, it.id); }, () => {});
  return html`<${Dialog} title=${`Send back to ${it.source} — why?`} text=${`Round ${it.attempts + 1}: ${it.label}`} onCancel=${close}
      actions=${html`<button class="ok-btn" onClick=${close}>Cancel</button>
        <button class="ok-btn primary" disabled=${!tag && !note.trim()} onClick=${send}>Send back</button>`}>
    <div class="gui-counters">${data.reasons.map((r) => html`<span key=${r.tag} class=${cls("ok-chip", { "is-on": tag === r.tag })}
      onClick=${() => setTag(tag === r.tag ? "" : r.tag)}>${r.label}</span>`)}</div>
    <p class="ok-dialog__section">What to fix</p>
    <textarea class="ok-input gui-textarea" rows="4" value=${note} onInput=${(e) => setNote(e.target.value)}></textarea>
  </${Dialog}>`;
}

/** A cart's acts. A held one: Accept first. One that needs you ran out of rounds or could not go back, so
 *  the person fixes it: Edit (a file: open it) comes first, Accept as it is after; once edited, Accept
 *  takes the edit. */
function Acts({ id, it, data }) {
  if (it.status === "rework") return html`<span class="ok-tone-muted">with ${it.source} for rework</span>`;
  const accept = (label, primary) => html`<button class=${cls("ok-btn", { primary })}
      onClick=${() => act(id, "accept", { item: it.id }).then(() => advance(id, data, it.id), () => {})}>${say(label)}</button>`;
  const fix = (primary) => it.kind === "file"
    ? html`<button class=${cls("ok-btn", { primary })} onClick=${() => openCart(id, it)}>${say("Open in Lake")}</button>`
    : html`<button class=${cls("ok-btn", { primary })} onClick=${() => edit(id, it)}>${say("Edit in Lake")}</button>`;
  if (it.edited) return html`${accept("Accept your version", true)}${fix(false)}`;
  if (it.status === "needs_you") return html`${fix(true)}${accept("Accept as it is", false)}`;
  return html`${accept("Accept", true)}
    <button class="ok-btn" onClick=${() => { reworking.value = { ...reworking.value, [id]: it.id }; }}>${say("Rework…")}</button>
    ${fix(false)}`;
}

/** A waiting cart as a card: what it is and where it goes, how it is, its title, its first line or its
 *  picture, where it came from and what its chain cost. */
function CartCard({ id, it }) {
  const w = it.what;
  const c = chosen.value[id];
  const on = !!c && c.kind === "item" && c.key === it.id;
  return html`<button class=${cls("loot-card", `loot-card--${w.type}`, { "is-asks": it.status === "needs_you", "is-chosen": on })} title=${it.title}
      onClick=${() => choose(id, "item", it.id)}>
    <span class="loot-card__head"><${Kind} what=${w} />
      <span class=${`loot-card__state ${TONE[it.status] || ""}`}>${MARK[it.status]}${say(WORD[it.status])}${it.edited ? ` · ${say("edited")}` : ""}</span></span>
    <span class="loot-card__title">${it.label}</span>
    ${w.images.length ? html`<span class="loot-card__pics">${w.images.map((p) => html`<${Thumb} key=${p} id=${id} item=${it.id} path=${p} className="loot-card__thumb" />`)}</span>`
      : w.lines.length > 0 && w.lines[0] !== it.label && html`<span class="loot-card__line">${w.lines.filter((l) => l !== it.label).slice(0, 2).join(" · ")}</span>`}
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
      <button class="ok-btn" title=${data.rules.join("\n")} onClick=${() => setRules(true)}>${say("Rules")}</button>
      ${tabOf(id, data) === "files" ? files > 0 && html`<button class="ok-btn primary" onClick=${() => act(id, "accept_files").catch(() => {})}>${say("Accept files")} · ${files}</button>`
        : c.held > 0 && html`<button class="ok-btn primary" onClick=${() => askAcceptAll(id)}>${say("Accept all")} · ${c.held}</button>`}
    </div>
    ${asks && html`<div class="loot-ask">
      <span class="loot-ask__who">! ${say("Needs you")}${c.needs_you > 1 ? ` · ${c.needs_you}` : ""}</span>
      <span class="loot-ask__what" title=${asks.why.join(" · ")}>${asks.label}${asks.why[0] ? ` — ${asks.why[0]}` : ""}</span>
      <button class="ok-btn primary" onClick=${() => choose(id, "item", asks.id)}>${say("Look")}</button>
    </div>`}
    ${rules && html`<${KeeperDialog} id=${id} title="The rules: what passes by itself, what waits for you" onClose=${() => setRules(false)}>
      <p class="ok-dialog__section">${say("Now")}</p>
      <ul class="loot-rules">${data.rules.map((r, i) => html`<li key=${i}>${say(r)}</li>`)}</ul>
      <p class="ok-dialog__section">${say("Change them")}</p>
    </${KeeperDialog}>`}
    <${ReworkDialog} id=${id} data=${data} />
    <${DropDialog} id=${id} data=${data} />
  </div>`;
}

/** Which tab the list shows: the one picked, else the carts — the changed files when no cart is there. */
function tabOf(id, data) {
  const t = tabs.value[id];
  if (t) return t;
  return !data.queue.length && !data.stored.length && (data.files.length || data.rejected.length) ? "files" : "carts";
}

/** The list: the carts (the one that needs you first, what passed folded under them) or the changed files of
 *  the working tree (what was rejected folded under them), a tab each. */
function Queue({ id, data }) {
  const empty = !data.queue.length && !data.files.length && !data.rejected.length && !data.stored.length;
  if (empty) return html`<p class="loot-empty">${say("Nothing waits: a road brings carts here, and the files agents change show up too.")}</p>`;
  const tab = tabOf(id, data);
  const files = data.files.filter((f) => !f.reviewed).length;
  const waiting = data.queue.filter((x) => x.status !== "rework").length;
  const pick = (t) => { tabs.value = { ...tabs.value, [id]: t }; };
  return html`<div class="loot-queue">
    <div class="loot-tabs" role="tablist">
      <button role="tab" aria-selected=${tab === "carts"} class=${cls("ok-tab", { "is-active": tab === "carts" })} onClick=${() => pick("carts")}>
        ${say("Carts")}${waiting ? ` · ${waiting}` : ""}</button>
      <button role="tab" aria-selected=${tab === "files"} class=${cls("ok-tab", { "is-active": tab === "files" })} onClick=${() => pick("files")}>
        ${say("Changed files")}${files ? ` · ${files}` : ""}</button>
    </div>
    ${tab === "carts" ? html`<${Carts} id=${id} data=${data} />` : html`<${Files} id=${id} data=${data} />`}
  </div>`;
}

function Carts({ id, data }) {
  const open = ordered(data.queue);
  return html`
    ${open.length ? html`<div class="loot-flow">${open.map((it) => html`<${CartCard} key=${it.id} id=${id} it=${it} />`)}</div>`
      : html`<p class="loot-empty">${say("No cart waits.")}</p>`}
    ${data.stored.length > 0 && html`<details class="loot-fold">
      <summary><span class="ok-tone-ok">✓ ${data.passed} ${say("passed")}</span>${data.passed_spent && html`<span>${data.passed_spent}</span>`}
        <span class="loot-fold__last">${say("last:")} ${data.stored[0].title} · ${data.stored[0].at}</span></summary>
      <ul class="loot-files">${data.stored.map((x) => html`<li key=${x.index}>
        <button class="loot-file" title=${x.path} onClick=${() => choose(id, "stored", x.index)}>
          <span class="loot-file__path">${x.title}</span><span class="loot-file__meta">${x.at} · ${x.source}${x.spent && ` · ${x.spent}`}</span></button></li>`)}</ul>
    </details>`}`;
}

/** The files agents changed in the working tree (or its `path`), not brought by any cart: each accepted or
 *  rejected (rolled back, kept aside, can be brought back). */
function Files({ id, data }) {
  const files = data.files.filter((f) => !f.reviewed).length;
  const c = chosen.value[id];
  return html`
    <p class="loot-scope">${files ? `${files} ${say("to review in")} ${data.scope}` : data.files.length ? say("All reviewed ✓") : `${say("Nothing changed in")} ${data.scope}`}</p>
    ${data.files.length > 0 && html`<ul class="loot-files">${data.files.map((f) => html`<li key=${f.path}>
      <button class=${cls("loot-file", { "is-done": f.reviewed, "is-chosen": c && c.kind === "file" && c.key === f.path })} title=${f.path}
        onClick=${() => choose(id, "file", f.path)}>
        <span class="loot-file__mark">${f.reviewed ? "✓" : CHANGE[f.change] || "~"}</span><span class="loot-file__path">${f.path}</span></button></li>`)}</ul>`}
    ${data.rejected.length > 0 && html`<details class="loot-fold">
      <summary><span class="ok-tone-error">✗ ${data.rejected.length} ${say("rejected")}</span>
        <span class="loot-fold__last">${say("kept aside, can be brought back")}</span></summary>
      <ul class="loot-files">${data.rejected.map((r) => html`<li key=${r.index}>
        <button class="loot-file" title=${r.path} onClick=${() => choose(id, "rejected", r.index)}>
          <span class="loot-file__mark">✗</span><span class="loot-file__path">${r.path}</span><span class="loot-file__meta">${r.at}</span></button></li>`)}</ul>
    </details>`}`;
}

function Chain({ chain, total }) {
  if (!chain.length) return html`<p class="ok-detail__meta">No ork worked on it.</p>`;
  return html`<table class="loot-chain">
    <thead><tr><th></th><th>${say("Building")}</th><th>${say("Who")}</th><th>${say("Ended")}</th><th>${say("Spent")}</th></tr></thead>
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

/** An open cart: its head and acts, then what it is (the main column), and beside it — under it in the half
 *  panel — why it waits and the chain it came through. */
function ItemDetail({ id, it, data }) {
  const [file, setFile] = useState(null);
  useEffect(() => setFile(null), [it.id]);
  return html`<div class="ok-detail loot-detail">
    <div class="loot-detail__top">
      <div class="ok-detail__head loot-open__title" title=${it.title}>${it.title}</div>
      <p class=${cls("ok-detail__meta", { "ok-tone-fire": it.status === "needs_you" })}>${say(WORD[it.status])} · ${say("from")} ${it.source} · ${it.at}${it.spent ? ` · ${it.spent}` : ""}
        ${it.attempts > 0 ? ` · ${say("reworked")} ${it.attempts}×` : ""}</p>
      <div class="ok-detail__actions">
        <${Acts} id=${id} it=${it} data=${data} />
        <span class="gui-head__spacer"></span>
        ${it.edited && html`<button class="ok-btn" onClick=${() => act(id, "discard_edit", { item: it.id }).catch(() => {})}>${say("Forget your edit")}</button>`}
        ${it.kind !== "file" && html`<button class="ok-btn" onClick=${() => openCart(id, it)}>${say("Open in Lake")}</button>`}
        <button class="ok-btn danger" onClick=${() => { dropping.value = { ...dropping.value, [id]: it.id }; }}>${say("Drop")}</button>
      </div>
      ${it.edited && html`<p class="ok-detail__meta ok-tone-wait">${say("Edited in Lake: Accept takes your version.")}</p>`}
    </div>
    <div class="loot-detail__main">
      <${What} id=${id} it=${it} />
      ${it.branch && html`<p class="ok-detail__section">${say("On")} ${it.branch.name} · ${it.branch.files.length} ${say("files")}</p>
        <ul class="ok-files">${it.branch.files.map((g) => html`<li key=${g.path} class=${cls("ok-file gui-tree__item", { "is-selected": file === g.path })}
          onClick=${() => setFile(g.path)}><span>${CHANGE[g.change] || "~"} ${g.path}</span></li>`)}</ul>
        ${file && html`<${Preview} id=${id} item=${it.id} path=${file} />`}`}
    </div>
    <div class="loot-detail__side">
      <p class="ok-detail__section">${say("Why it waits")}</p>
      <ul class="gui-rows">${it.why.map((w, i) => html`<li key=${i} class="ok-font-status">${w}</li>`)}
        ${it.notes.map((n, i) => html`<li key=${`n${i}`} class="ok-font-status ok-tone-muted">↩ ${n}</li>`)}</ul>
      <p class="ok-detail__section">${say("The chain it came through")}</p>
      <${Chain} chain=${it.chain} total=${it.total} />
    </div>
  </div>`;
}

/** The cart itself, first: what it is and where it goes, its pictures large, then what goes out (a draft
 *  without the ork's report) — the whole cart in Lake. */
function What({ id, it }) {
  const w = it.what;
  return html`<div class="loot-what">
    <${Kind} what=${w} className="loot-what__kind" />
    ${w.images.length > 0 && html`<div class="loot-what__pics">${w.images.map((p) => html`<${Thumb} key=${p} id=${id} item=${it.id} path=${p} className="loot-what__pic" />`)}</div>`}
    ${w.html ? html`<div class="gui-prose loot-what__body" dangerouslySetInnerHTML=${{ __html: w.html }}></div>`
      : (it.kind !== "file" || !w.images.length) && html`<pre class="gui-pre loot-what__body">${w.body}</pre>`}
    ${w.cut && html`<p class="ok-detail__meta">${say("… the rest in Lake")}</p>`}
    ${it.kind !== "file" && w.body.trim() !== it.value.trim() && html`<details class="loot-fold">
      <summary>${say("The whole cart, with the ork's report")}</summary>
      <pre class="gui-pre">${it.value}${it.cut ? "\n… (the rest in Lake)" : ""}</pre></details>`}
  </div>`;
}

/** The cart, file or passed one chosen, over the queue: ← back to it; null when nothing is chosen. */
function Open({ id, data }) {
  const body = Cart({ id, data });
  if (!body) return null;
  const back = () => { chosen.value = { ...chosen.value, [id]: null }; };
  const esc = (e) => {                     // a dialog over it (Rework, Drop) takes Escape first
    if (e.key === "Escape" && !document.querySelector(".gui-modal")) { e.stopPropagation(); back(); }
  };
  const c = chosen.value[id];
  const toFiles = c && (c.kind === "file" || c.kind === "rejected");
  return html`<div class="loot-open" onKeyDown=${esc}>
    <button class="ok-btn loot-open__back" onClick=${back}>← ${say(toFiles ? "Changed files" : "All carts")}</button>
    ${body}
  </div>`;
}

/** The list and, over it, what was opened; in the whole town's width (a full panel) the two side by side. */
function QueuePane({ id, data }) {
  const open = Open({ id, data });
  return html`<div class=${cls("loot-split", { "has-open": !!open })}>
    <div class="loot-split__list"><${Queue} id=${id} data=${data} /></div>
    <div class="loot-split__open">${open || html`<p class="loot-empty">${say("Choose a cart or a file on the left.")}</p>`}</div>
  </div>`;
}

function Cart({ id, data }) {
  const c = chosen.value[id];
  if (c && c.kind === "item") {
    const it = data.queue.find((x) => x.id === c.key);
    if (it) return html`<${ItemDetail} id=${id} it=${it} data=${data} />`;
  }
  if (c && c.kind === "file" && data.files.some((f) => f.path === c.key)) {
    const f = data.files.find((x) => x.path === c.key);
    return html`<div class="ok-detail">
      <div class="ok-detail__head loot-open__title" title=${f.path}>${f.path}</div>
      <div class="ok-detail__actions">
        ${!f.reviewed && html`<button class="ok-btn primary" onClick=${() => act(id, "file_accept", { path: f.path }).then(() => advanceFile(id, data, f.path), () => {})}>${say("Accept")}</button>`}
        <button class="ok-btn" onClick=${() => act(id, "file_reject", { path: f.path }).then(() => advanceFile(id, data, f.path), () => {})}>${say("Reject")}</button>
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

/** On the closed card, the cart that waits first — what it is, where it goes, its title — and the waiting
 *  carts' pictures, small. */
function Glance({ id, g, pics }) {
  return html`<div class="loot-glance">
    ${g && html`<div class="loot-glance__text"><${Kind} what=${{ type: g.type, where: g.where, files: 0 }} />
      <span class="loot-glance__title" title=${g.label}>${g.label}</span></div>`}
    ${pics.length > 0 && html`<div class="loot-glance__pics">${pics.map((p) => html`<${Thumb} key=${`${p.id}|${p.path}`} id=${id} item=${p.id} path=${p.path} className="loot-glance__thumb" />`)}</div>`}
  </div>`;
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
    ${(c.first || (c.pics || []).length > 0) && html`<${Glance} id=${b.id} g=${c.first} pics=${c.pics || []} />`}
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
