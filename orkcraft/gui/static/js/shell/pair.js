// Pair a phone, from the shell (docs/specs/34-v1-round-2.md §6): the existing pairing (`phones.pair`, `phones.pair_stop`,
// `PairQr` of js/phones.js) inside the modal — the QR, the time the code has left, in plain words how the phone will reach
// this computer, and the paired phones with Forget. Closing the dialog voids a code not used.
import { useEffect, useState } from "preact/hooks";
import { html, linked } from "../html.js";
import { command, say } from "../link.js";
import { usePairing, PairQr } from "../phones.js";
import { Modal, closeDialog, openDialog } from "./modals.js";

const when = (iso) => (iso ? iso.replace("T", " ").slice(0, 16) : "");
const hostOf = (url) => { try { return new URL(url).hostname; } catch { return String(url || "").replace(/^https?:\/\//, "").split(/[:/]/)[0]; } };

export function PairDialog() {
  const pairing = usePairing();
  const { offer, left, paired, pair, cancel, step } = pairing;
  const [info, setInfo] = useState(null);          // phones.list: the paired phones, the addresses
  const read = () => command("phones.list").then(setInfo, () => {});
  useEffect(() => { pair(); read(); }, []);
  useEffect(() => { if (paired) read(); }, [paired]);
  const forget = (id) => command("phones.forget", { id }).then(setInfo, () => {});
  const tail = offer?.tail_address || info?.tail_address, wifi = offer?.address || info?.address;
  return html`<${Modal} title="Pair a phone" onClose=${closeDialog} wide=${true}
    foot=${html`<button type="button" class="ok-btn" onClick=${() => openDialog("settings")}>← Settings</button>
      <button type="button" class="ok-btn primary" onClick=${closeDialog}>Done</button>`}>
    <div class="shell-pair">
      <div class="shell-pair__code" aria-live="polite">
        ${offer ? html`<${PairQr} pairing=${pairing} /><span class="ok-font-status shell-pair__left">The code is good for ${left} s, once.</span>
            <button type="button" class="ok-btn" onClick=${cancel}>Cancel the code</button>`
          : html`<p class="ok-font-status">${paired ? say(`Paired: ${paired}.`) : "No code is showing."}</p>
            <button type="button" class="ok-btn primary" onClick=${pair}>${paired ? "Pair another phone" : "Show a code"}</button>`}
      </div>
      <div class="shell-pair__how">
        ${step?.lines?.length > 0 && offer && html`<ol class="shell-pair__steps">${step.lines.map((l, n) => html`<li key=${n} class="ok-font-status">${linked(l)}</li>`)}</ol>`}
        <h3 class="ok-font-label">How the phone reaches this computer</h3>
        <ul class="shell-pair__reach">
          <li>On this Wi-Fi${wifi ? html`: <code>${wifi}</code>` : ""}.</li>
          ${tail ? html`<li>Anywhere on your tailnet: <code>${hostOf(tail)}</code>.</li>`
            : html`<li>Away from home? Install Tailscale on this computer and the phone.</li>`}
        </ul>
      </div>
      <div class="shell-pair__phones"><h3 class="ok-font-label">Paired phones</h3>
        ${info?.phones?.length ? html`<ul class="gui-phones__list">${info.phones.map((d) => html`<li key=${d.id} class="gui-phones__one">
          <span class="gui-phones__name">${d.name}</span>
          <span class="ok-font-status ok-tone-muted">${(info.open || []).includes(d.id) ? "connected now" : `last seen ${when(d.seen)}`}</span>
          <button type="button" class="ok-btn" title="Its token stops working at once" onClick=${() => forget(d.id)}>Forget</button></li>`)}</ul>`
          : html`<p class="ok-font-status ok-tone-muted">No phone is paired yet.</p>`}
      </div>
    </div>
  <//>`;
}
