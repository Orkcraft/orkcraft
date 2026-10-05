// 📯 The Horn: road or event → sound (core/workers/horn.py). The page plays the sounds: the hut card
// counts what the worker asked for (`plays`) and each new one is played here, at this page's volume
// (kept per building in this browser). Built-in sounds and audio files come from the `audio` act; the
// bell is made here.
import { signal } from "@preact/signals";
import { useEffect, useState } from "preact/hooks";
import { html, cls } from "../html.js";
import { act, say } from "../link.js";

const heard = new Map();             // building id → the last `plays` this page has played
const audio = new Map();             // building id + sound → Promise of its data URL ("" for the bell)
const volumes = signal({});          // building id → 0..1, as the slider stands
let context = null;

function volumeOf(id) {
  if (volumes.value[id] !== undefined) return volumes.value[id];
  let v = 0.8;
  try { const kept = localStorage.getItem(`horn.volume.${id}`); if (kept !== null) v = Number(kept); } catch { /* none */ }
  return Number.isFinite(v) ? Math.min(Math.max(v, 0), 1) : 0.8;
}

function setVolume(id, v) {
  volumes.value = { ...volumes.value, [id]: v };
  try { localStorage.setItem(`horn.volume.${id}`, String(v)); } catch { /* the slider still works */ }
}

function bell(volume) {
  try {
    context = context || new AudioContext();
    const osc = context.createOscillator(), gain = context.createGain();
    osc.frequency.value = 880;
    gain.gain.setValueAtTime(volume * 0.3, context.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.001, context.currentTime + 0.25);
    osc.connect(gain).connect(context.destination);
    osc.start();
    osc.stop(context.currentTime + 0.25);
  } catch { /* no Web Audio here */ }
}

/** Play `sound` of building `id` at its volume. */
export function play(id, sound) {
  if (!sound || sound === "none") return;
  const volume = volumeOf(id);
  if (sound === "bell") { bell(volume); return; }
  const key = `${id}\n${sound}`;
  if (!audio.has(key)) audio.set(key, act(id, "audio", { sound }).then((r) => r.url, () => { audio.delete(key); return ""; }));
  audio.get(key).then((url) => {
    if (!url) { bell(volume); return; }
    const a = new Audio(url);
    a.volume = volume;
    a.play().catch(() => {});
  });
}

const stop = (e) => e.stopPropagation();      // a control on the hut is not a press on the hut

function HornCard({ b }) {
  const c = b.card;
  useEffect(() => {
    const before = heard.get(b.id);
    heard.set(b.id, c.plays);
    if (before !== undefined && c.plays > before) play(b.id, c.played);
  }, [b.id, c.plays]);
  const volume = volumeOf(b.id);
  return html`<div class="ok-row" onPointerDown=${stop} onClick=${stop}>
    <button class=${cls("ok-chip", { "is-on": !c.muted })} aria-pressed=${!c.muted}
      title=${say(c.muted ? "Muted: click to sound again" : "Sounding: click to mute")}
      onClick=${() => act(b.id, "mute").catch(() => {})}>${c.muted ? "Muted" : "Sound on"}</button>
    <input type="range" min="0" max="1" step="0.05" value=${volume} disabled=${c.muted} style="width: 7em; accent-color: var(--frame-focus)"
      aria-label=${say("Volume")} title=${say(`Volume ${Math.round(volume * 100)}%`)}
      onInput=${(e) => setVolume(b.id, Number(e.target.value))}
      onChange=${(e) => play(b.id, c.played || "horn")} />
  </div>`;
}

/** Closed: the mute toggle and the volume slider, right on the card (docs/design/building-views.md). */
export function card(b) {
  return b.card ? html`<${HornCard} b=${b} />` : null;
}

/** The Command Card's quick actions, done here: Test plays everything else, Mute flips it. */
export function quick(id, action) {
  if (action === "horn.test") { act(id, "test", { event: "*" }).catch(() => {}); return true; }
  if (action === "horn.mute") { act(id, "mute").catch(() => {}); return true; }
  return false;
}

function when(at) {
  return (at || "").slice(11, 16);
}

function Calls({ calls }) {
  if (!calls.length) return html`<p class="ok-tone-muted">Nothing has sounded yet.</p>`;
  return html`<ul class="ok-list__items">${calls.map((c, i) => html`<li key=${i} class=${cls("ok-item", { "is-disabled": !c.heard })}>
    <span>${c.sound}</span><span>${c.title || c.event}</span>
    <span class="meta">${c.heard ? "" : `${say("kept quiet")}: ${say(c.why)} · `}${c.from} · ${when(c.at)}</span></li>`)}</ul>`;
}

function Rows({ id, rows, picked, onPick }) {
  return html`<ul class="ok-list__items">${rows.map((r) => {
    const key = `${r.source}/${r.event}`;
    return html`<li key=${key} class=${cls("ok-item", { "is-selected": picked === key })}
        title=${say("Click: the next sound, played")}
        onClick=${() => { if (onPick) onPick(key); act(id, "cycle", { source: r.source, event: r.event }).catch(() => {}); }}>
      <b>${r.file ? r.sound.split("/").pop() : r.sound}</b>
      <span>${say(r.label)}</span>${r.event !== "*" && html`<span class="meta">${r.from}</span>`}</li>`;
  })}</ul>`;
}

