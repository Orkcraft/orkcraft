// 🗼 Watchtower: what comes in from outside (core/workers/watchtower.py). Closed: how many are new, a
// counter per source (a failing one marked), the newest message in the foot. Open, made for the half
// panel: a chip per source with what is new in it (it filters the feed), when it last looked, Open new,
// Read all and Check now; a failing source says why; the feed one line per signal, a signal opening over
// it to be read in full (← back); the sources and the intent open the same way, from Sources & intent, and so
// does Add a source (+), which a tower with no source opens on (watchtower_add.js) — never a dialog.
import { signal } from "@preact/signals";
import { useEffect, useState } from "preact/hooks";
import { html, cls } from "../html.js";
import { act, say } from "../link.js";
import { askKeeper } from "../keeper.js";
import { Dialog } from "../dialog.js";
import { openBuilding } from "../windows.js";
import { AddPane, Glyph, editSource } from "./watchtower_add.js";
import { Places } from "./watchtower_places.js";

const source = signal({});         // building id → the source whose feed shows ("" all)
const tab = signal({});            // building id → "signals" | "settings" | "add" (over the feed); none: "add" while no source
const opened = signal({});         // building id → the key of the signal read over the feed

const read = (id, key) => {
  opened.value = { ...opened.value, [id]: key };
  return act(id, "read", { key }).catch(() => {});
};

const sheet = new URL("./watchtower.css", import.meta.url).href;
if (typeof document !== "undefined" && !document.querySelector(`link[href="${sheet}"]`)) {
  const link = document.createElement("link");
  link.rel = "stylesheet";
  link.href = sheet;
  document.head.appendChild(link);
}

// -- closed ------------------------------------------------------------------------------------------------

/** Closed: the headline is how many are new; under it a counter per source — `gmail 3`, `slack 99+`,
 *  `jira ✗ ERR`; more than four fold into `+N more` — and the foot the newest message (from, subject,
 *  time), marked when it just arrived. */
export function card(b) {
  const c = b.card;
  if (!c) return null;
  if (!c.sources.length) {
    return html`<div class="gui-hut__body-in">
      <div class="gui-hut__big">${say("No sources")}<small>${say("yet")}</small></div>
      <button class="ok-btn primary gui-tower__add" onPointerDown=${(e) => e.stopPropagation()}
        onClick=${(e) => { e.stopPropagation(); tab.value = { ...tab.value, [b.id]: "add" }; openBuilding(b.id, "work"); }}>+ Add a source</button>
      <div class="gui-hut__text ok-tone-muted">${say("Mail, GitHub, Slack, Jira, Figma…")}</div>
    </div>`;
  }
  const s = (c.latest || [])[0];
  const n = c.new ?? 0;
  return html`<div class="gui-hut__body-in gui-tower">
    ${n ? html`<div class="gui-hut__big">${n}<small>${say("new")}${c.failing ? html` · <span class="ok-tone-error">✗ ${c.failing} ${say("failing")}</span>` : ""}</small></div>`
      : html`<div class="gui-hut__big"><span class="ok-tone-ok">✓</span> ${say("All read")}${c.failing ? html`<small><span class="ok-tone-error">✗ ${c.failing} ${say("failing")}</span></small>` : ""}</div>`}
    <div class="gui-hut__text">
      ${c.sources.map((x) => html`<span key=${x.label} class="gui-tower__count">
        <span class="ok-tone-muted">${x.label}</span> <b class=${cls("", { "ok-tone-error": x.n === "ERR" })}>${x.n === "ERR" ? "✗ ERR" : x.n}</b></span>`)}
      ${c.more && html`<span class="gui-tower__count"><span class="ok-tone-muted">+${c.more.count} ${say("more")}</span> <b>${c.more.n}</b></span>`}
    </div>
    ${s ? html`<div class=${cls("gui-hut__foot gui-tower__msg", { "is-fresh": s.fresh, "is-read": s.read })}>
        <span>${!s.read ? html`<span class="ok-tone-fire" aria-label=${say("new")}>● </span>` : ""}<span class="ok-tone-muted">${s.label}</span> ${s.from && html`<b>${s.from}</b> `}${s.title}</span>
        <span class="gui-hut__when">${s.at}</span></div>`
      : html`<div class="gui-hut__foot"><span>${say("Nothing came in yet")}</span></div>`}
  </div>`;
}

