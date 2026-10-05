// 🗼 Watchtower: what comes in from outside (core/workers/watchtower.py). Closed: what is new per
// source; command: the newest per source, a failing source with why; full: the sources with their
// counters, the chosen source's feed, the item read in full, and a tab for the sources and the intent
// (drawn in the feed's pane, the item's hidden).
import { signal } from "@preact/signals";
import { useEffect, useState } from "preact/hooks";
import { html, cls } from "../html.js";
import { act, say } from "../link.js";
import { askKeeper } from "../keeper.js";

const source = signal({});         // building id → the source whose feed shows ("" all)
const tab = signal({});            // building id → "signals" | "settings"

const read = (id, key) => act(id, "read", { key }).catch(() => {});

/** Closed: a counter per source — `gmail 3`, `slack 99+`, `jira ERR`; more than four fold into `+N more`. */
export function card(b) {
  const c = b.card;
  if (!c) return null;
  if (!c.sources.length) return html`<span class="ok-tone-muted">no source yet</span>`;
  return html`<div class="gui-counters">
    ${c.sources.map((s) => html`<span key=${s.label} class="gui-counter">
      <span class="ok-tone-muted">${s.label}</span> <b class=${cls("", { "ok-tone-error": s.n === "ERR" })}>${s.n}</b></span>`)}
    ${c.more && html`<span class="gui-counter"><span class="ok-tone-muted">+${c.more.count} more</span> <b>${c.more.n}</b></span>`}
  </div>`;
}

/** The Command Card's quick actions, done here: Open new, Read all, Check now. */
export function quick(id, action) {
  const name = { "mail.open_new": "open_new", "watch.read_all": "read_all", "mail.refresh": "check_now" }[action];
  if (!name) return false;
  act(id, name).catch(() => {});
  return true;
}

function Failing({ sources }) {
  const bad = sources.filter((s) => s.why);
  return bad.map((s) => html`<p key=${s.id} class="ok-tone-error"><b>${s.label}</b> ${say("is failing")}: ${s.why}</p>`);
}

function Row({ id, s, selected }) {
  return html`<li class=${cls("ok-item", { "is-selected": selected, "is-disabled": s.kept === false })}
      title=${s.why || ""} onClick=${() => read(id, s.key)}>
    <span class=${cls("", { "ok-tone-fire": !s.read })}>${s.read ? "" : "●"}</span>
    <span class="ok-tone-muted">${s.label}</span>
    ${s.from && html`<b>${s.from}</b>`}<span>${s.title}</span>
    <span class="meta">${s.at.slice(5)}</span></li>`;
}

/** Command: the newest per source (source, from, title), a failing source with why. */
export function preview(id, d) {
  return html`<div class="gui-rows">
    ${!d.sources.length && html`<p class="ok-tone-muted">No source yet: mail, GitHub, Slack, Jira, Confluence, Figma, a schedule or a webhook, in its settings.</p>`}
    <${Failing} sources=${d.sources} />
    ${d.sources.length > 0 && !d.latest.length && html`<p class="ok-tone-muted">Nothing came in yet${d.checked ? ` · checked ${d.checked}` : ""}.</p>`}
    <ul class="ok-list__items">${d.latest.map((s) => html`<${Row} key=${s.key} id=${id} s=${s} />`)}</ul>
    ${d.reading && html`<div class="gui-prose" dangerouslySetInnerHTML=${{ __html: d.reading.html }}></div>`}
  </div>`;
}

