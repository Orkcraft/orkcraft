// Changing the town: raising a building from the catalog, laying a road between two buildings and
// taking one up. The acts are the core's (gui/builder.py); the dialogs are the page's.
import { signal } from "@preact/signals";
import { useEffect, useState } from "preact/hooks";
import { html, cls } from "./html.js";
import { town, command, say } from "./link.js";
import { Dialog } from "./dialog.js";
import { HandlerDialog } from "./acts.js";
import { openBuilding, closeBuilding } from "./windows.js";

export const building = signal(false);            // the Build dialog is open
export const laying = signal(null);                // {from, to}: a road waits for what it carries
export const pickedRoad = signal(null);            // the road key the person clicked

export function BuildDialog() {
  const [types, setTypes] = useState(null);
  const close = () => { building.value = false; };
  useEffect(() => { if (building.value && types === null) command("town.catalog").then(setTypes, () => setTypes([])); },
            [building.value]);
  if (!building.value) return null;
  const raise = (t) => command("town.build", { type: t.id }).then((id) => { close(); openBuilding(id); }, () => {});
  return html`<${Dialog} title="Build" text=${say("A building straight from the catalog, with its defaults; its settings live in its window.")}
      onCancel=${close} actions=${html`<button class="ok-btn" onClick=${close}>Cancel</button>`}>
    ${types === null ? html`<p class="ok-tone-muted">Looking…</p>` : html`<ul class="gui-catalog">
      ${types.map((t) => html`<li key=${t.id} class="gui-catalog__item" onClick=${() => raise(t)}>
        <b>${say(t.title)}</b>${t.agentic ? html` <span class="ok-word ok-tone-muted">agents</span>` : ""}
        <div class="ok-font-status ok-tone-muted">${t.summary}</div>
        ${t.sends.length > 0 && html`<div class="ok-font-status">sends: ${t.sends.join(" · ")}</div>`}
      </li>`)}</ul>`}
  </${Dialog}>`;
}

export function RoadDialog() {
  const pair = laying.value;
  const [choices, setChoices] = useState(null);
  useEffect(() => {
    setChoices(null);
    if (pair) command("roads.choices", { from: pair.from, to: pair.to }).then(setChoices, () => setChoices([]));
  }, [pair && pair.from, pair && pair.to]);
  if (!pair) return null;
  const close = () => { laying.value = null; };
  const titles = Object.fromEntries(town.value.buildings.map((b) => [b.id, say(b.title)]));
  const lay = (c) => command("roads.lay", { from: pair.from, to: pair.to, event: c.event, handler: c.handler })
    .then(close, () => {});
  return html`<${Dialog} title=${`${say("Road")}: ${titles[pair.from]} → ${titles[pair.to]}`}
      text=${say("What the road carries, and who takes it at the other end.")} onCancel=${close}
      actions=${html`<button class="ok-btn" onClick=${close}>Cancel</button>`}>
    ${choices === null ? html`<p class="ok-tone-muted">Looking…</p>`
      : !choices.length ? html`<p class="ok-tone-muted">${say("No plain road fits")} from ${titles[pair.from]} to ${titles[pair.to]}.
          A road an ork handles by a rule (Listen with a prompt) is laid in the TUI for now.</p>`
      : html`<div class="gui-orders__options">${choices.map((c) => html`<button key=${c.event + (c.handler || "")}
          class="ok-btn" onClick=${() => lay(c)}>${c.label}</button>`)}</div>`}
  </${Dialog}>`;
}

/** The road the person clicked: what it is, its handler and taking it up (the TUI's road console: H, U). */
export function RoadBar() {
  const key = pickedRoad.value;
  const t = town.value;
  const [handling, setHandling] = useState(false);
  const road = key && t.roads.find((r) => r.id === key);
  if (!road) return null;
  const titles = Object.fromEntries(t.buildings.map((b) => [b.id, say(b.title)]));
  return html`<div class="gui-roadbar ok-toast">
    <span><b>${titles[road.from] || road.from}</b> → <b>${titles[road.to] || road.to}</b> · ${road.label}${road.handler ? ` · ${road.handler}` : ""}</span>
    <button class="ok-act" onClick=${() => setHandling(true)}><span class="ok-act__label">${say("Handler")}</span></button>
    <button class="ok-act" onClick=${() => command("roads.remove", { key }).then(() => { pickedRoad.value = null; }, () => {})}>
      <span class="ok-act__label">Remove</span></button>
    <button class="ok-act" onClick=${() => { pickedRoad.value = null; }}><span class="ok-act__label">Close</span></button>
  </div>
  ${handling && html`<${HandlerDialog} road=${{ key, title: titles[road.from] || road.from, label: road.label }}
    onClose=${() => setHandling(false)} onDone=${() => {}} />`}`;
}

export function Demolish({ b, onClose }) {
  return html`<${Dialog} title=${`Demolish ${say(b.title)}?`} warn onCancel=${onClose}
      text=${say("It leaves the town and stops its work; its settings and chronicle stay, and git keeps the rest.")}
      actions=${html`<button class="ok-btn" onClick=${onClose}>Cancel</button>
        <button class="ok-btn danger" onClick=${() => command("town.demolish", { id: b.id }).then(() => { onClose(); closeBuilding(b.id); }, () => {})}>Demolish</button>`} />`;
}