/** Folded (docs/design/folded-cards.md): its failing sources first, else how many came in new. */
export function mark(b) {
  const c = b.card;
  if (!c || !c.sources || !c.sources.length) return null;
  if (c.failing) return { text: `${c.failing} failing`, tone: "error" };
  return c.new ? { text: `${c.new} new` } : null;
}

/** Its Info's quick actions, done here: Open new, Read all, Check now. */
export function quick(id, action) {
  const name = { "mail.open_new": "open_new", "watch.read_all": "read_all", "mail.refresh": "check_now" }[action];
  if (!name) return false;
  act(id, name).catch(() => {});
  return true;
}

// -- open: the head -------------------------------------------------------------------------------------------

/** Make a listed source again in the pane over the feed: Edit (step 2) or Log in again (step 1). */
const fix = (id, x, login) => editSource(id, x.id, login).then(() => { tab.value = { ...tab.value, [id]: "add" }; }, () => {});

/** The one button a failing source offers: Log in again, Edit — or none, when it only could not get through. */
function Fix({ id, x }) {
  if (!x.fix || !x.editable) return x.fails === "network" ? html`<span class="ok-tone-muted gui-tower__retry">${say("it tries again by itself")}</span>` : null;
  return html`<button class="ok-btn" onClick=${() => fix(id, x, x.fails === "login")}>${say(x.fix)}</button>`;
}

function Failing({ id, listed }) {
  return listed.filter((x) => x.why).map((x) => html`<p key=${x.id} class="gui-tower__failing ok-tone-error" title=${x.why}>
    <span>✗ <b>${x.label}</b> ${say("is failing")}: ${x.why}</span> <${Fix} id=${id} x=${x} /></p>`);
}

const shownTab = (id, d) => tab.value[id] || (d.sources.length ? "signals" : "add");

function Sources({ id, d }) {
  if (!d.sources.length) return null;          // nothing to filter or check yet: the feed pane is Add a source
  const pick = source.value[id] || "";
  const on = shownTab(id, d);
  const choose = (key) => {
    source.value = { ...source.value, [id]: key };
    tab.value = { ...tab.value, [id]: "signals" };
    opened.value = { ...opened.value, [id]: null };
  };
  const chip = (key, label, n, why) => html`<button key=${key} class=${cls("ok-chip", { "is-on": pick === key && on === "signals" })}
      aria-pressed=${pick === key} title=${why || ""} onClick=${() => choose(key)}>
    ${label} <b class=${cls("", { "ok-tone-error": !!why })}>${why ? "✗ ERR" : n}</b></button>`;
  const state = [d.looking ? say("checking…") : d.checked && `${say("checked")} ${d.checked}`,
    d.mailbox !== null && `${d.mailbox} ${say("unread in the mailbox")}`,
    d.listening && `${say("listening on")} 127.0.0.1:${d.listening}`].filter(Boolean).join(" · ");
  return html`<div class="gui-tower__head">
    <div class="gui-tower__chips" role="group" aria-label=${say("Show the signals of")}>
      ${chip("", say("all"), d.new, "")}
      ${d.sources.map((s) => chip(s.id, s.label, s.new, s.why))}
      <button class=${cls("ok-chip gui-tower__plus", { "is-on": on === "add" })} title=${say("Add a source")} aria-label=${say("Add a source")}
        onClick=${() => { tab.value = { ...tab.value, [id]: "add" }; }}>+</button>
    </div>
    <div class="gui-tower__bar">
      <span class="gui-tower__state" title=${state}>${state}</span>
      <button class=${cls("ok-btn", { "is-pressed": on === "settings" })} aria-pressed=${on === "settings"}
        onClick=${() => { tab.value = { ...tab.value, [id]: on === "settings" ? "signals" : "settings" }; }}>${say("Sources & intent")}</button>
      <button class="ok-btn" onClick=${() => act(id, "check_now").catch(() => {})}>${say("Check now")}</button>
      <button class="ok-btn" onClick=${() => act(id, "read_all", { source: pick }).catch(() => {})}>${say("Read all")}</button>
      <button class="ok-btn primary" disabled=${!d.new} onClick=${() => act(id, "open_new").then((key) => { if (key) opened.value = { ...opened.value, [id]: key }; }, () => {})}>${say("Open new")}</button>
    </div>
    <${Failing} id=${id} listed=${d.listed} />
    ${d.error && html`<p class="gui-tower__failing ok-tone-error">✗ ${d.error}</p>`}
  </div>`;
}

