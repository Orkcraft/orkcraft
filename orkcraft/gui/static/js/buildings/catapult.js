// 🎯 The Catapult: the strict way out. Closed: the headline says how it stands (`2/3` loaded, `Firing…`,
// `⚠ Log in`, `✓ 201`), under it where it sends and what the schema says of the load, the last shot in the
// foot. Open, made for the half panel: a shot that waits for your yes as a strip with Fire right there;
// where it sends with Fire, Dry run (and Scout, Log in in browser mode); what is loaded as JSON with the
// schema check; the shots one line each, a shot opening over them (← back): the request, the answer, the
// pictures of the forms; in browser mode the forms. Ask before every shot and the schema and address
// (the steward's to write) fold to a line. The work is the worker's (core/workers/catapult.py).
import { signal } from "@preact/signals";
import { useEffect, useState } from "preact/hooks";
import { html, cls } from "../html.js";
import { act, say } from "../link.js";
import { openInLake } from "../lake.js";
import { KeeperDialog } from "../keeper.js";

const sheet = new URL("./catapult.css", import.meta.url).href;
if (!document.querySelector(`link[href="${sheet}"]`)) {
  const link = document.createElement("link");
  link.rel = "stylesheet";
  link.href = sheet;
  document.head.appendChild(link);
}

const picked = signal({});        // building id → the shot's `at` open over the rows
const pictures = new Map();       // path → data URL, fetched once

/** A time as a card says it: today's as 09:21, an older one as 10-06. */
function stamp(at) {
  if (!at) return "";
  const d = new Date();
  const today = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
  return at.slice(0, 10) === today ? at.slice(11, 16) : at.slice(5, 10);
}

/** The quick actions in its Info (catalog: Fire, Dry run, Scout). */
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
  return html`<img src=${src} alt=${path} title=${say("Open it large in the Inspector")} style=${big ? "max-width:100%" : "max-width:180px"}
    class="gui-link" onClick=${() => openInLake({ path, title: path.split("/").pop(), from: id })} />`;
}

// -- closed ------------------------------------------------------------------------------------------------

/** The headline of the card from its line: the number or the word, and what it means. */
function headline(c) {
  const line = c.line || "";
  const m = /^wait (\d+\/\d+)(.*)$/.exec(line);
  if (m) return [m[1], `${say("loaded, waits for the rest")}${m[2]}`, ""];
  const n = /^(\d+) loaded(.*)$/.exec(line);
  if (n) return [n[1], `${say("loaded")}${n[2]}`, ""];
  if (line === "log in") return [`⚠ ${say("Log in")}`, say("the site wants you"), "fire"];
  if (line === "waits for your yes") return [`? ${say("Fire?")}`, say("a shot waits for your yes"), "fire"];
  if (line === "idle") return [say("Ready"), say("fires when its carts are loaded"), ""];
  if (c.last && line.startsWith(c.last.mark)) return [line, `${say("last shot")} · ${stamp(c.last.at)}`, c.tone];
  return [say(line), "", c.tone === "muted" ? "" : c.tone];
}

const TONE = { ok: "ok-tone-ok", error: "ok-tone-error", wait: "ok-tone-wait", fire: "ok-tone-fire" };

/** Closed: the headline says how it stands; under it where it sends and what the schema says of the load;
 *  the foot the last shot and when (unless the headline is that shot). */
export function card(b) {
  const c = b.card;
  if (!c) return null;
  const [big, small, tone] = headline(c);
  const lastInBig = c.last && (c.line || "").startsWith(c.last.mark);
  return html`<div class="gui-hut__body-in">
    <div class=${cls("gui-hut__big", TONE[tone] || "")}>${big}${small && html`<small>${small}</small>`}</div>
    <div class="gui-hut__text ok-tone-muted" title=${c.target || ""}>${c.browser ? say("browser · ") : ""}${say(c.target || "")}</div>
    ${c.problem ? html`<div class="gui-hut__text ok-tone-error" title=${c.problem}>✗ ${say("schema")}: ${c.problem}</div>`
      : c.loaded > 0 && html`<div class="gui-hut__text"><span class="ok-tone-ok">✓</span> ${say("the load passes the schema")}</div>`}
    ${c.last && !lastInBig && html`<div class="gui-hut__foot"><span>${say("last shot")} <span class=${TONE[c.last.tone] || ""}>${say(c.last.mark)}</span></span>
      <span class="gui-hut__when">${stamp(c.last.at)}</span></div>`}
  </div>`;
}

// -- open: the head ----------------------------------------------------------------------------------------

/** A shot that waits for the person: a strip that says where it goes, Fire and Not now beside it. */
function Asking({ id, data }) {
  if (!data.asking) return null;
  return html`<div class="gui-cat__ask">
    <div class="gui-cat__askline">
      <span class="gui-cat__askwho">? ${say("Fire?")}</span>
      <span class="gui-cat__askwhat" title=${data.asking.title}>${data.asking.title}</span>
      <button class="ok-btn" onClick=${() => act(id, "answer", { yes: false }).catch(() => {})}>${say("Not now")}</button>
      <button class="ok-btn primary" onClick=${() => act(id, "answer", { yes: true }).catch(() => {})}>Fire</button>
    </div>
    <details class="gui-cat__fold"><summary>${say("What it sends")}</summary><pre class="gui-pre">${data.asking.text}</pre></details>
  </div>`;
}

