// Settings → Phones (docs/design/mobile.md §2): the phones paired with this machine, Forget for each
// (at once: its socket closes), and Pair a phone: a QR code the phone scans, which carries the
// listener's address, the certificate's fingerprint the phone pins and a one-time code good for two
// minutes. The host's phones.* commands (gui/phones.py). Closing the settings voids a code not used.
// Places (docs/design/phone-places.md §3, §7): whether Tailscale lets a phone on the road reach the town, and a
// recipe for Shortcuts or Tasker — a token of its own, shown once, with the call that reports a place.
// The app in the phone's browser (gui/pwa.py): with Tailscale here and its certificate, the QR code leads the
// person through it — Tailscale's download while no phone of theirs is in the tailnet, then the app's link,
// which opens Orkcraft in the phone's browser and pairs it at once.
import { useEffect, useRef, useState } from "preact/hooks";
import { html } from "./html.js";
import { command, say } from "./link.js";

const WHAT = "A paired phone sees the town small: each building, the questions the orks wait on, spend and "
  + "quotas. It may answer a question, stop all, drop a text or a file into Drop file here and ask the Warchief. It never builds, "
  + "types into a terminal or changes a setting.";

const when = (iso) => (iso ? iso.replace("T", " ").slice(0, 16) : "");

/** While a code shows: Tailscale's state each few seconds, and what the QR code says now — `{qr, alt, lines}`.
 *  No phone opens the `orkcraft://` link (no app takes it yet: tools/phone.py does), so without Tailscale and its
 *  certificate here the code leads to what is missing, and Pair a phone again looks for the tailnet anew. */
export function useAppStep(offer, left) {
  const [t, setT] = useState(null);
  useEffect(() => {
    if (!offer) { setT(null); return undefined; }
    const read = () => command("phones.tailnet").then(setT, () => {});
    read();
    const timer = setInterval(read, 3000);
    return () => clearInterval(timer);
  }, [offer]);
  if (!offer) return null;
  if (!t) return { qr: null, link: "", alt: "", lines: [say("Looking for Tailscale…")] };
  const again = say("Then Cancel and Pair a phone again: the town looks for Tailscale anew.");
  if (!offer.app_link && !t.running) {
    return { qr: t.install_qr, link: t.install, alt: say("QR code to install Tailscale"), lines: [
      say(t.installed ? "Tailscale is on this computer but not running or not logged in: start it and log in."
        : "The phone reaches the town through Tailscale, and it is not on this computer: install it here (tailscale.com/download) and log in."),
      say("On the phone: scan this code, install Tailscale and log in with the same account."), again] };
  }
  if (!offer.app_link) {
    return { qr: t.dns_qr, link: t.dns, alt: say("QR code to the tailnet's DNS settings"), lines: [
      say("Tailscale runs, but the tailnet gives this computer no HTTPS certificate, and the phone's browser needs one."),
      say("Turn on MagicDNS and HTTPS Certificates in the tailnet's DNS settings (this code opens them; login.tailscale.com/admin/dns)."), again] };
  }
  const phone = t.phones.find((p) => p.online);
  if (!phone) {
    return { qr: t.install_qr, link: t.install, alt: say("QR code to install Tailscale"), lines: [
      say("1. Scan it with the phone's camera and install Tailscale."),
      say(t.account ? `2. Log in to Tailscale on the phone as ${t.account} and turn it on.` : "2. Log in to Tailscale on the phone with this computer's account and turn it on."),
      say("3. When the phone is in the tailnet, this code turns into the link that opens Orkcraft on it."),
      say(`The pairing code is good for ${left} s; show a new one if it runs out.`)] };
  }
  return { qr: offer.app_qr, link: offer.app_link, alt: say("QR code to open Orkcraft on the phone"), lines: [
    say(`${phone.name} (${phone.os}) is in the tailnet. Scan it with the phone's camera: Orkcraft opens in its browser and pairs.`),
    say(phone.os === "iOS" ? "Then Share → Add to Home Screen." : "Then Install app (or Add to Home screen) in the browser's menu."),
    say(`Good for ${left} s, once.`)] };
}