function Sources({ id, d }) {
  const pick = source.value[id] || "";
  const on = tab.value[id] || "signals";
  const chip = (key, label, n, why) => html`<button key=${key} class=${cls("ok-chip", { "is-on": pick === key && on === "signals" })}
      title=${why || ""} onClick=${() => { source.value = { ...source.value, [id]: key }; tab.value = { ...tab.value, [id]: "signals" }; }}>
    ${label} <b class=${cls("", { "ok-tone-error": !!why && !(pick === key && on === "signals") })}>${why ? "ERR" : n}</b></button>`;
  return html`<div class="gui-rows">
    <div class="gui-head">
      ${chip("", say("all"), d.new, "")}
      ${d.sources.map((s) => chip(s.id, s.label, s.new, s.why))}
      <span class="gui-head__spacer"></span>
      <span class="ok-tone-muted">${[d.looking ? say("checking…") : d.checked && `${say("checked")} ${d.checked}`,
        d.mailbox !== null && `${d.mailbox} ${say("unread in the mailbox")}`,
        d.listening && `${say("listening on")} 127.0.0.1:${d.listening}`].filter(Boolean).join(" · ")}</span>
      <button class="ok-act" onClick=${() => act(id, "open_new").catch(() => {})}><span class="ok-act__label">Open new</span></button>
      <button class="ok-act" onClick=${() => act(id, "read_all", { source: pick }).catch(() => {})}><span class="ok-act__label">Read all</span></button>
      <button class="ok-act" onClick=${() => act(id, "check_now").catch(() => {})}><span class="ok-act__label">Check now</span></button>
    </div>
    <div class="ok-tabs" role="tablist">
      ${[["signals", "Signals"], ["settings", "Sources & intent"]].map(([k, label]) => html`<button key=${k} role="tab"
        class=${cls("ok-tab", { "is-active": on === k })} onClick=${() => { tab.value = { ...tab.value, [id]: k }; }}>${label}</button>`)}
    </div>
    <${Failing} sources=${d.sources} />
    ${d.error && html`<p class="ok-tone-error">${d.error}</p>`}
  </div>`;
}

function Feed({ id, d }) {
  const pick = source.value[id] || "";
  const rows = d.signals.filter((s) => !pick || s.source === pick);
  if (!rows.length) return html`<p class="ok-tone-muted">Nothing here yet.</p>`;
  const at = d.reading && d.reading.key;
  return html`<ul class="ok-list__items">${rows.map((s) => html`<${Row} key=${s.key} id=${id} s=${s} selected=${s.key === at} />`)}</ul>`;
}

function Item({ d }) {
  if (!d.reading) return html`<p class="ok-tone-muted">Pick a signal to read it in full.</p>`;
  return html`<div class="gui-prose" dangerouslySetInnerHTML=${{ __html: d.reading.html }}></div>`;
}

function Settings({ id, d }) {
  const [intent, setIntent] = useState(d.intent);
  const [ask, setAsk] = useState("");
  useEffect(() => setIntent(d.intent), [d.intent]);
  const s = d.settings;
  const line = (label, value) => value !== "" && value !== undefined && html`<li class="ok-item"><span class="ok-tone-muted">${label}</span>
    <span>${value}</span></li>`;
  return html`<div class="gui-rows">
    <p class="ok-list__head">What to listen for</p>
    <div class="gui-head">
      <input class="ok-input" style="flex: 1; width: auto" placeholder=${say("e.g. user feedback about the app — empty lets everything through")} value=${intent}
        onInput=${(e) => setIntent(e.target.value)} onKeyDown=${(e) => e.key === "Enter" && act(id, "intent", { intent }).catch(() => {})} />
      <button class="ok-act" disabled=${intent === d.intent} onClick=${() => act(id, "intent", { intent }).catch(() => {})}>
        <span class="ok-act__label">Keep it</span></button>
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
      <button class="ok-act" disabled=${!ask.trim()} onClick=${() => askKeeper(id, ask.trim()).then(() => setAsk(""))}>
        <span class="ok-act__label">Ask the keeper</span></button>
    </div>
  </div>`;
}

/** Full: the sources with their counters and state · the chosen source's feed · the item in full; a tab
 *  for the sources and the intent. */
export function panes(id, d) {
  const settings = (tab.value[id] || "signals") === "settings";
  return {
    sources: () => html`<${Sources} id=${id} d=${d} />`,
    feed: () => (settings ? html`<${Settings} id=${id} d=${d} />` : html`<${Feed} id=${id} d=${d} />`),
    item: () => (settings ? null : html`<${Item} d=${d} />`),
  };
}