/** Command: road or event → sound (a click moves to the next and plays it), the last calls. */
export function preview(id, d) {
  return html`<div class="gui-rows">
    ${d.rows.length === 1 && html`<p class="ok-tone-muted">No road comes here yet: pull one from another building's +.</p>`}
    <${Rows} id=${id} rows=${d.rows} />
    <p class="ok-list__head">Last calls</p>
    <${Calls} calls=${d.calls.slice(0, 5)} />
  </div>`;
}

function Settings({ id, d }) {
  const [quiet, setQuiet] = useState(d.quiet);
  const [cooldown, setCooldown] = useState(String(d.cooldown));
  useEffect(() => { setQuiet(d.quiet); setCooldown(String(d.cooldown)); }, [d.quiet, d.cooldown]);
  const save = (args) => act(id, "settings", args).catch(() => {});
  return html`<div class="gui-head">
    <button class=${cls("ok-chip", { "is-on": d.muted })} onClick=${() => act(id, "mute").catch(() => {})}>
      ${d.muted ? "Muted" : "Mute"}</button>
    <label class="gui-field">Quiet hours
      <input class="ok-input" placeholder="22:00-08:00" value=${quiet} style="width: 9em"
        onInput=${(e) => setQuiet(e.target.value)} onBlur=${() => quiet !== d.quiet && save({ quiet })}
        onKeyDown=${(e) => e.key === "Enter" && save({ quiet })} /></label>
    <label class="gui-field">Pause between two sounds, s
      <input class="ok-input" type="number" min="0" max="600" value=${cooldown} style="width: 5em"
        onInput=${(e) => setCooldown(e.target.value)}
        onBlur=${() => cooldown !== String(d.cooldown) && save({ cooldown: Number(cooldown) })}
        onKeyDown=${(e) => e.key === "Enter" && save({ cooldown: Number(cooldown) })} /></label>
    <label class="gui-field">Default
      <select class="ok-input" value=${d.default} style="width: 8em" onChange=${(e) => save({ default: e.target.value })}>
        ${d.sounds.map((s) => html`<option key=${s.id} value=${s.id} title=${s.about}>${s.id}</option>`)}
        ${!d.sounds.some((s) => s.id === d.default) && html`<option value=${d.default}>${d.default}</option>`}
      </select></label>
    ${d.problems.map((p) => html`<span key=${p} class="ok-tone-wait">⚠ ${p}</span>`)}
  </div>`;
}

function Row({ id, r, sounds }) {
  const [file, setFile] = useState(r.file ? r.sound : "");
  useEffect(() => setFile(r.file ? r.sound : ""), [r.sound]);
  const set = (sound) => act(id, "set", { source: r.source, event: r.event, sound }).catch(() => {});
  return html`<tr>
    <td>${say(r.label)}${r.event !== "*" && html` <span class="ok-tone-muted">· ${r.from}</span>`}</td>
    <td><select class="ok-input" value=${r.file ? "" : r.sound} onChange=${(e) => e.target.value && set(e.target.value)}>
      ${r.file && html`<option value="">audio file</option>`}
      ${sounds.map((s) => html`<option key=${s.id} value=${s.id} title=${s.about}>${s.id}</option>`)}</select></td>
    <td><input class="ok-input" placeholder="sounds/ping.mp3" value=${file}
      title=${say("An audio file of the project (.wav, .mp3, .ogg…)")}
      onInput=${(e) => setFile(e.target.value)} onKeyDown=${(e) => e.key === "Enter" && file.trim() && set(file.trim())} /></td>
    <td><span class="ok-row">
      <button class="ok-act" disabled=${!file.trim() || file === r.sound} onClick=${() => set(file.trim())}>
        <span class="ok-act__label">Use file</span></button>
      <button class="ok-act" onClick=${() => act(id, "test", { source: r.source, event: r.event }).catch(() => {})}>
        <span class="ok-act__label">Play</span></button></span></td>
  </tr>`;
}

function Table({ id, d }) {
  return html`<div><table style="width: 100%">
    <thead><tr><th>Road or event</th><th>Sound</th><th>Or an audio file</th><th></th></tr></thead>
    <tbody>${d.rows.map((r) => html`<${Row} key=${`${r.source}/${r.event}`} id=${id} r=${r} sounds=${d.sounds} />`)}</tbody>
  </table></div>`;
}

/** Full: the table with an audio file per row, quiet hours, the pause, the whole log. */
export function panes(id, d) {
  return {
    settings: () => html`<${Settings} id=${id} d=${d} />`,
    table: () => html`<${Table} id=${id} d=${d} />`,
    log: () => html`<div><p class="ok-list__head">Every call</p><${Calls} calls=${d.calls} /></div>`,
  };
}