function target(data) {
  if (data.mode === "browser") {
    return `${data.forms.map((f) => f.name + (f.scouted ? "" : " (not scouted)")).join(" → ") || "no forms set"} · then ${data.finish === "press" ? "press submit" : "hand over"}`;
  }
  return `${data.method} ${data.url || "no address set — dry runs only"}`;
}

/** Ask before every shot, the schema and the address: one line until opened — they change rarely. */
function Settings({ id, data }) {
  const [asking, setAsking] = useState(false);
  return html`<details class="gui-cat__fold">
    <summary><span>${say("Settings")}</span>
      <span class="gui-cat__sum">${say(data.confirm ? "asks before every shot" : "fires without asking")} · ${say("schema")} ${data.schema || say("none")}${data.key ? ` · ${say("grouped by")} ${data.key}` : ""}${data.ttl ? ` · ${say(`dropped after ${data.ttl} min`)}` : ""}</span></summary>
    <div class="gui-cat__settings">
      <button class="ok-check" role="checkbox" aria-checked=${data.confirm} title=${say("The setting: every shot asks first")}
        onClick=${() => act(id, "confirm", { on: !data.confirm }).catch(() => {})}><i>${data.confirm ? "✓" : ""}</i> ${say("Ask before every shot")}</button>
      <button class="ok-btn" onClick=${() => setAsking(true)}>${say("Change the schema or the address")}</button>
    </div>
    ${asking && html`<${KeeperDialog} id=${id} title=${say(`The schema and the address — now ${data.method} ${data.url || "no address"}, schema ${data.schema || "none"}`)}
      onClose=${() => setAsking(false)} />`}
  </details>`;
}

function Head({ id, data }) {
  return html`<div class="gui-cat__head">
    <${Asking} id=${id} data=${data} />
    <div class="gui-cat__bar">
      <span class="gui-cat__target" title=${say(target(data))}>${say(target(data))}</span>
      ${data.state && html`<span class=${cls("gui-cat__state", data.login ? "ok-tone-fire" : "ok-tone-wait")}>${say(data.state)}</span>`}
      <span class="gui-cat__acts">
        ${data.login && html`<button class="ok-btn primary" onClick=${() => act(id, "login").catch(() => {})}>${say("Log in")}</button>`}
        ${data.mode === "browser" && html`<button class="ok-btn" onClick=${() => act(id, "scout").catch(() => {})}>Scout</button>`}
        <button class="ok-btn" onClick=${() => act(id, "dry_run").catch(() => {})}>${say("Dry run")}</button>
        <button class=${cls("ok-btn", { primary: !data.login })} onClick=${() => act(id, "fire").catch(() => {})}>Fire</button>
      </span>
    </div>
    <${Settings} id=${id} data=${data} />
  </div>`;
}

// -- open: the load ------------------------------------------------------------------------------------------

function Waits({ data }) {
  if (data.wait_for.length) {
    return html`<span>${say("waits for")} ${data.wait_for.map((w, i) => html`<span key=${w.source}>${i > 0 ? ", " : ""}
      <span class=${w.loaded ? "ok-tone-ok" : "ok-tone-muted"}>${w.loaded ? "✓" : "·"} ${w.source}</span></span>`)}</span>`;
  }
  return html`<span><b>${data.loaded.length}</b> ${say(data.loaded.length ? "loaded" : "loaded — it fires on every cart")}</span>`;
}

function Check({ data }) {
  if (!data.schema) return html`<span class="ok-tone-muted">${say("no schema")}</span>`;
  if (!data.body) return html`<span class="ok-tone-muted">${say("schema")} ${data.schema}</span>`;
  return data.problems.length
    ? html`<span class="ok-tone-error">✗ ${say(`schema: ${data.problems.length === 1 ? "1 problem" : `${data.problems.length} problems`}`)}</span>`
    : html`<span class="ok-tone-ok">✓ ${say("passes the schema")}</span>`;
}

function Load({ data }) {
  return html`<div class="gui-cat__load">
    <p class="gui-cat__loadline"><${Waits} data=${data} /> · <${Check} data=${data} />
      ${data.queued > 0 && html` · <b>${data.queued}</b> ${say("queued")}`}</p>
    ${data.problems.length > 0 && html`<ul class="gui-cat__problems">${data.problems.map((p, i) => html`<li key=${i} class="ok-tone-error">✗ ${p}</li>`)}</ul>`}
    ${data.body ? html`<pre class=${cls("gui-pre gui-cat__json", { "is-bad": data.problems.length > 0 })}>${data.body}</pre>`
      : html`<p class="ok-tone-muted">${say("Nothing is loaded — a road brings the carts.")}</p>`}
  </div>`;
}

