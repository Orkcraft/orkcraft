// The task's history, the minimal waybill (docs/design/cart-waybill.md §2, decisions-2026-10.md §13.1): a click on a
// cart, or on an ork's thought bubble, opens where the task stopped, the tokens it spent and the time it took, stop by
// stop (gui/waybill.py reads them from the cart's own trail). A number nobody recorded says so; none is guessed.
import { signal } from "@preact/signals";
import { useEffect, useState } from "preact/hooks";
import { html } from "../html.js";
import { command, say, town } from "../link.js";

export const waybillOf = signal(null);     // {cart} | {building} | {building, task}: whose history is open

export const tokensWord = (n) => (n === null || n === undefined ? null
  : n >= 10000 ? `${Math.round(n / 1000)}k` : n >= 1000 ? `${(n / 1000).toFixed(1)}k` : String(n));
export const moneyWord = (v) => (v === null || v === undefined ? null : `$${Number(v).toFixed(2)}`);
const timeWord = (ms) => (ms === null || ms === undefined ? null
  : ms < 60000 ? `${Math.max(1, Math.round(ms / 1000))} s` : `${Math.round(ms / 60000)} min`);
const NOT = () => html`<span class="ok-tone-muted">${say("not recorded")}</span>`;
const or = (v) => v || NOT();

/** A waybill asked of the host (`cart.waybill`) and asked again when the town changes: undefined while it comes, null
 *  when there is none. */
export function useWaybill(of) {
  const [d, setD] = useState(undefined);
  const snap = town.value;
  useEffect(() => { setD(undefined); }, [JSON.stringify(of)]);
  useEffect(() => {
    if (!of) return undefined;
    let live = true;
    command("cart.waybill", of).then((x) => { if (live) setD(x || null); }, () => { if (live) setD(null); });
    return () => { live = false; };
  }, [JSON.stringify(of), snap]);
  return d;
}

/** Its stops, the ork at each, the tokens, the spend and the time there; where it is now; the sum. */
export function WaybillBody({ d }) {
  if (d === undefined) return html`<p class="ok-tone-muted">${say("Opening…")}</p>`;
  if (d === null) return html`<p class="ok-tone-muted">${say("No cart of it is on the roads now.")}</p>`;
  return html`
    ${d.source_title && html`<p class="ok-tone-muted">${say(`From ${d.source_title}`)}</p>`}
    <table class="gui-camp__waybill-stops">
      <thead><tr><th>${say("Stop")}</th><th>${say("Ork")}</th><th>${say("Tokens")}</th><th>${say("Spend")}</th><th>${say("Time")}</th></tr></thead>
      <tbody>
        ${d.stops.map((s, i) => html`<tr key=${i}><td>${say(s.title)}${s.at ? html` <span class="ok-tone-muted">${s.at}</span>` : ""}
          ${s.outcome ? html` <span class="ok-tone-muted">· ${say(s.outcome)}</span>` : ""}</td>
          <td>${s.ork ? say(s.ork) : "—"}</td><td>${or(tokensWord(s.tokens))}</td><td>${or(moneyWord(s.cost))}</td><td>${or(timeWord(s.ms))}</td></tr>`)}
        <tr class="is-now"><td colspan="5">▸ ${say(`Now: ${d.now.title}`)} <span class="ok-tone-muted">· ${say(d.now.status)}</span></td></tr>
      </tbody>
    </table>
    <p class="gui-camp__waybill-sum">${say("In all")}: ${or(tokensWord(d.tokens))} ${say("tokens")} · ${or(moneyWord(d.cost))} · ${or(timeWord(d.ms))}</p>`;
}

export function Waybill() {
  const of = waybillOf.value;
  const d = useWaybill(of);
  useEffect(() => {
    if (!of) return undefined;
    const key = (e) => { if (e.key === "Escape") { e.stopImmediatePropagation(); waybillOf.value = null; } };
    window.addEventListener("keydown", key, true);
    return () => window.removeEventListener("keydown", key, true);
  }, [!!of]);
  if (!of) return null;
  const close = () => { waybillOf.value = null; };
  return html`<section class="gui-camp__waybill" role="dialog" aria-label=${say("The task's history")} onPointerDown=${(e) => e.stopPropagation()}
      onClick=${(e) => e.stopPropagation()}>
    <header class="gui-camp__waybill-head">
      <b>${d ? `${d.ref ? `${d.ref} · ` : ""}${d.title || say("A cart")}` : say("The task's history")}</b>
      <button type="button" class="gui-toolerr__close" title=${say("Close")} aria-label=${say("Close")} onClick=${close}>×</button>
    </header>
    <${WaybillBody} d=${d} />
  </section>`;
}
