// The town in a narrow window (a phone, docs/design/mobile.md §1: a glance, a tap, back in the pocket): no map,
// no roads — the buildings as a list of their cards, closed to one line each, what wants the person first.
// A tap opens a card in place (its live status and its quick actions); Open takes the whole building.
import { signal } from "@preact/signals";
import { html, cls } from "./html.js";
import { openBuilding } from "./windows.js";
import { busy as busyOf } from "./fold.js";
import { Card, Mark, QuickTray } from "./hut.js";
import { TypeIcon, OrkHead } from "./icons.js";
import { say } from "./link.js";

const WIDTH = "(max-width: 640px)";
const query = typeof matchMedia === "function" ? matchMedia(WIDTH) : null;
export const narrow = signal(!!(query && query.matches));
if (query) query.addEventListener("change", (e) => { narrow.value = e.matches; });

const unfolded = signal(null);              // the one building whose card is open in the list

/** What a building's line says closed: its own mark (what its folded card says first), else its first status line. */
function Gist({ b }) {
  const mark = Mark({ b });
  if (mark) return mark;
  const line = (b.status_plain || [])[0];
  return line ? html`<span class="ok-tone-muted">${say(line)}</span>` : null;
}

function Row({ b, number }) {
  const open = unfolded.value === b.id;
  const lead = b.garrison.find((o) => o.lead) || b.garrison[0];
  const toggle = () => { unfolded.value = open ? null : b.id; };
  return html`<li class=${cls("gui-pocket__row ok-hut", { "is-open": open, "is-alert": !!b.alert, "is-busy": busyOf(b) })}>
    <button class="gui-pocket__head" aria-expanded=${open} onClick=${toggle}>
      <span class="gui-pocket__no">${number}</span>
      <${TypeIcon} type=${b.type} />
      <span class="gui-pocket__name">${say(b.title)}</span>
      <span class="gui-pocket__gist">${b.alert ? html`<span class="ok-tone-wait">❓ ${say("asks you")}</span>` : html`<${Gist} b=${b} />`}</span>
      ${lead && (b.alert || busyOf(b)) && html`<${OrkHead} o=${lead} alert=${!!b.alert} />`}
      <span class="gui-pocket__chev" aria-hidden="true">${open ? "▾" : "▸"}</span>
    </button>
    ${open && html`<div class="gui-pocket__body">
      <${Card} b=${b} />
      <div class="gui-pocket__acts">
        <${QuickTray} b=${b} />
        <button class="ok-btn primary" onClick=${() => openBuilding(b.id)}>${say("Open")}</button>
      </div>
    </div>`}
  </li>`;
}

export function Pocket({ buildings }) {
  const numbered = buildings.map((b, i) => ({ b, n: i + 1 }));
  const asks = numbered.filter((x) => x.b.alert);
  const working = numbered.filter((x) => !x.b.alert && busyOf(x.b));
  const rest = numbered.filter((x) => !x.b.alert && !busyOf(x.b));
  const group = (label, list) => list.length > 0 && html`<section class="gui-pocket__group">
    <h2 class="ok-list__head">${say(label)} <span class="ok-tone-muted">${list.length}</span></h2>
    <ul class="gui-pocket__list">${list.map((x) => html`<${Row} key=${x.b.id} b=${x.b} number=${x.n} />`)}</ul>
  </section>`;
  return html`<main class="ok-ground gui-town gui-pocket">
    ${group("Asks you", asks)}${group("At work", working)}${group("Buildings", rest)}
    ${!buildings.length && html`<p class="gui-empty ok-font-body ok-tone-muted">${say("No buildings in this orkspace yet.")}</p>`}
  </main>`;
}
