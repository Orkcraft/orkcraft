// 🎯 The Catapult: the strict way out. Closed: one line (`wait 2/3`, `firing…`, `log in`, `✓ 201`). Command:
// what is loaded and what it waits for, the schema check, the last three shots, the browser's current
// step; Fire and Dry run are the quick actions, Scout beside them, and whether every shot asks first.
// Full: the load as JSON with what the schema says, the shots (request, answer, code), and in browser mode
// the forms with their fields and a small picture of each form (large in Lake). The schema and the
// address are the keeper's to write. The work is the worker's (core/workers/catapult.py).
import { signal } from "@preact/signals";
import { useEffect, useState } from "preact/hooks";
import { html, cls } from "../html.js";
import { act, say } from "../link.js";
import { openInLake } from "../lake.js";
import { KeeperDialog } from "../keeper.js";

const picked = signal({});        // building id → the shot's `at` shown in full
const pictures = new Map();       // path → data URL, fetched once

/** The quick actions on the Command Card (catalog: Fire, Dry run, Scout). */
export function quick(id, action) {
  const name = { "catapult.fire": "fire", "catapult.dry_run": "dry_run", "catapult.scout": "scout" }[action];
  if (!name) return false;
  act(id, name).catch(() => {});
  return true;
}

function Picture({ id, path, big = false }) {
  const [src, setSrc] = useState(pictures.get(path) || null);
  useEffect(() => {
    if (pictures.has(path)) { setSrc(pictures.get(path)); return; }
    act(id, "picture", { path }).then((url) => { pictures.set(path, url); setSrc(url); }, () => setSrc(""));
  }, [id, path]);
  if (src === null) return html`<span class="ok-tone-muted">…</span>`;
  if (!src) return null;
  return html`<img src=${src} alt=${path} title="Open it large in Lake" style=${big ? "max-width:100%" : "max-width:180px"}
    class="gui-link" onClick=${() => openInLake({ path, title: path.split("/").pop(), from: id })} />`;
}

function Asking({ id, data }) {
  if (!data.asking) return null;
  return html`<div class="gui-head">
    <span class="gui-head__what ok-tone-fire">${data.asking.title}</span>
    <span class="gui-head__spacer"></span>
    <button class="ok-act" onClick=${() => act(id, "answer", { yes: true }).catch(() => {})}><span class="ok-act__label">Fire</span></button>
    <button class="ok-act" onClick=${() => act(id, "answer", { yes: false }).catch(() => {})}><span class="ok-act__label">Not now</span></button>
  </div>
  <pre class="gui-pre">${data.asking.text}</pre>`;
}

function Confirm({ id, data }) {
  return html`<label class="ok-check" title="The setting: every shot asks first"
      onClick=${() => act(id, "confirm", { on: !data.confirm }).catch(() => {})}>
    <i>${data.confirm ? "✓" : ""}</i> Ask before every shot</label>`;
}

function Waits({ data }) {
  if (data.wait_for.length) {
    return html`<span>waits for ${data.wait_for.map((w, i) => html`<span key=${w.source}>${i > 0 ? ", " : ""}
      <span class=${w.loaded ? "ok-tone-ok" : "ok-tone-muted"}>${w.loaded ? "✓" : "·"} ${w.source}</span></span>`)}</span>`;
  }
  return html`<span>${data.loaded.length ? `${data.loaded.length} loaded` : say("fires on every cart")}</span>`;
}

function Check({ data }) {
  if (!data.schema) return html`<span class="ok-tone-muted">no schema</span>`;
  if (!data.body) return html`<span class="ok-tone-muted">schema ${data.schema}</span>`;
  return data.problems.length
    ? html`<span class="ok-tone-error">schema: ${data.problems.join("; ")}</span>`
    : html`<span class="ok-tone-ok">schema ✓</span>`;
}

function target(data) {
  if (data.mode === "browser") {
    return `${data.forms.map((f) => f.name + (f.scouted ? "" : " (not scouted)")).join(" → ") || "no forms set"} · then ${data.finish === "press" ? "press submit" : "hand over"}`;
  }
  return `${data.method} ${data.url || "no address set — dry runs only"}`;
}

function ShotLine({ s }) {
  const mark = s.dry ? "dry run" : s.ok ? (s.status ? `✓ ${s.status}` : "✓ filled") : `✗ ${s.error || s.status}`;
  return html`<span class=${s.dry ? "ok-tone-muted" : s.ok ? "ok-tone-ok" : "ok-tone-error"}>${mark}</span>
    <span class="ok-tone-muted"> · ${s.when}</span>`;
}