function Offer({ offer, left, onCancel }) {
  const step = useAppStep(offer, left);
  return html`<div class="gui-phones__offer">
    ${step.qr
      ? html`<img class="gui-phones__qr" src=${step.qr} width="240" height="240" alt=${step.alt} />`
      : step.link && html`<div><p class="ok-font-status ok-tone-wait">${say("No QR code: this install lacks segno. Run pip install segno and open the town again — or type this link on the phone:")}</p>
          <code class="gui-phones__link">${step.link}</code></div>`}
    <div class="gui-phones__how">
      ${step.lines.map((line) => html`<span class="ok-font-status">${line}</span>`)}
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

/** Pair a phone from the portrait's menu (docs/design/portrait.md): a code while it is good, the time left and the
 *  phone that paired with it, named once; the menu closing voids a code not used. Settings → Phones keeps the
 *  list, Forget and Places. */
export function usePairing() {
  const [offer, setOffer] = useState(null);
  const [left, setLeft] = useState(0);
  const [paired, setPaired] = useState("");
  const live = useRef(null);
  live.current = offer;
  useEffect(() => () => { if (live.current) command("phones.pair_stop").catch(() => {}); }, []);
  useEffect(() => {
    if (!offer) return undefined;
    const known = new Set(offer.phones.map((d) => d.id));
    const t = setInterval(() => command("phones.list").then((r) => {
      setLeft(Math.round(r.pairing));
      const fresh = r.phones.find((d) => !known.has(d.id));
      if (fresh) setPaired(fresh.name);
      if (!r.pairing || fresh) setOffer(null);
    }, () => {}), 1000);
    return () => clearInterval(t);
  }, [offer]);
  const pair = () => command("phones.pair").then((r) => { setPaired(""); setLeft(Math.round(r.pairing)); setOffer(r); }, () => {});
  const cancel = () => command("phones.pair_stop").then(() => setOffer(null), () => {});
  const step = useAppStep(offer, left);
  return { offer, left, paired, pair, cancel, step };
}

/** The code itself, at the right of the head in the menu's top block (under it when the sheet is too narrow). */
export function PairQr({ pairing: { step } }) {
  if (!step) return null;
  return step.qr
    ? html`<img class="gui-phones__qr gui-you__qr" src=${step.qr} width="128" height="128" alt=${step.alt} />`
    : step.link && html`<div class="gui-you__qr"><p class="ok-font-status ok-tone-wait">${say("No QR code: this install lacks segno. Run pip install segno and open the town again — or type this link on the phone:")}</p>
      <code class="gui-phones__link">${step.link}</code></div>`;
}

/** Under the head's name: Pair a phone, or while a code shows how to scan it, the address, the fingerprint and Cancel. */
export function PairNote({ pairing: { offer, paired, pair, cancel, step } }) {
  if (!offer) {
    return html`<span class="gui-you__pair">
      <button class="ok-btn" title=${say("A QR code to scan with the Orkcraft app. The paired phones and Forget are in Town settings → Phones.")}
        onClick=${pair}>${say("Pair a phone")}</button>
      ${paired && html`<span class="ok-font-status">${say(`Paired: ${paired}`)}</span>`}</span>`;
  }
  return html`<div class="gui-phones__how">
    ${step.lines.map((line) => html`<span class="ok-font-status">${line}</span>`)}
    <span class="ok-font-status ok-tone-muted">${say(`Address: ${offer.address}`)}</span>
    <span class="ok-font-status ok-tone-muted">${say("Certificate (the phone checks it):")}</span>
    <code class="gui-phones__fp">${offer.fingerprint}</code>
    <span><button class="ok-btn" onClick=${cancel}>${say("Cancel")}</button></span>
  </div>`;
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
