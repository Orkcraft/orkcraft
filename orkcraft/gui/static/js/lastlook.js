// "Since your last look" (docs/design/audience.md §2a; core/last_look.py, realm/last_look.py): what greets the person
// when they come back, measured from their last look. The page tells the town when it is in front of them (focused
// and visible for LOOK_MIN_S, then a beat every BEAT_S); the town decides whether a new look began and what to say.
// One column, so it can become the phone's first screen: what was built, the questions (one tap), the problems with
// what each waits for, what it cost. Never an endless list, no counters to clear; the camp stays alive behind it.
import { useEffect } from "preact/hooks";
import { html } from "./html.js";
import { command, say, town } from "./link.js";
import { openBuilding } from "./windows.js";
import { openOrders } from "./orders.js";

const LOOK_MIN_S = 5;          // realm/last_look.py keeps the same
const BEAT_S = 30;
const QUIET_S = 12;            // "nothing new" says its line and goes back to the camp by itself

function inFront() {
  return document.visibilityState === "visible" && document.hasFocus();
}

// Counts the seconds the window has been in front; beats once it is a look, then every BEAT_S while it stays.
let front = 0;
function watchLooks() {
  setInterval(() => {
    if (!inFront()) { front = 0; return; }
    front += 1;
    if (front === LOOK_MIN_S || (front > LOOK_MIN_S && (front - LOOK_MIN_S) % BEAT_S === 0)) {
      command("look.beat").catch(() => {});
    }
  }, 1000);
}
watchLooks();

const done = () => command("look.done").catch(() => {});

function More({ n, what, onOpen }) {
  if (!n) return null;
  return html`<button class="ok-btn gui-lastlook__more" onClick=${onOpen}>and ${n} more ${what}</button>`;
}

function Built({ built }) {
  if (!built.items.length && !built.moved) return null;
  return html`<section class="gui-lastlook__part">
    <h4 class="ok-dialog__section">What was built</h4>
    ${(built.more > 0 || built.moved > 0) && html`<p class="ok-font-body">${say(built.summary)}</p>`}
    ${built.items.length > 0 && html`<ul class="gui-rows">${built.items.map((b, k) => html`<li key=${k}
        class="ok-font-body gui-lastlook__row"><span>${b.line}</span>
        ${b.building && html`<button class="ok-btn" onClick=${() => { done(); openBuilding(b.building, "work"); }}>Open</button>`}
      </li>`)}</ul>`}
    ${built.more > 0 && html`<p class="ok-font-status ok-tone-muted">and ${built.more} more</p>`}
  </section>`;
}

function Questions({ questions }) {
  if (!questions.items.length) return null;
  const answer = (q, key) => command("orders.answer", { id: q.id, key }).catch(() => {});
  return html`<section class="gui-lastlook__part">
    <h4 class="ok-dialog__section">Questions</h4>
    ${questions.items.map((q) => html`<div key=${q.id} class="gui-lastlook__ask">
      <p class="ok-font-body"><b>${q.who ? `${q.who}: ` : ""}</b>${q.title}</p>
      <div class="gui-lastlook__options">
        ${q.options.map(([key, label]) => html`<button key=${key} class="ok-btn" onClick=${() => answer(q, key)}>${label}</button>`)}
        ${q.building && html`<button class="ok-btn" onClick=${() => { done(); openBuilding(q.building, "work"); }}>Answer in a line</button>`}
      </div></div>`)}
    <${More} n=${questions.more} what="questions" onOpen=${() => { done(); openOrders(); }} />
  </section>`;
}

function Problems({ problems }) {
  if (!problems.items.length) return null;
  return html`<section class="gui-lastlook__part">
    <h4 class="ok-dialog__section">Problems</h4>
    <ul class="gui-rows">${problems.items.map((p) => html`<li key=${p.id} class="ok-font-body gui-lastlook__row">
      <span><b>${say(p.title)}</b> · ${say(p.line)}<br /><span class="ok-font-status ok-tone-muted">Waits for: ${say(p.waits)}</span></span>
      <button class="ok-btn" onClick=${() => { done(); openBuilding(p.building, "work"); }}>Open</button></li>`)}</ul>
    ${problems.more > 0 && html`<p class="ok-font-status ok-tone-muted">and ${problems.more} more</p>`}
  </section>`;
}

function Cost({ cost, known }) {
  if (!known) return null;
  return html`<section class="gui-lastlook__part">
    <h4 class="ok-dialog__section">What it cost</h4>
    ${cost.length
      ? html`<ul class="gui-rows">${cost.map((c) => html`<li key=${c.key} class="ok-font-body">${c.line}</li>`)}</ul>`
      : html`<p class="ok-font-body">No window used while you were away.</p>`}
  </section>`;
}

export function LastLook() {
  const t = town.value;
  const g = t && t.last_look;
  useEffect(() => {
    if (!g || !g.empty) return undefined;
    const timer = setTimeout(done, QUIET_S * 1000);
    return () => clearTimeout(timer);
  }, [g && g.since, g && g.empty]);
  if (!g) return null;
  if (g.empty) {
    return html`<div class="gui-lastlook is-quiet" role="status">
      <p class="ok-font-body">${say(g.headline)}</p>
      <button class="ok-btn" onClick=${done}>Back to the camp</button></div>`;
  }
  return html`<div class="gui-lastlook" role="region" aria-label="Since your last look">
    <div class="ok-dialog">
      <div class="ok-dialog__head"><h3 class="ok-dialog__title">Since your last look</h3></div>
      <p class="ok-font-body gui-lastlook__headline">${say(g.headline)}</p>
      <p class="ok-dialog__hint">You were away ${g.away}.</p>
      <div class="gui-lastlook__body">
        <${Built} built=${g.built} />
        <${Questions} questions=${g.questions} />
        <${Problems} problems=${g.problems} />
        <${Cost} cost=${g.cost} known=${g.cost_known} />
        <p class="ok-font-status ok-tone-muted">${say(`Now ${g.working}.`)}</p>
      </div>
      <div class="ok-dialog__actions"><button class="ok-btn primary" onClick=${done}>Back to the camp</button></div>
    </div></div>`;
}