function Head({ id, data }) {
  const [asking, setAsking] = useState(false);
  return html`<${Asking} id=${id} data=${data} />
  <div class="gui-head">
    <span class="gui-head__what">${say(target(data))}${data.state && html` · <span class=${data.login ? "ok-tone-fire" : "ok-tone-wait"}>${say(data.state)}</span>`}</span>
    <span class="gui-head__spacer"></span>
    <button class="ok-act" onClick=${() => act(id, "fire").catch(() => {})}><span class="ok-act__label">Fire</span></button>
    <button class="ok-act" onClick=${() => act(id, "dry_run").catch(() => {})}><span class="ok-act__label">Dry run</span></button>
    ${data.mode === "browser" && html`<button class="ok-act" onClick=${() => act(id, "scout").catch(() => {})}><span class="ok-act__label">Scout</span></button>`}
    ${data.login && html`<button class="ok-act" onClick=${() => act(id, "login").catch(() => {})}><span class="ok-act__label">Log in</span></button>`}
    <button class="ok-act" onClick=${() => setAsking(true)}><span class="ok-act__label">Schema and address</span></button>
  </div>
  <div class="gui-head"><${Confirm} id=${id} data=${data} /></div>
  ${asking && html`<${KeeperDialog} id=${id} title=${`The schema and the address — now ${data.method} ${data.url || "no address"}, schema ${data.schema || "none"}`}
    onClose=${() => setAsking(false)} />`}`;
}

function Load({ data }) {
  return html`<div class="gui-section">
    <div class="ok-font-status"><${Waits} data=${data} />${data.key && ` · grouped by ${data.key}`}${data.ttl ? ` · dropped after ${data.ttl} min` : ""}
      ${data.queued > 0 && ` · ${data.queued} queued`}</div>
    <div class="ok-font-status"><${Check} data=${data} /></div>
    ${data.body ? html`<pre class=${cls("gui-pre", { "ok-tone-error": data.problems.length > 0 })}>${data.body}</pre>`
      : html`<p class="ok-tone-muted">Nothing is loaded.</p>`}
    ${data.problems.length > 0 && html`<ul class="gui-rows">${data.problems.map((p, i) => html`<li key=${i} class="ok-font-status ok-tone-error">✗ ${p}</li>`)}</ul>`}
  </div>`;
}

function Shot({ id, s }) {
  return html`<div class="ok-detail">
    <div class="ok-detail__head"><${ShotLine} s=${s} /></div>
    ${!s.dry && html`<p class="ok-detail__section">Request</p><pre class="gui-pre">${`→ ${s.url}\n${s.body}`}</pre>`}
    <p class="ok-detail__section">${s.dry ? "What it would send" : s.status ? `Answer · ${s.status}` : "What happened"}</p>
    <pre class="gui-pre">${(s.error && s.error !== String(s.status) ? s.error + "\n\n" : "") + (s.answer || "(no answer)")}</pre>
    ${s.screens.length > 0 && html`<p class="ok-detail__section">The forms</p>
      <div class="gui-counters">${s.screens.map((r) => html`<div key=${r.path}><div class="ok-font-status">${r.form}</div>
        <${Picture} id=${id} path=${r.path} /></div>`)}</div>`}
  </div>`;
}

function Shots({ id, data }) {
  if (!data.shots.length) return html`<p class="ok-tone-muted">No shots yet.</p>`;
  const at = picked.value[id] || data.shots[0].at;
  const s = data.shots.find((x) => x.at === at) || data.shots[0];
  return html`<div class="gui-split is-row">
    <ul class="ok-list__items" style="flex: 2 1 0">${data.shots.map((x) => html`<li key=${x.at}
        class=${cls("ok-item", { "is-selected": x.at === s.at })} onClick=${() => { picked.value = { ...picked.value, [id]: x.at }; }}>
      <${ShotLine} s=${x} />${x.screens.length > 0 && html`<span class="meta">${x.screens.length === 1 ? "1 picture" : `${x.screens.length} pictures`}</span>`}</li>`)}</ul>
    <div style="flex: 3 1 0; min-width: 0"><${Shot} id=${id} s=${s} /></div>
  </div>`;
}

