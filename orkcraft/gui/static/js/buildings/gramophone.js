// 📻 The Gramophone (docs/design/audio-briefing.md §7). Closed: the episode being made and its step, or the last
// one with its length. Open, made for the half panel: an episode of pasted text (or of the last text that came)
// with what a minute costs; the one being made, or one that waits for its price with Speak anyway; the
// episodes one line each with ▶ (played in the page), download and the transcript over the rows (← back); the
// settings: the Gemini key and where the text goes, the language, length, voice, limit and how many to keep.
// The making is the worker's (core/workers/gramophone.py); the file comes from /api/audio (gui/server.py).
import { signal } from "@preact/signals";
import { useState } from "preact/hooks";
import { html, cls } from "../html.js";
import { act, details, say } from "../link.js";
import { Dialog } from "../dialog.js";
import { usePeek } from "../windows.js";

const sheet = new URL("./gramophone.css", import.meta.url).href;
if (!document.querySelector(`link[href="${sheet}"]`)) {
  const link = document.createElement("link");
  link.rel = "stylesheet";
  link.href = sheet;
  document.head.appendChild(link);
}

const TOKEN = new URLSearchParams(location.search).get("t") || "";
const chosen = signal({});          // building id → the transcript open over the rows {id, title, text}
const playing = signal({});         // building id → the episode playing in the page
const making = signal({});          // building id → true: Make an episode is open over the town

const money = (usd) => `$${usd && usd < 0.01 ? usd.toFixed(4) : (usd || 0).toFixed(2)}`;
const day = (at) => (at || "").slice(5, 16).replace("T", " ");
const length = (s) => (s ? `${Math.floor(s / 60)}:${String(Math.round(s % 60)).padStart(2, "0")}` : "");
const size = (b) => (!b ? "" : b < 1048576 ? `${Math.max(1, Math.round(b / 1024))} KB` : `${(b / 1048576).toFixed(1)} MB`);
const fileOf = (id, eid, dl = false) =>
  `/api/audio/${encodeURIComponent(id)}/${encodeURIComponent(eid)}?t=${encodeURIComponent(TOKEN)}${dl ? "&dl=1" : ""}`;
const STATUS = { queued: "Waiting its turn", script: "Writing the script", speaking: "Speaking", held: "Waits for its price",
  done: "Ready", failed: "Failed", stopped: "Stopped" };
const MARK = { done: "▶", failed: "✗", stopped: "■", held: "?", queued: "…", script: "…", speaking: "…" };
const TONE = { done: "ok-tone-ok", failed: "ok-tone-error", stopped: "ok-tone-muted", held: "ok-tone-fire",
  queued: "ok-tone-wait", script: "ok-tone-wait", speaking: "ok-tone-wait" };

// -- closed --------------------------------------------------------------------------------------------------

export function card(b) {
  const c = b.card;
  if (!c) return null;
  const key = !c.has_key && html`<div class="gui-hut__text ok-tone-fire">${say("No Gemini key: open it to add one")}</div>`;
  if (c.state === "running") {
    return html`<div class="gui-hut__body-in">
      <div class="gui-hut__big ok-tone-wait">${say(c.step ? c.step[0].toUpperCase() + c.step.slice(1) : "Making an episode")}<small>${c.queue ? `${c.queue} ${say("waiting")}` : ""}</small></div>
      <div class="gui-hut__foot"><span>${c.title}</span></div>
    </div>`;
  }
  if (c.state === "none") {
    return html`<div class="gui-hut__body-in">
      <div class="gui-hut__big">${say("Ready")}<small>${say("no episodes yet")}</small></div>
      ${key || html`<div class="gui-hut__text ok-tone-muted">${say("A road brings a text, or paste one")}</div>`}
    </div>`;
  }
  return html`<div class="gui-hut__body-in">
    <div class=${cls("gui-hut__big", TONE[c.state] || "")}>${MARK[c.state] || ""} ${say(STATUS[c.state] || c.state)}<small>${c.state === "done" ? length(c.seconds) : say("the last episode")}</small></div>
    ${key}
    <div class="gui-hut__foot"><span class=${c.state === "failed" ? "ok-tone-error" : ""}>${c.state === "failed" ? c.error : c.title}</span>
      <span class="gui-hut__when">${day(c.at).slice(6)}</span></div>
  </div>`;
}

// -- making one ----------------------------------------------------------------------------------------------

