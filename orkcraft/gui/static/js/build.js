// Changing the town: Build (the Warchief asked, or a building raised from the catalog), laying a road
// between two buildings and taking one up. The acts are the core's (gui/builder.py); the dialogs are the page's.
import { signal } from "@preact/signals";
import { useEffect, useState } from "preact/hooks";
import { html } from "./html.js";
import { town, command, act, say } from "./link.js";
import { Dialog } from "./dialog.js";
import { HandlerDialog } from "./acts.js";
import { opened, openBuilding, closeBuilding } from "./windows.js";

const HALL = "town_hall";                          // the Warchief's hall (js/buildings/town_hall.js)

export const building = signal(false);            // the Build dialog is open: true, or {hut: [x, y], need}
export const laying = signal(null);                // {from, to}: a road waits for what it carries
export const pickedRoad = signal(null);            // the road key the person clicked
export const demolishing = signal(null);           // the building id a Demolish dialog asks about
export const settingUp = signal(null);             // {id, type}: a building just raised, its setup asked in the Warchief's line

/** A building just raised: a type with a `Setup` of its own (js/types.js) is set up in the Warchief's line, in a
 *  question or two (docs/design/select-a-building.md §7); any other opens in its window as before. */
export function raised(id, type) {
  if (!id) return;
  import(`./buildings/${type}.js`).then(
    (m) => { if (m.Setup) settingUp.value = { id, type }; else openBuilding(id); },
    () => openBuilding(id));
}

/** Build, in one (docs/design/building-views.md §3, Town Hall): say what you need — the Warchief points
 *  at the building that does it (its chat offers to build it) — or pick one of the catalog, by what it is for. */
export function BuildDialog() {
  const [types, setTypes] = useState(null);
  const [need, setNeed] = useState("");
  const close = () => { building.value = false; setNeed(""); };
  useEffect(() => {
    if (building.value && types === null) command("town.catalog").then(setTypes, () => setTypes([]));
    if (building.value && building.value.need) setNeed(building.value.need);
  }, [building.value]);
  if (!building.value) return null;
  const hut = building.value.hut;
  const raise = (t) => command("town.build", hut ? { type: t.id, hut } : { type: t.id })
    .then((id) => { close(); raised(id, t.id); }, () => {});
  const ask = () => need.trim() && act(HALL, "ask", { text: `What should I build? ${need.trim()}` })
    .then(() => { close(); if (opened.value.active !== HALL) openBuilding(HALL); }, () => {});
  const groups = [];
  for (const t of types || []) {
    if (!groups.length || groups[groups.length - 1][0] !== t.intent) groups.push([t.intent, []]);
    groups[groups.length - 1][1].push(t);
  }
  return html`<${Dialog} title="Build" text=${say("Say what you need, or pick a building; its settings live in its window.")}
      onCancel=${close} actions=${html`<button class="ok-btn" onClick=${close}>Cancel</button>`}>
    <div class="gui-form__row">
      <input class="ok-input" autofocus placeholder=${say("What do you need? e.g. sort my inbox into tasks")}
        value=${need} onInput=${(e) => setNeed(e.target.value)} onKeyDown=${(e) => e.key === "Enter" && ask()} />
      <button class="ok-btn primary" style="flex:none" disabled=${!need.trim()} onClick=${ask}>${say("Ask the Warchief")}</button>
    </div>
    ${types === null ? html`<p class="ok-tone-muted">Looking…</p>` : html`<ul class="gui-catalog">
      ${groups.map(([intent, list]) => html`<li key=${intent} class="ok-font-heading ok-tone-muted">${intent}</li>
        ${list.map((t) => html`<li key=${t.id} class="gui-catalog__item" onClick=${() => raise(t)}>
          <b>${say(t.title)}</b>${t.agentic ? html` <span class="ok-word ok-tone-muted">agents</span>` : ""}
          <div class="ok-font-status ok-tone-muted">${t.summary}</div>
          ${t.sends.length > 0 && html`<div class="ok-font-status">sends: ${t.sends.join(" · ")}</div>`}
        </li>`)}`)}</ul>`}
  </${Dialog}>`;
}

/** A road in words, both ways in: + Listen on the receiver ({to, among}: the steward picks the source) and an
 *  arrow drawn from one building to another ({from, to}). Say what it should listen to and what to do with
 *  it — the steward offers roads (gui/road_planner.py, a job); picking by hand waits folded below. */
