// Orders: the questions the orks wait on, answered by the person (an ork never opens a dialog: its
// building burns until someone opens this). A session's question gets the key typed into it; the
// Warder's and a building's are acknowledged (core/roster.py `Muster.answer`).
import { signal } from "@preact/signals";
import { html, cls } from "./html.js";
import { town, command, say } from "./link.js";
import { Dialog } from "./dialog.js";
import { showSession } from "./tent.js";
import { openBuilding } from "./windows.js";

const ordersOpen = signal(false);
const picked = signal(null);

export function openOrders(id = null) {
  picked.value = id;
  ordersOpen.value = true;
}

export function Orders() {
  if (!ordersOpen.value) return null;
  const alerts = town.value.alerts;
  const close = () => { ordersOpen.value = false; };
  if (!alerts.length) {
    return html`<${Dialog} title="Awaiting an answer" text="Nothing waits for you." onCancel=${close}
      actions=${html`<button class="ok-btn primary" onClick=${close}>Close</button>`} />`;
  }
  const a = alerts.find((x) => x.id === picked.value) || alerts[0];
  const answer = (key) => command("orders.answer", { id: a.id, key }).then(() => {
    if (alerts.length <= 1) close();
  }, () => {});
  return html`<${Dialog} title=${`Awaiting an answer (${alerts.length})`} onCancel=${close}
      actions=${html`
        ${a.source === "terminal" && html`<button class="ok-btn" onClick=${() => { close(); showSession(a.ref); }}>Open its terminal</button>`}
        ${a.source === "view" && a.ref && html`<button class="ok-btn" onClick=${() => { close(); openBuilding(a.ref, "work"); }}>${say("Open it")}</button>`}
        ${a.advice && html`<button class="ok-btn primary" onClick=${() => command("orders.follow", { id: a.id }).then(() => {
          if (alerts.length <= 1) close();
        }, () => {})}>${say("Follow the Elders")}</button>`}
        <button class="ok-btn gui-orders__later" onClick=${close}>Later</button>`}>
    ${alerts.length > 1 && html`<ul class="ok-list__items gui-orders__list">${alerts.map((x) => html`<li key=${x.id}
        class=${cls("ok-item", { "is-selected": x.id === a.id, "is-alert": x.waited >= 30 })}
        onClick=${() => { picked.value = x.id; }}>${x.who || "Alert"}<span class="meta" title=${x.title}>${x.title}</span></li>`)}</ul>`}
    <p class="ok-dialog__text"><b>${a.who ? `${a.who}: ` : ""}</b>${a.title}</p>
    ${a.context.length > 0 && html`<pre class="gui-pre gui-orders__context">${a.context.join("\n")}</pre>`}
    ${a.advice && html`<p class="ok-dialog__hint gui-orders__advice">
      <b>${say("The Elders")} advise ${a.advice.key}. ${(a.options.find(([k]) => k === a.advice.key) || ["", ""])[1]}</b>
      ${a.advice.why && ` — ${a.advice.why}`}
      ${a.advice.warn && html`<br /><span class="ok-tone-wait">⚠ ${a.advice.warn}</span>`}</p>`}
    <div class="gui-orders__options">
      ${a.options.map(([key, label]) => html`<button key=${key}
          class=${a.advice && a.advice.key === key ? "ok-btn is-focus" : "ok-btn"} onClick=${() => answer(key)}>
        <span class="ok-kbd">${key}</span> ${label}</button>`)}
    </div>
  </${Dialog}>`;
}
