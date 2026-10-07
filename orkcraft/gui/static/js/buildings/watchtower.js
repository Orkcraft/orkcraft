// 🗼 Watchtower: what comes in from outside (core/workers/watchtower.py). Closed: how many are new, a
// counter per source (a failing one marked), the newest message in the foot. Open, made for the half
// panel: a chip per source with what is new in it (it filters the feed), when it last looked, Open new,
// Read all and Check now; a failing source says why; the feed one line per signal, a signal opening over
// it to be read in full (← back); the sources and the intent open the same way, from Sources & intent.
import { signal } from "@preact/signals";
import { useEffect, useState } from "preact/hooks";
import { html, cls } from "../html.js";
import { act, say } from "../link.js";
import { askKeeper } from "../keeper.js";

const source = signal({});         // building id → the source whose feed shows ("" all)
const tab = signal({});            // building id → "signals" | "settings" (the sources and the intent, over the feed)
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
      <div class="gui-hut__text ok-tone-muted">${say("Open it and say what to listen to")}</div>
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

/** Its Info's quick actions, done here: Open new, Read all, Check now. */
export function quick(id, action) {
  const name = { "mail.open_new": "open_new", "watch.read_all": "read_all", "mail.refresh": "check_now" }[action];
  if (!name) return false;
  act(id, name).catch(() => {});
  return true;
}

// -- open: the head -------------------------------------------------------------------------------------------

function Failing({ sources }) {
  const bad = sources.filter((s) => s.why);
  return bad.map((s) => html`<p key=${s.id} class="gui-tower__failing ok-tone-error" title=${s.why}>✗ <b>${s.label}</b> ${say("is failing")}: ${s.why}</p>`);
}

function Sources({ id, d }) {
  const pick = source.value[id] || "";
  const on = tab.value[id] || "signals";
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
    </div>
    <div class="gui-tower__bar">
      <span class="gui-tower__state" title=${state}>${state}</span>
      <button class=${cls("ok-btn", { "is-pressed": on === "settings" })} aria-pressed=${on === "settings"}
        onClick=${() => { tab.value = { ...tab.value, [id]: on === "settings" ? "signals" : "settings" }; }}>${say("Sources & intent")}</button>
      <button class="ok-btn" onClick=${() => act(id, "check_now").catch(() => {})}>${say("Check now")}</button>
      <button class="ok-btn" onClick=${() => act(id, "read_all", { source: pick }).catch(() => {})}>${say("Read all")}</button>
      <button class="ok-btn primary" disabled=${!d.new} onClick=${() => act(id, "open_new").then((key) => { if (key) opened.value = { ...opened.value, [id]: key }; }, () => {})}>${say("Open new")}</button>
    </div>
    <${Failing} sources=${d.sources} />
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
  if ((tab.value[id] || "signals") === "settings") return html`<${Settings} id=${id} d=${d} />`;
  const at = opened.value[id];
  return at ? html`<${Item} key=${at} id=${id} d=${d} at=${at} />` : html`<${Feed} id=${id} d=${d} />`;
}

function Settings({ id, d }) {
  const [intent, setIntent] = useState(d.intent);
  const [ask, setAsk] = useState("");
  useEffect(() => setIntent(d.intent), [d.intent]);
  const s = d.settings;
  const line = (label, value) => value !== "" && value !== undefined && html`<li class="ok-item"><span class="ok-tone-muted">${label}</span>
    <span>${value}</span></li>`;
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
    <p class="ok-list__head">Sources</p>
    <ul class="ok-list__items">
      ${line(say("mail"), s.host && `${s.host}${s.folder ? ` · ${s.folder}` : ""}`)}
      ${line("GitHub", s.github)}
      ${line(say("schedule"), s.cron)}
      ${line("webhook", s.webhook_port && `127.0.0.1:${s.webhook_port}`)}
      ${s.feeds.map((f) => html`<li key=${f} class="ok-item"><span class="gui-pre">${f}</span></li>`)}
      ${!d.sources.length && html`<li class="ok-item ok-tone-muted">No source yet.</li>`}
    </ul>
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