function MakeForm({ id, data, onDone }) {
  const [text, setText] = useState("");
  const [title, setTitle] = useState("");
  const [busy, setBusy] = useState(false);
  const go = () => {
    setBusy(true);
    act(id, "make", { text, title }).then(() => { setText(""); setTitle(""); onDone && onDone(); }, () => {})
      .finally(() => setBusy(false));
  };
  const s = data.settings || {};
  return html`<div class="gui-gramophone__make">
    <input class="ok-input" placeholder=${say("Title (optional)")} value=${title} onInput=${(e) => setTitle(e.target.value)} />
    <textarea class="ok-input gui-textarea" rows="3" value=${text} onInput=${(e) => setText(e.target.value)}
      placeholder=${say(data.has_input ? "Paste a text, or leave it empty for the last text that came" : "Paste a report, a summary or a page")}></textarea>
    <div class="gui-gramophone__go">
      <span class="ok-tone-muted">${say(`about ${s.minutes} min`)} · ${say(`~${money(data.per_minute)} a minute to speak`)} · ${say(`up to ${money(s.cap_usd)}`)}</span>
      <button class="ok-btn primary" disabled=${busy || !data.has_key || (!text.trim() && !data.has_input)} onClick=${go}>${say("Make an episode")}</button>
    </div>
  </div>`;
}

function Current({ id, e }) {
  if (e.status === "held") {
    return html`<div class="gui-gramophone__current">
      <p><b class="ok-tone-fire">? ${say(STATUS.held)}</b> <span>${e.title}</span></p>
      <p class="ok-tone-muted">${e.error}</p>
      <div class="ok-detail__actions">
        <button class="ok-btn primary" onClick=${() => act(id, "speak", { id: e.id }).catch(() => {})}>${say(`Speak anyway · ~${money(e.estimate)}`)}</button>
        <button class="ok-btn" onClick=${() => act(id, "delete", { id: e.id }).catch(() => {})}>${say("Drop it")}</button>
      </div>
    </div>`;
  }
  return html`<div class="gui-gramophone__current">
    <p><b class="ok-tone-wait">${say(e.step ? e.step[0].toUpperCase() + e.step.slice(1) : STATUS[e.status] || e.status)}…</b> <span>${e.title}</span></p>
  </div>`;
}

// -- the episodes --------------------------------------------------------------------------------------------

function Transcript({ id, t, count }) {
  const back = () => { chosen.value = { ...chosen.value, [id]: null }; };
  return html`<div class="gui-gramophone__transcript" onKeyDown=${(e) => { if (e.key === "Escape") { e.stopPropagation(); back(); } }}>
    <button class="ok-btn" onClick=${back}>← ${say("All episodes")} · ${count}</button>
    <pre class="gui-gramophone__text">${t.text || say("No transcript kept")}</pre>
  </div>`;
}

function Row({ id, e }) {
  const on = playing.value[id] === e.id;
  const play = () => { playing.value = { ...playing.value, [id]: on ? null : e.id }; };
  const read = () => act(id, "transcript", { id: e.id }).then((t) => { chosen.value = { ...chosen.value, [id]: t }; }, () => {});
  const done = e.status === "done";
  return html`<li class="gui-gramophone__row">
    <div class="gui-gramophone__line">
      ${done ? html`<button class="ok-btn gui-gramophone__play" onClick=${play} aria-label=${say(on ? "Hide the player" : "Play")}>${on ? "■" : "▶"}</button>`
        : html`<span class=${cls("gui-gramophone__mark", TONE[e.status])} title=${say(STATUS[e.status] || "")}>${MARK[e.status] || "·"}</span>`}
      <span class="gui-gramophone__at">${day(e.created)}</span>
      <span class="gui-gramophone__what" title=${e.error || e.title}>${e.title}</span>
      <span class="ok-tone-muted">${done ? `${length(e.seconds)} · ${e.lang}` : say(STATUS[e.status] || e.status)}</span>
      <span class="gui-gramophone__cost">${e.cost ? money(e.cost) : ""}</span>
    </div>
    ${on && html`<audio class="gui-gramophone__audio" controls autoplay src=${fileOf(id, e.id)}></audio>`}
    <div class="gui-gramophone__acts">
      ${done && html`<a class="ok-btn" href=${fileOf(id, e.id, true)} download>⬇ ${say("Download")} <span class="ok-tone-muted">${size(e.bytes)}</span></a>`}
      ${(done || e.status === "held") && html`<button class="ok-btn" onClick=${read}>${say("Transcript")}</button>`}
      ${e.status === "failed" && html`<span class="ok-tone-error">${e.error}</span>`}
      ${!["queued", "script", "speaking"].includes(e.status) && html`<button class="ok-btn" onClick=${() => act(id, "delete", { id: e.id }).catch(() => {})}>${say("Delete")}</button>`}
    </div>
  </li>`;
}