// -- open: the feed, and a signal over it -----------------------------------------------------------------

function Row({ id, s }) {
  return html`<li><button class=${cls("gui-tower__row", { "is-read": s.read, "is-out": s.kept === false })}
      title=${s.why || s.title} onClick=${() => read(id, s.key)}>
    <span class="gui-tower__dot">${s.read ? "" : html`<span class="ok-tone-fire" aria-label=${say("new")}>●</span>`}</span>
    <span class="gui-tower__src">${s.label}</span>
    <span class="gui-tower__what">${s.from && html`<b>${s.from}</b> · `}${s.title}</span>
    <span class="gui-tower__at">${s.at.slice(5)}</span></button></li>`;
}

function Feed({ id, d }) {
  const pick = source.value[id] || "";
  const rows = d.signals.filter((s) => !pick || s.source === pick);
  if (!rows.length) return html`<p class="ok-tone-muted">${say(d.sources.length ? "Nothing here yet — Check now looks again." : "No source yet — Sources & intent says what to listen to.")}</p>`;
  return html`<ul class="gui-tower__rows">${rows.map((s) => html`<${Row} key=${s.key} id=${id} s=${s} />`)}</ul>`;
}

/** A signal read over the feed: ← back, then the signal in full. */
function Item({ id, d, at }) {
  const back = () => { opened.value = { ...opened.value, [id]: null }; };
  const s = d.signals.find((x) => x.key === at);
  return html`<div class="gui-tower__item" onKeyDown=${(e) => { if (e.key === "Escape") { e.stopPropagation(); back(); } }}>
    <button class="ok-btn gui-tower__back" onClick=${back}>← ${say("All signals")} · ${d.signals.length}</button>
    ${s && html`<p class="ok-detail__meta">${s.label}${s.from ? ` · ${s.from}` : ""} · ${s.at}</p>`}
    ${d.reading && d.reading.key === at ? html`<div class="gui-prose" dangerouslySetInnerHTML=${{ __html: d.reading.html }}></div>`
      : html`<p class="ok-tone-muted">${say("Opening…")}</p>`}
  </div>`;
}

function FeedPane({ id, d }) {
  const on = shownTab(id, d);
  if (on === "settings") return html`<${Settings} id=${id} d=${d} />`;
  if (on === "add") return html`<${AddPane} id=${id} d=${d} done=${() => { tab.value = { ...tab.value, [id]: "signals" }; }} />`;
  const at = opened.value[id];
  return at ? html`<${Item} key=${at} id=${id} d=${d} at=${at} />` : html`<${Feed} id=${id} d=${d} />`;
}

