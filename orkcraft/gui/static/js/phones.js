// Settings → Phones (docs/design/mobile.md §2): the phones paired with this machine, Forget for each
// (at once: its socket closes), and Pair a phone: a QR code the phone scans, which carries the
// listener's address, the certificate's fingerprint the phone pins and a one-time code good for two
// minutes. The host's phones.* commands (gui/phones.py). Closing the settings voids a code not used.
import { useEffect, useRef, useState } from "preact/hooks";
import { html } from "./html.js";
import { command, say } from "./link.js";

const WHAT = "A paired phone sees the town small: each building, the questions the orks wait on, spend and "
  + "quotas. It may answer a question, stop all, drop a text or a file into Drop file here and ask the Warchief. It never builds, "
  + "types into a terminal or changes a setting.";

const when = (iso) => (iso ? iso.replace("T", " ").slice(0, 16) : "");

function Offer({ offer, left, onCancel }) {
  return html`<div class="gui-phones__offer">
    ${offer.qr
      ? html`<img class="gui-phones__qr" src=${offer.qr} width="240" height="240" alt=${say("QR code to pair a phone")} />`
      : html`<code class="gui-phones__link">${offer.link}</code>`}
    <div class="gui-phones__how">
      <span class="ok-font-status">${say(`Scan it with the Orkcraft app on the phone. Good for ${left} s, once.`)}</span>
      <span class="ok-font-status ok-tone-muted">${say(`Address: ${offer.address}`)}</span>
      <span class="ok-font-status ok-tone-muted">${say("Certificate (the phone checks it):")}</span>
      <code class="gui-phones__fp">${offer.fingerprint}</code>
      <span><button class="ok-btn" onClick=${onCancel}>${say("Cancel")}</button></span>
    </div>
  </div>`;
}

export function PhonesField() {
  const [p, setP] = useState(null);
  const [offer, setOffer] = useState(null);
  const [left, setLeft] = useState(0);
  const live = useRef(null);
  live.current = offer;
  useEffect(() => {
    command("phones.list").then(setP, () => {});
    return () => { if (live.current) command("phones.pair_stop").catch(() => {}); };
  }, []);
  // While a code shows: the list again each second (a phone that paired appears), and the time left.
  useEffect(() => {
    if (!offer) return undefined;
    const t = setInterval(() => command("phones.list").then((r) => {
      setP(r);
      setLeft(Math.round(r.pairing));
      if (!r.pairing) setOffer(null);
    }, () => {}), 1000);
    return () => clearInterval(t);
  }, [offer]);
  if (!p) return null;
  const pair = () => command("phones.pair").then((r) => { setP(r); setLeft(Math.round(r.pairing)); setOffer(r); }, () => {});
  const cancel = () => command("phones.pair_stop").then((r) => { setP(r); setOffer(null); }, () => {});
  const forget = (id) => command("phones.forget", { id }).then(setP, () => {});
  const open = new Set(p.open || []);
  return html`<div class="gui-field gui-phones"><span class="ok-font-label">${say("Phones")}</span>
    <p class="ok-font-status ok-tone-muted">${say(WHAT)}</p>
    ${p.phones.length > 0 && html`<ul class="gui-phones__list">
      ${p.phones.map((d) => html`<li key=${d.id} class="gui-phones__one">
        <span class="gui-phones__name">${d.name}</span>
        <span class="ok-font-status ok-tone-muted">${open.has(d.id) ? say("connected now") : say(`last seen ${when(d.seen)}`)}</span>
        <button class="ok-btn" onClick=${() => forget(d.id)} title=${say("Its token stops working at once")}>${say("Forget")}</button>
      </li>`)}
    </ul>`}
    ${offer
      ? html`<${Offer} offer=${offer} left=${left} onCancel=${cancel} />`
      : html`<span><button class="ok-btn" onClick=${pair}>${say("Pair a phone")}</button></span>`}
    ${p.listening && !offer && html`<span class="ok-font-status ok-tone-muted">${say(`Listening for paired phones on ${p.address}`)}</span>`}
  </div>`;
}