function Episodes({ id, data }) {
  const open = chosen.value[id];
  const list = (data.episodes || []).filter((e) => !(data.running && e.id === data.running.id));
  if (open) return html`<${Transcript} id=${id} t=${open} count=${list.length} />`;
  return html`<div class="gui-gramophone__episodes">
    ${list.length ? html`<ul class="gui-gramophone__rows">${list.map((e) => html`<${Row} key=${e.id} id=${id} e=${e} />`)}</ul>`
      : html`<p class="ok-tone-muted">${say("No episodes yet — paste a text above, or a road brings one.")}</p>`}
    ${data.spent > 0 && html`<p class="ok-detail__meta">${say(`Spent on these episodes: ${money(data.spent)}`)}</p>`}
  </div>`;
}

// -- settings ------------------------------------------------------------------------------------------------

function Settings({ id, data }) {
  const s = data.settings || {};
  const [secret, setSecret] = useState("");
  const [form, setForm] = useState({ language: s.language, minutes: s.minutes, voice: s.voice, cap_usd: s.cap_usd, keep: s.keep });
  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value });
  const keep = () => act(id, "settings", form).catch(() => {});
  const saveKey = () => act(id, "save_key", { secret }).then(() => setSecret(""), () => {});
  return html`<details class="gui-gramophone__settings" open=${!data.has_key}><summary>${say("Settings")}</summary>
    <p class=${data.has_key ? "ok-tone-muted" : "ok-tone-fire"}>${data.has_key
      ? say(`Gemini key: ${data.key_where}`) : say(`No Gemini key: set $${data.default_key}, or paste one to keep it on this machine`)}</p>
    <div class="gui-gramophone__go">
      <input class="ok-input" type="password" autocomplete="off" placeholder=${say("Gemini API key")} value=${secret}
        onInput=${(e) => setSecret(e.target.value)} aria-label=${say("Gemini API key")} />
      <button class="ok-btn" disabled=${!secret.trim()} onClick=${saveKey}>${say("Keep the key")}</button>
    </div>
    <p class="ok-tone-muted">${say("The script is written by its steward's model, then sent to Google (Gemini API) to be spoken. E-mails, phones, cards and tokens are taken out first.")}</p>
    <div class="gui-gramophone__grid">
      <label>${say("Language")}<select class="ok-input" value=${form.language} onChange=${set("language")}>
        <option value="auto">${say("As the text")}</option><option value="ru">Русский</option><option value="en">English</option></select></label>
      <label>${say("Minutes")}<input class="ok-input" type="number" min="2" max="20" value=${form.minutes} onInput=${set("minutes")} /></label>
      <label>${say("Voice")}<input class="ok-input" value=${form.voice} onInput=${set("voice")} /></label>
      <label>${say("Limit an episode, $")}<input class="ok-input" type="number" min="0.05" max="5" step="0.05" value=${form.cap_usd} onInput=${set("cap_usd")} /></label>
      <label>${say("Keep")}<input class="ok-input" type="number" min="1" max="200" value=${form.keep} onInput=${set("keep")} /></label>
    </div>
    <div class="ok-detail__actions"><button class="ok-btn primary" onClick=${keep}>${say("Save settings")}</button></div>
  </details>`;
}

/** The window by its UI document (design/buildings/gramophone.json). */
export function panes(id, data) {
  return {
    make: () => html`<${MakeForm} id=${id} data=${data} />`,
    current: () => {
      const held = (data.episodes || []).filter((e) => e.status === "held");
      if (!data.running && !held.length) return null;
      return html`${data.running && html`<${Current} id=${id} e=${data.running} />`}
        ${held.map((e) => html`<${Current} key=${e.id} id=${id} e=${e} />`)}`;
    },
    episodes: () => html`<${Episodes} id=${id} data=${data} />`,
    settings: () => html`<${Settings} id=${id} data=${data} />`,
  };
}

/** Make an episode from its Info or its closed card: the text in its own small window. */
export function quick(id, action) {
  if (action === "gramophone.make") { making.value = { ...making.value, [id]: true }; return true; }
  return false;
}

function Making({ id }) {
  usePeek(id);
  const close = () => { making.value = { ...making.value, [id]: false }; };
  const data = (details.value[id] || {}).data;
  return html`<${Dialog} title=${say("Make an episode")} onCancel=${close} wide=${true}
      actions=${html`<button class="ok-btn" onClick=${close}>${say("Cancel")}</button>`}>
    ${data ? html`<${MakeForm} id=${id} data=${data} onDone=${close} />` : html`<p class="ok-tone-muted">${say("Loading…")}</p>`}
  </${Dialog}>`;
}

export function overlay() {
  return html`${Object.keys(making.value).filter((id) => making.value[id]).map((id) => html`<${Making} key=${id} id=${id} />`)}`;
}