// -- open: the shots -------------------------------------------------------------------------------------------

function ShotLine({ s }) {
  const mark = s.dry ? say("dry run") : s.ok ? (s.status ? `✓ ${s.status}` : `✓ ${say("filled")}`) : `✗ ${s.error || s.status}`;
  return html`<span class=${cls("gui-cat__mark", s.dry ? "ok-tone-muted" : s.ok ? "ok-tone-ok" : "ok-tone-error")}>${mark}</span>`;
}

function Shot({ id, data, s }) {
  const back = () => { picked.value = { ...picked.value, [id]: null }; };
  return html`<div class="gui-cat__shot" onKeyDown=${(e) => { if (e.key === "Escape") { e.stopPropagation(); back(); } }}>
    <button class="ok-btn gui-cat__back" onClick=${back}>← ${say("All shots")} · ${data.shots.length}</button>
    <p class="gui-cat__shothead"><${ShotLine} s=${s} /> <span class="ok-tone-muted">${s.when}</span></p>
    ${!s.dry && html`<p class="ok-detail__section">${say("Request")}</p><pre class="gui-pre gui-cat__json">${`→ ${s.url}\n${s.body}`}</pre>`}
    <p class="ok-detail__section">${s.dry ? say("What it would send") : s.status ? `${say("Answer")} · ${s.status}` : say("What happened")}</p>
    <pre class="gui-pre gui-cat__json">${(s.error && s.error !== String(s.status) ? s.error + "\n\n" : "") + (s.answer || say("(no answer)"))}</pre>
    ${s.screens.length > 0 && html`<p class="ok-detail__section">${say("The forms")}</p>
      <div class="gui-counters">${s.screens.map((r) => html`<div key=${r.path}><div class="ok-font-status">${r.form}</div>
        <${Picture} id=${id} path=${r.path} /></div>`)}</div>`}
  </div>`;
}

function Shots({ id, data }) {
  if (!data.shots.length) return html`<p class="ok-tone-muted">${say("No shots yet — Dry run shows what it would send.")}</p>`;
  const s = data.shots.find((x) => x.at === picked.value[id]);
  if (s) return html`<${Shot} key=${s.at} id=${id} data=${data} s=${s} />`;
  const ok = data.shots.filter((x) => x.ok && !x.dry).length, bad = data.shots.filter((x) => !x.ok && !x.dry).length;
  return html`<div class="gui-cat__shots">
    <p class="gui-cat__sum2"><b>${data.shots.length}</b> ${say(data.shots.length === 1 ? "shot" : "shots")} · <span class="ok-tone-ok">✓ ${ok}</span>
      <span class=${bad ? "ok-tone-error" : ""}>✗ ${bad}</span></p>
    <ul class="gui-cat__rows">${data.shots.map((x) => html`<li key=${x.at}><button class="gui-cat__row"
        onClick=${() => { picked.value = { ...picked.value, [id]: x.at }; }}>
      <${ShotLine} s=${x} />
      <span class="gui-cat__at">${x.when}</span>
      <span class="gui-cat__url">${x.dry ? "" : x.url}</span>
      <span class="gui-cat__at">${x.screens.length ? say(x.screens.length === 1 ? "1 picture" : `${x.screens.length} pictures`) : ""}</span>
    </button></li>`)}</ul>
  </div>`;
}

// -- open: the forms (browser mode) -------------------------------------------------------------------------

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
    ${f.script && html`<div class="ok-detail__actions"><button class="ok-btn" onClick=${() => openInLake({ path: f.script, title: `${f.name}: fill.py`, from: id })}>
      ${say("Its script in the Inspector")}</button></div>`}
  </div>`;
}

function Forms({ id, data }) {
  if (data.mode !== "browser") return null;
  return html`<div class="gui-section">
    <div class="gui-head">
      <span class="gui-head__what">${data.progress ? `filling ${data.step} (${data.progress})` : (data.forms.length === 1 ? "1 form" : `${data.forms.length} forms`)}</span>
      <span class="gui-head__spacer"></span>
      <button class="ok-btn" onClick=${() => act(id, "map").catch(() => {})}>${say("Map fields")}</button>
      <button class="ok-btn" onClick=${() => act(id, "finish").catch(() => {})}>
        ${data.finish === "press" ? say("Hand the forms over instead") : say("Press submit instead")}</button>
    </div>
    ${data.forms.length ? data.forms.map((f) => html`<${Form} key=${f.name} id=${id} f=${f} />`)
      : html`<p class="ok-tone-muted">No forms set — ask the steward under Settings.</p>`}
  </div>`;
}

/** The window by its UI document (design/buildings/catapult.json). */
export function panes(id, data) {
  return {
    head: () => html`<${Head} id=${id} data=${data} />`,
    load: () => html`<${Load} data=${data} />`,
    shots: () => html`<${Shots} id=${id} data=${data} />`,
    forms: () => (data.mode === "browser" ? html`<${Forms} id=${id} data=${data} />` : null),
  };
}
