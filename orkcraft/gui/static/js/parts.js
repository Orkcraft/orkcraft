// A closed card's parts the person may hide (Task Fields: the orks' work, my chores, the scribbles; War
// Drum: meetings, schedules, limits): a row of checkboxes over the card, one per part, kept per building
// in this browser. A card with a part hidden is shorter; the town lifts the huts under it by what it
// lost (`lost`), measured against its height with every part shown.
import { signal } from "@preact/signals";
import { html, cls } from "./html.js";
import { say } from "./link.js";

const KEY = "parts.hidden.";
const TALL = "parts.tall.";
const hiddenParts = signal({});          // building id → [part key] hidden
const read = new Map();                  // building id → what this browser kept, read once
const tall = new Map();                  // building id → its height with every part shown, as last drawn

function kept(prefix, id, fallback) {
  try { const v = localStorage.getItem(prefix + id); return v === null ? fallback : JSON.parse(v); } catch { return fallback; }
}

function keep(prefix, id, value) {
  try { localStorage.setItem(prefix + id, JSON.stringify(value)); } catch { /* it holds till the page reloads */ }
}

/** The parts of building `id` the person hid. */
export function hidden(id) {
  const all = hiddenParts.value;
  if (all[id] !== undefined) return all[id];
  if (!read.has(id)) {
    const list = kept(KEY, id, []);
    read.set(id, Array.isArray(list) ? list : []);
  }
  return read.get(id);
}

export const shown = (id, part) => !hidden(id).includes(part);

function toggle(id, part) {
  const list = hidden(id);
  const next = list.includes(part) ? list.filter((p) => p !== part) : [...list, part];
  if (!list.length && tall.has(id)) keep(TALL, id, tall.get(id));     // its full height, for after a reload
  hiddenParts.value = { ...hiddenParts.value, [id]: next };
  keep(KEY, id, next);
}

/** The row of checkboxes: `parts` is [{key, label, mark?, title?}]. A press on it never opens or drags the hut. */
export function PartToggles({ id, parts }) {
  const stop = (e) => e.stopPropagation();
  return html`<div class="gui-parts" onPointerDown=${stop}>
    ${parts.map((p) => {
      const on = shown(id, p.key);
      return html`<label key=${p.key} class=${cls("ok-check gui-parts__one", { "is-off": !on })} role="checkbox" aria-checked=${on}
          title=${say(p.title || (on ? `Hide ${p.label}` : `Show ${p.label}`))}
          onClick=${(e) => { stop(e); toggle(id, p.key); }}>
        <i>${on ? "✓" : ""}</i>${p.mark && html`<span class=${p.tone ? `ok-tone-${p.tone}` : ""} aria-hidden="true">${p.mark}</span>`}${say(p.label)}</label>`;
    })}
  </div>`;
}

/** A hut drawn `h` high: with every part shown that is its full height; with some hidden, the pixels
 * it lost since (0 when it never stood with all shown in this browser). */
export function lost(id, h) {
  if (!hidden(id).length) {
    tall.set(id, h);
    return 0;
  }
  if (!tall.has(id)) tall.set(id, Number(kept(TALL, id, 0)) || 0);
  return Math.max(tall.get(id) - h, 0);
}
