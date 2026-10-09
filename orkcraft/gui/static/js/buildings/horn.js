// 📯 The Horn: road or event → sound (core/workers/horn.py). The page plays the sounds: the hut card
// counts what the worker asked for (`plays`) and each new one is played here, at this page's volume
// (kept per building in this browser). Built-in sounds and audio files come from the `audio` act; the
// bell is made here. Closed: how many calls it sounded today (or Muted, Quiet hours), the mute toggle and
// the volume slider, the last call. Open, made for the half panel: Sound on and the volume on one line,
// the quiet hours, the pause and the default folded beside them; a row per road with its sound and Play;
// every call under them.
import { signal } from "@preact/signals";
import { useEffect, useState } from "preact/hooks";
import { html, cls } from "../html.js";
import { act, say } from "../link.js";

const sheet = new URL("./horn.css", import.meta.url).href;
if (!document.querySelector(`link[href="${sheet}"]`)) {
  const link = document.createElement("link");
  link.rel = "stylesheet";
  link.href = sheet;
  document.head.appendChild(link);
}

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

/** A time as a card says it: today's as 09:21, an older one as 10-06. */
function stamp(at) {
  if (!at) return "";
  const d = new Date();
  const today = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
  return at.slice(0, 10) === today ? at.slice(11, 16) : at.slice(5, 10);
}

/** Sound on / Muted, and this page's volume beside it (`play` hears the new volume when it is let go). */
function Volume({ id, muted, played }) {
  const volume = volumeOf(id);
  return html`<span class="gui-horn__volume">
    <button class=${cls("ok-chip", { "is-on": !muted })} aria-pressed=${!muted}
      title=${say(muted ? "Muted: click to sound again" : "Sounding: click to mute")}
      onClick=${() => act(id, "mute").catch(() => {})}>${muted ? say("Muted") : say("Sound on")}</button>
    <input type="range" class="gui-horn__slider" min="0" max="1" step="0.05" value=${volume} disabled=${muted}
      aria-label=${say("Volume")} title=${say(`Volume ${Math.round(volume * 100)}%`)}
      onInput=${(e) => setVolume(id, Number(e.target.value))}
      onChange=${() => play(id, played || "horn")} />
  </span>`;
}

function HornCard({ b }) {
  const c = b.card;
  useEffect(() => {
    const before = heard.get(b.id);
    heard.set(b.id, c.plays);
    if (before !== undefined && c.plays > before) play(b.id, c.played);
  }, [b.id, c.plays]);
  const last = c.last;
  return html`<div class="gui-hut__body-in">
    ${c.muted ? html`<div class="gui-hut__big ok-tone-wait">⚠ ${say("Muted")}<small>${say("nothing sounds")}</small></div>`
      : c.quiet_now ? html`<div class="gui-hut__big ok-tone-wait">${say("Quiet hours")}<small>${c.quiet}</small></div>`
      : html`<div class="gui-hut__big">${c.today ?? 0}<small>${say("sounded today")}${c.kept ? ` · ${c.kept} ${say("kept quiet")}` : ""}</small></div>`}
    <div class="gui-hut__text gui-horn__row" onPointerDown=${stop} onClick=${stop}>
      <${Volume} id=${b.id} muted=${c.muted} played=${c.played} /></div>
    ${last && html`<div class="gui-hut__foot"><span class=${last.heard ? "" : "ok-tone-muted"}>${last.sound} · ${last.title}${last.heard ? "" : ` · ${say("kept quiet")}: ${say(last.why)}`}</span>
      <span class="gui-hut__when">${stamp(last.at)}</span></div>`}
  </div>`;
}

/** Closed: how many calls it sounded today, the mute toggle and the volume slider right on the card, the
 *  last call (docs/design/building-views.md). */
/** No view of its own: in Camp it stands with no card, its house and its name alone (js/hut.js bareOf). */
export const bare = true;

export function card(b) {
  return b.card ? html`<${HornCard} b=${b} />` : null;
}

/** Its Info's quick actions, done here: Test plays everything else, Mute flips it. */
export function quick(id, action) {
  if (action === "horn.test") { act(id, "test", { event: "*" }).catch(() => {}); return true; }
  if (action === "horn.mute") { act(id, "mute").catch(() => {}); return true; }
  return false;
}

// -- open ----------------------------------------------------------------------------------------------

