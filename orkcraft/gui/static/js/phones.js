// Settings → Phones (docs/design/mobile.md §2): the phones paired with this machine, Forget for each
// (at once: its socket closes), and Pair a phone: a QR code the phone scans, which carries the
// listener's address, the certificate's fingerprint the phone pins and a one-time code good for two
// minutes. The host's phones.* commands (gui/phones.py). Closing the settings voids a code not used.
// Places (docs/design/phone-places.md §3, §7): whether Tailscale lets a phone on the road reach the town, and a
// recipe for Shortcuts or Tasker — a token of its own, shown once, with the call that reports a place.
import { useEffect, useRef, useState } from "preact/hooks";
import { html } from "./html.js";
import { command, say } from "./link.js";
import { Dialog } from "./dialog.js";

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

const TAIL = "Tailscale lets a phone on the road reach this town at home: install it on this machine and on the "
  + "phone, log both in, and turn on HTTPS certificates in the tailnet's DNS settings. Its coordination server "
  + "knows which of your devices exist, not what they say; Funnel is never used.";

function Tailnet({ p }) {
  if (p.tail_address) {
    return html`<span class="ok-font-status ok-tone-muted">${say(`On the road: ${p.tail_address}`)}${p.tail_trusted ? ""
      : say(" (no tailnet certificate: Shortcuts and Tasker need HTTPS certificates on in the tailnet)")}</span>`;
  }
  return html`<span class="ok-font-status ok-tone-muted">${p.tailscale ? say("Tailscale is here but not running or not logged in. ") : ""}${say(TAIL)}
    ${!p.tailscale && html` <a href="https://tailscale.com/download" target="_blank" rel="noopener">tailscale.com/download</a>`}</span>`;
}

function Recipe({ r, onDone }) {
  const body = '{"id": "<a new id each time>", "place": "home", "change": "arrived", "at": "<the date now, ISO 8601>"}';
  return html`<div class="gui-phones__recipe">
    <span class="ok-font-label">${say(`A token for ${r.name}: shown once`)}</span>
    <code class="gui-phones__fp">${r.token}</code>
    <span class="ok-font-status">${say("In iOS Shortcuts: Automation → Arrive (or Leave) → Get contents of URL. In Tasker: a Location profile → HTTP Request.")}</span>
    <dl class="gui-phones__kv">
      <dt>${say("URL")}</dt><dd><code>${r.url || say("(not listening: connect this machine to a network first)")}</code></dd>
      <dt>${say("Method")}</dt><dd><code>POST</code></dd>
      <dt>${say("Headers")}</dt><dd><code>Authorization: Bearer ${r.token}</code><br /><code>Content-Type: application/json</code></dd>
      <dt>${say("Body")}</dt><dd><code>${body}</code></dd>
    </dl>
    ${!r.trusted && html`<span class="ok-font-status ok-tone-wait">${say("This address has no certificate a phone trusts by itself: Shortcuts will refuse it. Turn on Tailscale's HTTPS certificates and open Settings again.")}</span>`}
    <span><button class="ok-btn" onClick=${onDone}>${say("Done")}</button></span>
  </div>`;
}

/** The phone beside the portrait (docs/design/mobile.md §2): its QR code at once, in a dialog of its own. */
export function PhonePair({ onClose }) {
  return html`<${Dialog} title=${say("Pair a phone")} onCancel=${onClose}
      actions=${html`<button class="ok-btn" onClick=${onClose}>${say("Close")}</button>`}>
    <${PhonesField} pairNow=${true} />
  </${Dialog}>`;
}

export function PhonesField({ pairNow = false }) {
  const [p, setP] = useState(null);
  const [recipe, setRecipe] = useState(null);
  const [offer, setOffer] = useState(null);
  const [left, setLeft] = useState(0);
  const live = useRef(null);
  live.current = offer;
  useEffect(() => {
    if (pairNow) command("phones.pair").then((r) => { setP(r); setLeft(Math.round(r.pairing)); setOffer(r); }, () => {});
    else command("phones.list").then(setP, () => {});
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
  const makeRecipe = () => command("phones.recipe", { name: "Shortcuts" }).then((r) => { setP(r); setRecipe(r.recipe); }, () => {});
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
    ${p.listening && !offer && p.address && html`<span class="ok-font-status ok-tone-muted">${say(`Listening for paired phones on ${p.address}`)}</span>`}
    <${Tailnet} p=${p} />
    ${recipe ? html`<${Recipe} r=${recipe} onDone=${() => setRecipe(null)} />`
      : html`<span><button class="ok-btn" onClick=${makeRecipe}
          title=${say("A token for an iOS Shortcuts or Android Tasker automation that reports places")}>${say("Places through Shortcuts or Tasker")}</button></span>`}
  </div>`;
}