function Form({ id, f }) {
  return html`<div class="ok-detail">
    <div class="ok-detail__head">${f.name}</div>
    <p class="ok-detail__meta">${f.url}${f.goal && ` · ${f.goal}`}</p>
    ${!f.scouted ? html`<p class="ok-detail__meta ok-tone-wait">Not scouted yet: Scout sends the ork to find it.</p>`
      : html`<p class="ok-detail__meta">${f.fields} fields · submit ${f.submit || "unknown"}${f.reached_by && ` · reached by ${f.reached_by}`}
          ${f.by_hand ? " · its script was edited by hand" : ""}</p>`}
    ${f.steps.length > 0 && html`<table class="gui-diff"><tbody>${f.steps.map((s, i) => html`<tr key=${i}>
      <td>${s.label}</td><td>← ${s.from}</td><td class="ok-tone-muted">${s.by}</td><td>${s.value}</td></tr>`)}</tbody></table>`}
    ${f.unfilled.length > 0 && html`<p class="ok-detail__meta ok-tone-error">required, left empty: ${f.unfilled.join(", ")}</p>`}
    ${f.unused.length > 0 && html`<p class="ok-detail__meta">not used: ${f.unused.join(", ")}</p>`}
    ${f.problems.length > 0 && html`<p class="ok-detail__meta ok-tone-wait">settings: ${f.problems.join("; ")}</p>`}
    ${f.picture && html`<${Picture} id=${id} path=${f.picture} />`}
    ${f.script && html`<div class="ok-detail__actions"><button class="ok-act" onClick=${() => openInLake({ path: f.script, title: `${f.name}: fill.py`, from: id })}>
      <span class="ok-act__label">Its script in Lake</span></button></div>`}
  </div>`;
}

function Forms({ id, data }) {
  if (data.mode !== "browser") return null;
  return html`<div class="gui-section">
    <div class="gui-head">
      <span class="gui-head__what">${data.progress ? `filling ${data.step} (${data.progress})` : (data.forms.length === 1 ? "1 form" : `${data.forms.length} forms`)}</span>
      <span class="gui-head__spacer"></span>
      <button class="ok-act" onClick=${() => act(id, "map").catch(() => {})}><span class="ok-act__label">Map fields</span></button>
      <button class="ok-act" onClick=${() => act(id, "finish").catch(() => {})}>
        <span class="ok-act__label">${data.finish === "press" ? "Hand the forms over instead" : "Press submit instead"}</span></button>
    </div>
    ${data.forms.length ? data.forms.map((f) => html`<${Form} key=${f.name} id=${id} f=${f} />`)
      : html`<p class="ok-tone-muted">No forms set — ask the keeper.</p>`}
  </div>`;
}

/** Closed: one line. */
export function card(b) {
  const c = b.card;
  if (!c) return null;
  return html`<div>${c.browser && html`<i class="ok-ico">🌐 </i>`}<span class=${`ok-tone-${c.tone}`}>${say(c.line)}</span></div>`;
}

/** Command: what is loaded and what it waits for, the schema check, the last three shots, the browser's step. */
export function preview(id, data) {
  return html`<div class="gui-section">
    <${Asking} id=${id} data=${data} />
    <div class="ok-font-status ok-tone-muted">${say(target(data))}</div>
    <div class="ok-font-status"><${Waits} data=${data} />${data.queued > 0 && ` · ${data.queued} queued`}</div>
    <div class="ok-font-status"><${Check} data=${data} /></div>
    ${data.state && html`<div class=${cls("ok-font-status", { "ok-tone-fire": !!data.login, "ok-tone-wait": !data.login })}>${say(data.state)}</div>`}
    ${data.progress && html`<div class="ok-font-status">filling ${data.step} (${data.progress})</div>`}
    ${data.shots.length > 0 && html`<ul class="gui-rows">${data.shots.slice(0, 3).map((s) => html`<li key=${s.at} class="ok-font-status">
      <${ShotLine} s=${s} /></li>`)}</ul>`}
    <div class="ok-detail__actions">
      ${data.mode === "browser" && html`<button class="ok-act" onClick=${() => act(id, "scout").catch(() => {})}><span class="ok-act__label">Scout</span></button>`}
      ${data.login && html`<button class="ok-act" onClick=${() => act(id, "login").catch(() => {})}><span class="ok-act__label">Log in</span></button>`}
      <${Confirm} id=${id} data=${data} />
    </div>
  </div>`;
}

export function panes(id, data) {
  return {
    head: () => html`<${Head} id=${id} data=${data} />`,
    load: () => html`<${Load} data=${data} />`,
    shots: () => html`<${Shots} id=${id} data=${data} />`,
    forms: () => (data.mode === "browser" ? html`<${Forms} id=${id} data=${data} />` : null),
  };
}