function Settings({ id, d }) {
  const [intent, setIntent] = useState(d.intent);
  const [ask, setAsk] = useState("");
  const [removing, setRemoving] = useState(null);
  useEffect(() => setIntent(d.intent), [d.intent]);
  const back = () => { tab.value = { ...tab.value, [id]: "signals" }; };
  return html`<div class="gui-tower__setup" onKeyDown=${(e) => { if (e.key === "Escape") { e.stopPropagation(); back(); } }}>
    <button class="ok-btn gui-tower__back" onClick=${back}>← ${say("Signals")} · ${d.signals.length}</button>
    <p class="ok-list__head">What to listen for</p>
    <div class="gui-head">
      <input class="ok-input" style="flex: 1; width: auto" placeholder=${say("e.g. user feedback about the app — empty lets everything through")} value=${intent}
        onInput=${(e) => setIntent(e.target.value)} onKeyDown=${(e) => e.key === "Enter" && act(id, "intent", { intent }).catch(() => {})} />
      <button class="ok-btn primary" disabled=${intent === d.intent} onClick=${() => act(id, "intent", { intent }).catch(() => {})}>Keep it</button>
    </div>
    ${d.intent_error && html`<p class="ok-tone-error">${d.intent_error}</p>`}
    <div class="gui-head"><p class="ok-list__head" style="flex: 1">Sources · ${d.listed.length}</p>
      <button class="ok-btn primary" onClick=${() => { tab.value = { ...tab.value, [id]: "add" }; }}>+ Add a source</button></div>
    <ul class="gui-tower__sources">
      ${d.listed.map((x) => html`<li key=${x.id} class=${cls("gui-tower__source", { "is-bad": !!x.why })}>
        <${Glyph} service=${x.kind} big=${true} />
        <div><div class="gui-tower__source-name">${x.label}
          ${x.why ? html`<span class="ok-tone-error">✗ ${x.why}</span>` : html`<span class="ok-tone-ok">✓ listening</span>`}</div>
          <div class="ok-tone-muted gui-tower__source-line">${x.line}</div></div>
        <div class="gui-tower__source-acts">
          ${x.fails === "login" && x.editable && html`<button class="ok-btn primary" onClick=${() => fix(id, x, true)}>Log in again</button>`}
          ${x.editable && html`<button class=${cls("ok-btn", { primary: x.fails === "target" })} onClick=${() => fix(id, x, false)}>Edit</button>`}
          <button class="ok-btn" onClick=${() => setRemoving(x)}>Remove</button></div>
      </li>`)}
      ${!d.listed.length && html`<li class="ok-item ok-tone-muted">No source yet.</li>`}
    </ul>
    ${removing && html`<${Dialog} title=${`Remove ${removing.label}?`} warn onCancel=${() => setRemoving(null)}
      text=${say("The tower stops listening to it. Its login stays on this machine, for the next time.")}
      actions=${html`<button class="ok-btn" onClick=${() => setRemoving(null)}>Cancel</button>
        <button class="ok-btn danger" onClick=${() => act(id, "remove", { source: removing.id }).finally(() => setRemoving(null))}>Remove</button>`} />`}
    ${d.places && html`<${Places} id=${id} p=${d.places} />`}
    <p class="ok-list__head">Change the sources</p>
    <div class="gui-head">
      <input class="ok-input" style="flex: 1; width: auto" placeholder=${say("Say it in plain words: e.g. also watch #support in Slack")} value=${ask}
        onInput=${(e) => setAsk(e.target.value)} />
      <button class="ok-btn" disabled=${!ask.trim()} onClick=${() => askKeeper(id, ask.trim()).then(() => setAsk(""))}>${say("Ask the steward")}</button>
    </div>
  </div>`;
}

/** The window by its UI document (design/buildings/watchtower.json): a signal and the sources & intent open
 *  over the feed, in `feed`; `item` shows nothing of its own (an older document that still has it loses
 *  nothing). */
export function panes(id, d) {
  return {
    sources: () => html`<${Sources} id=${id} d=${d} />`,
    feed: () => html`<${FeedPane} id=${id} d=${d} />`,
    item: () => null,
  };
}