export function RoadDialog() {
  const pair = laying.value;
  const [choices, setChoices] = useState(null);
  const [words, setWords] = useState("");
  useEffect(() => {
    setChoices(null);
    if (pair && pair.from) command("roads.choices", { from: pair.from, to: pair.to }).then(setChoices, () => setChoices([]));
  }, [pair && pair.from, pair && pair.to]);
  useEffect(() => setWords(""), [pair && pair.to]);
  if (!pair) return null;
  const close = () => { laying.value = null; };
  const titles = Object.fromEntries(town.value.buildings.map((b) => [b.id, say(b.title)]));
  const lay = (c) => command("roads.lay", { from: pair.from, to: pair.to, event: c.event, handler: c.handler })
    .then(close, () => {});
  const find = () => words.trim() && command("roads.plan", { to: pair.to, from: pair.from || "", prompt: words.trim(),
    among: pair.among || null }).then(close, () => {});
  const sources = (pair.among || []).filter((id) => id !== pair.to && titles[id]);
  const title = pair.from ? `${say("Road")}: ${titles[pair.from]} → ${titles[pair.to]}` : say(`Listen — ${titles[pair.to]}`);
  return html`<${Dialog} title=${title} text=${pair.from ? say("What should the road carry, and what should happen to it?")
      : say("What should it listen to, and what should happen to it?")} onCancel=${close}
      actions=${html`<button class="ok-btn" onClick=${close}>Cancel</button>
        <button class="ok-btn primary" disabled=${!words.trim()} onClick=${find}>Find the road</button>`}>
    <textarea class="ok-input gui-textarea" rows="3" autofocus value=${words} onInput=${(e) => setWords(e.target.value)}
      onKeyDown=${(e) => e.key === "Enter" && (e.ctrlKey || e.metaKey) && find()}
      placeholder=${say("e.g. listen to unread messages and make to-dos of them")}></textarea>
    <details class="gui-road__manual">
      <summary class="ok-font-label ok-tone-muted">${pair.from ? "Pick the event by hand" : "Pick the building by hand"}</summary>
      ${!pair.from ? html`<ul class="gui-catalog">${sources.map((id) => html`<li key=${id} class="gui-catalog__item"
          onClick=${() => { laying.value = { ...pair, from: id }; }}><b>${titles[id]}</b></li>`)}</ul>`
      : choices === null ? html`<p class="ok-tone-muted">Looking…</p>`
      : !choices.length ? html`<p class="ok-tone-muted">${say("No plain road fits")} from ${titles[pair.from]} to ${titles[pair.to]}.
          Describe it above: an ork will handle it by a rule.</p>`
      : html`<div class="gui-orders__options">${choices.map((c) => html`<button key=${c.event + (c.handler || "")}
          class="ok-btn" onClick=${() => lay(c)}>${c.label}</button>`)}</div>`}
    </details>
  </${Dialog}>`;
}

/** The road the person clicked: every road from one building into the same other one is one road
 *  (js/town.js together), so its card lists each of them — what it carries, its handler, taking it up —
 *  and lays another between them (the TUI's road console: H, U; docs/design/road-sound.md §2). */
export function RoadBar() {
  const key = pickedRoad.value;
  const t = town.value;
  const [handling, setHandling] = useState(null);
  const road = key && t.roads.find((r) => r.id === key);
  if (!road) return null;
  const titles = Object.fromEntries(t.buildings.map((b) => [b.id, say(b.title)]));
  const name = (id) => titles[id] || id;
  const group = t.roads.filter((r) => r.from === road.from && r.to === road.to);
  const remove = (r) => command("roads.remove", { key: r.id })
    .then(() => { if (group.length === 1 || r.id === key) pickedRoad.value = group.find((x) => x.id !== r.id)?.id || null; }, () => {});
  return html`<div class="gui-roadbar ok-toast">
    <div class="gui-roadbar__head">
      <span><b>${name(road.from)}</b> → <b>${name(road.to)}</b>${group.length > 1 ? html` <span class="ok-tone-muted">· ${group.length} ${say("events")}</span>` : ""}</span>
      <button class="ok-act" title=${say("Lay another road between these two buildings")}
        onClick=${() => { laying.value = { from: road.from, to: road.to }; }}><span class="ok-act__label">${say("Add an event")}</span></button>
      <button class="ok-act" onClick=${() => { pickedRoad.value = null; }}><span class="ok-act__label">Close</span></button>
    </div>
    <ul class="gui-roadbar__list">${group.map((r) => html`<li key=${r.id} class="gui-roadbar__row">
      <span class="gui-roadbar__what">${r.label}${r.handler ? html`<span class="ok-tone-muted"> · ${r.handler}</span>` : ""}</span>
      <button class="ok-act" onClick=${() => setHandling(r)}><span class="ok-act__label">${say("Handler")}</span></button>
      <button class="ok-act" onClick=${() => remove(r)}><span class="ok-act__label">Remove</span></button>
    </li>`)}</ul>
  </div>
  ${handling && html`<${HandlerDialog} road=${{ key: handling.id, title: name(handling.from), label: handling.label }}
    onClose=${() => setHandling(null)} onDone=${() => {}} />`}`;
}

/** Demolish asked from the hut's menu or the Warchief's line. */
export function DemolishAsked() {
  const id = demolishing.value;
  const b = id && town.value.buildings.find((x) => x.id === id);
  if (!b) return null;
  return html`<${Demolish} b=${b} onClose=${() => { demolishing.value = null; }} />`;
}

export function Demolish({ b, onClose }) {
  return html`<${Dialog} title=${`Demolish ${say(b.title)}?`} warn onCancel=${onClose}
      text=${say("It leaves the town and stops its work; its settings and chronicle stay, and git keeps the rest.")}
      actions=${html`<button class="ok-btn" onClick=${onClose}>Cancel</button>
        <button class="ok-btn danger" onClick=${() => command("town.demolish", { id: b.id }).then(() => { onClose(); closeBuilding(b.id); }, () => {})}>Demolish</button>`} />`;
}