/** The head: Sound on and the volume; the quiet hours, the pause and the default folded to one line. */
function Settings({ id, d }) {
  const [quiet, setQuiet] = useState(d.quiet);
  const [cooldown, setCooldown] = useState(String(d.cooldown));
  useEffect(() => { setQuiet(d.quiet); setCooldown(String(d.cooldown)); }, [d.quiet, d.cooldown]);
  const save = (args) => act(id, "settings", args).catch(() => {});
  const last = d.calls.find((c) => c.heard);
  return html`<div class="gui-horn__head">
    <div class="gui-horn__bar">
      <${Volume} id=${id} muted=${d.muted} played=${last ? last.sound : d.default} />
      ${d.problems.map((p) => html`<span key=${p} class="ok-tone-wait">⚠ ${p}</span>`)}
      <span class="gui-horn__spacer"></span>
      <button class="ok-btn" title=${say("Plays the sound of everything else")} onClick=${() => act(id, "test", { event: "*" }).catch(() => {})}>${say("Test")}</button>
    </div>
    <details class="gui-horn__fold">
      <summary><span>${say("Quiet hours")} ${d.quiet || say("none")} · ${say("pause")} ${d.cooldown} s · ${say("default")} ${d.default}</span></summary>
      <div class="gui-horn__settings">
        <label class="gui-field">${say("Quiet hours")}
          <input class="ok-input" placeholder="22:00-08:00" value=${quiet} style="width: 9em"
            onInput=${(e) => setQuiet(e.target.value)} onBlur=${() => quiet !== d.quiet && save({ quiet })}
            onKeyDown=${(e) => e.key === "Enter" && save({ quiet })} /></label>
        <label class="gui-field">${say("Pause between two sounds, s")}
          <input class="ok-input" type="number" min="0" max="600" value=${cooldown} style="width: 5em"
            onInput=${(e) => setCooldown(e.target.value)}
            onBlur=${() => cooldown !== String(d.cooldown) && save({ cooldown: Number(cooldown) })}
            onKeyDown=${(e) => e.key === "Enter" && save({ cooldown: Number(cooldown) })} /></label>
        <label class="gui-field">${say("Default sound")}
          <select class="ok-input" value=${d.default} style="width: 8em" onChange=${(e) => save({ default: e.target.value })}>
            ${d.sounds.map((s) => html`<option key=${s.id} value=${s.id} title=${s.about}>${s.id}</option>`)}
            ${!d.sounds.some((s) => s.id === d.default) && html`<option value=${d.default}>${d.default}</option>`}
          </select></label>
      </div>
    </details>
  </div>`;
}

const FILE = "\u0000file";          // the select's "an audio file…" choice

/** A road or event: its sound (a built-in one, or an audio file written in under it), and Play. */
function Row({ id, r, sounds }) {
  const [file, setFile] = useState(r.file ? r.sound : "");
  const [asFile, setAsFile] = useState(r.file);
  useEffect(() => { setFile(r.file ? r.sound : ""); setAsFile(r.file); }, [r.sound]);
  const set = (sound) => act(id, "set", { source: r.source, event: r.event, sound }).catch(() => {});
  return html`<li class="gui-horn__rule">
    <span class="gui-horn__what">${say(r.label)}${r.event !== "*" && html` <span class="ok-tone-muted">· ${say(r.from)}</span>`}</span>
    <select class="ok-input gui-horn__sound" value=${asFile ? FILE : r.sound} aria-label=${say(`Sound for ${r.label}`)}
      onChange=${(e) => { if (e.target.value === FILE) setAsFile(true); else { setAsFile(false); set(e.target.value); } }}>
      ${sounds.map((s) => html`<option key=${s.id} value=${s.id} title=${s.about}>${s.id}</option>`)}
      <option value=${FILE}>${say("an audio file…")}</option></select>
    <button class="ok-btn gui-horn__play" aria-label=${say(`Play the sound for ${r.label}`)} title=${say("Play it")}
      onClick=${() => act(id, "test", { source: r.source, event: r.event }).catch(() => {})}>▶</button>
    ${asFile && html`<span class="gui-horn__file">
      <input class="ok-input" placeholder="sounds/ping.mp3" value=${file} aria-label=${say("An audio file of the project")}
        title=${say("An audio file of the project (.wav, .mp3, .ogg…)")}
        onInput=${(e) => setFile(e.target.value)} onKeyDown=${(e) => e.key === "Enter" && file.trim() && set(file.trim())} />
      <button class="ok-btn" disabled=${!file.trim() || file === r.sound} onClick=${() => set(file.trim())}>${say("Use file")}</button></span>`}
  </li>`;
}

function Table({ id, d }) {
  if (!d.rows.length) return html`<p class="ok-tone-muted">${say("No roads come in yet — lay one to it from a building.")}</p>`;
  return html`<ul class="gui-horn__rules">${d.rows.map((r) => html`<${Row} key=${`${r.source}/${r.event}`} id=${id} r=${r} sounds=${d.sounds} />`)}</ul>`;
}

function Calls({ calls }) {
  if (!calls.length) return html`<p class="ok-tone-muted">${say("Nothing has sounded yet — Test plays a sound.")}</p>`;
  const heardN = calls.filter((c) => c.heard).length;
  return html`<div class="gui-horn__calls">
    <p class="gui-horn__sum"><b>${calls.length}</b> ${say(calls.length === 1 ? "call" : "calls")} · ${heardN} ${say("sounded")} · ${calls.length - heardN} ${say("kept quiet")}</p>
    <ul class="gui-horn__log">${calls.map((c, i) => html`<li key=${i} class=${cls("gui-horn__call", { "is-quiet": !c.heard })}>
      <span class="gui-horn__at">${stamp(c.at)}</span>
      <span class="gui-horn__snd">${c.heard ? "♪" : "–"} ${c.sound}</span>
      <span class="gui-horn__title">${c.title || c.event}</span>
      <span class="gui-horn__from">${c.heard ? "" : `${say("kept quiet")}: ${say(c.why)} · `}${say(c.from)}</span></li>`)}</ul>
  </div>`;
}

/** The window by its UI document (design/buildings/horn.json). */
export function panes(id, d) {
  return {
    settings: () => html`<${Settings} id=${id} d=${d} />`,
    table: () => html`<${Table} id=${id} d=${d} />`,
    log: () => html`<${Calls} calls=${d.calls} />`,
  };
}
