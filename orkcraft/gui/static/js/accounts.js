// Settings → Accounts (gui/accounts.py, docs/design/google-account.md): a personal Google account, signed in once,
// heard by External listeners (Gmail), shown by the Calendar (and New event adds there) and read by the Wiki (Drive).
// The wizard walks the person through their own client in Google Cloud, five steps with a link to each page of the
// console; the sign-in comes back to this machine and is kept as a login here, never in the project. The
// onboarding's last card opens the same wizard (js/onboarding.js).
import { signal } from "@preact/signals";
import { useEffect, useState } from "preact/hooks";
import { html, cls } from "./html.js";
import { command, say, town } from "./link.js";
import { Dialog } from "./dialog.js";

export const googleOpen = signal(false);
/** Whether Connect Google is offered: put away for now (its wizard is long), unless ORKCRAFT_GOOGLE=1 (gui/state.py).
 *  An account already connected still shows in Settings → Accounts, with Disconnect. */
export const googleShown = () => !!(town.value && town.value.google);

const PARTS = [["gmail", "Gmail", "External listeners hear new mail"],
  ["calendar", "Calendar", "the Calendar shows your week and adds events"],
  ["drive", "Drive", "the Wiki reads your Docs and text files"]];
const NAME = Object.fromEntries(PARTS.map(([id, name]) => [id, name]));
const BUILDING = { gmail: "External listeners", calendar: "Calendar", drive: "Wiki" };

const SAFETY = "Read-only for mail and Drive: nothing is sent, deleted or marked read. The calendar may add events "
  + "you ask for. Mail, events and documents that orks work on go to the AI tool that runs them, as any other text does. "
  + "The sign-in is kept on this machine (the keychain, when there is one), never in the project.";

function Link({ href, children }) {
  return html`<a class="ok-btn" href=${href} target="_blank" rel="noopener">${children} ↗</a>`;
}

function Step({ n, title, done, children }) {
  return html`<li class=${cls("gui-acc__step", { "is-done": done })}>
    <span class="gui-acc__n" aria-hidden="true">${done ? "✓" : n}</span>
    <div class="gui-acc__body"><span class="ok-font-label">${title}</span>${children}</div>
  </li>`;
}

function ClientForm({ a, setA }) {
  const [f, setF] = useState({ id: "", secret: "" });
  const save = () => command("google.client", f).then(setA, () => {});
  return html`<div class="gui-form">
    <label class="gui-field"><span class="ok-font-label">Client ID (or paste the whole JSON file)</span>
      <input class="ok-input" value=${f.id} placeholder="1234-abc.apps.googleusercontent.com"
        onInput=${(e) => setF({ ...f, id: e.target.value })} /></label>
    ${!f.id.trim().startsWith("{") && html`<label class="gui-field"><span class="ok-font-label">Client secret</span>
      <input class="ok-input" type="password" value=${f.secret} placeholder="GOCSPX-…" autocomplete="off"
        onInput=${(e) => setF({ ...f, secret: e.target.value })} /></label>`}
    <span><button class="ok-btn primary" disabled=${!f.id.trim()} onClick=${save}>Save the client</button></span>
  </div>`;
}

function SignIn({ a, setA }) {
  const [parts, setParts] = useState(["gmail", "calendar", "drive"]);
  const c = a.consent;
  const flip = (id) => setParts(parts.includes(id) ? parts.filter((x) => x !== id) : [...parts, id]);
  const go = () => command("google.connect", { parts }).then((r) => {
    setA(r);
    if (r.consent) window.open(r.consent.url, "_blank", "noopener");
  }, () => {});
  if (c && c.state === "waiting") {
    return html`<div class="gui-form">
      <p class="ok-font-body">${say("Waiting for Google… Finish the sign-in in the browser tab that opened.")}</p>
      <p class="ok-font-status ok-tone-muted">${say("Google will say it hasn't verified this app: it is your own client. Click Advanced, then Go to … (unsafe), and leave Gmail, Calendar and Drive ticked.")}</p>
      <span><a class="ok-btn" href=${c.url} target="_blank" rel="noopener">${say("Open the sign-in again")} ↗</a>
        <button class="ok-btn" onClick=${() => command("google.cancel").then(setA, () => {})}>Cancel</button></span>
    </div>`;
  }
  return html`<div class="gui-form">
    ${PARTS.map(([id, name, what]) => html`<label key=${id} class="ok-check">
      <input type="checkbox" class="gui-onb__hide" checked=${parts.includes(id)} onChange=${() => flip(id)} />
      <i>${parts.includes(id) ? "✓" : ""}</i><span><b>${name}</b>: ${say(what)}</span></label>`)}
    <p class="ok-font-status ok-tone-muted">${say("Google will say it hasn't verified this app: it is your own client. Click Advanced, then Go to … (unsafe).")}</p>
    ${c && c.state === "failed" && html`<p class="ok-font-status ok-tone-error">${c.error}</p>`}
    <span><button class="ok-btn primary" disabled=${!parts.length} onClick=${go}>Sign in with Google</button></span>
  </div>`;
}

/** After the sign-in: which buildings use the account; a building that is not in the town is set up. */
function UseIt({ a, setA, account, onDone }) {
  const [parts, setParts] = useState(account.parts);
  const flip = (id) => setParts(parts.includes(id) ? parts.filter((x) => x !== id) : [...parts, id]);
  const use = () => command("google.use", { email: account.email, parts }).then((r) => { setA(r); onDone(); }, () => {});
  const missing = (a.consent && a.consent.account && a.consent.account.missing) || [];
  return html`<div class="gui-form">
    <p class="ok-font-body">${say(`Connected: ${account.email}.`)}</p>
    ${missing.length > 0 && html`<p class="ok-font-status ok-tone-wait">${say(`Google did not allow ${missing.map((p) => NAME[p]).join(", ")}. ${a.fallback}`)}</p>`}
    <span class="ok-font-label">Use it in the town</span>
    ${account.parts.map((id) => html`<label key=${id} class="ok-check">
      <input type="checkbox" class="gui-onb__hide" checked=${parts.includes(id)} onChange=${() => flip(id)} />
      <i>${parts.includes(id) ? "✓" : ""}</i>
      <span><b>${NAME[id]}</b> → ${say(BUILDING[id])}${a.standing[id] ? "" : say(" (set up now: not in the town yet)")}</span></label>`)}
    <span><button class="ok-btn primary" disabled=${!parts.length} onClick=${use}>Use it</button></span>
  </div>`;
}

/** The five steps, from making the client in Google Cloud to the buildings that use the account. */
export function GoogleWizard() {
  const [a, setA] = useState(null);
  const open = googleOpen.value;
  useEffect(() => { if (open) command("accounts.list").then(setA, () => {}); }, [open]);
  const waiting = a && a.consent && a.consent.state === "waiting";
  useEffect(() => {
    if (!open || !waiting) return undefined;
    const t = setInterval(() => command("accounts.list").then(setA, () => {}), 1500);
    return () => clearInterval(t);
  }, [open, waiting]);
  if (!open || !a) return null;
  const close = () => { googleOpen.value = false; };
  const got = a.consent && a.consent.state === "done" ? a.consent.account : null;
  const account = got && a.accounts.find((x) => x.email === got.email);
  const L = a.links;
  return html`<${Dialog} title=${say("Connect Google")} wide=${true} onCancel=${close}
      meta=${say("For your own Google account: about 6 minutes, once. You make a small client of your own in Google Cloud; Orkcraft has no server and sees nothing on the way.")}
      actions=${html`<button class="ok-btn" onClick=${close}>${account ? "Later" : "Close"}</button>`}>
    <ol class="gui-acc__steps">
      <${Step} n="1" title=${say("Make a project in Google Cloud")} done=${!!a.client}>
        <span class="ok-font-status ok-tone-muted">${say("Any name, e.g. Orkcraft. Free: no billing is needed.")}</span>
        ${!a.client && html`<span><${Link} href=${L.project}>Create a project</${Link}></span>`}
      </${Step}>
      <${Step} n="2" title=${say("Turn on the Gmail, Calendar and Drive APIs")} done=${!!a.client}>
        <span class="ok-font-status ok-tone-muted">${say("Pick the project at the top of the page, then Enable.")}</span>
        ${!a.client && html`<span><${Link} href=${L.apis}>Turn on the APIs</${Link}></span>`}
      </${Step}>
      <${Step} n="3" title=${say("Name the app and publish it")} done=${!!a.client}>
        ${!a.client && html`<span class="ok-font-status ok-tone-muted">${say("Branding: an app name (e.g. Orkcraft, mine) and your e-mail. Then Audience: External, and Publish app. Not Testing: in Testing, Google ends the sign-in after 7 days.")}</span>
          <span><${Link} href=${L.branding}>Branding</${Link}> <${Link} href=${L.audience}>Audience: publish</${Link}></span>`}
      </${Step}>
      <${Step} n="4" title=${say("Make a Desktop client and paste it here")} done=${!!a.client}>
        ${a.client ? html`<span class="ok-font-status ok-tone-muted">${say(`Client ${a.client.id.split("-")[0]}… is saved on this machine.`)}</span>`
          : html`<span class="ok-font-status ok-tone-muted">${say("Clients → Create client → Application type: Desktop app → Create. Copy its Client ID and Client secret, or download the JSON.")}</span>
            <span><${Link} href=${L.client}>Create the client</${Link}></span>
            <${ClientForm} a=${a} setA=${setA} />`}
      </${Step}>
      <${Step} n="5" title=${say("Sign in")} done=${!!account}>
        ${a.client && (account ? html`<${UseIt} a=${a} setA=${setA} account=${account} onDone=${close} />`
          : html`<${SignIn} a=${a} setA=${setA} />`)}
      </${Step}>
    </ol>
    <p class="ok-font-status ok-tone-muted">${say(SAFETY)}</p>
    <p class="ok-font-status ok-tone-muted">${say(`If Google refuses the sign-in. ${a.fallback}`)}</p>
  </${Dialog}>`;
}

function Folder({ account, use, setA }) {
  const [list, setList] = useState(null);
  const pick = (folder) => command("google.folder", { email: account.email, building: use.id, folder })
    .then((r) => { setA(r); setList(null); }, () => {});
  return html`<span class="gui-acc__folder">
    <span class="ok-font-status">${say(`${use.title} reads ${use.folder ? "one folder of Drive" : "the whole Drive"}.`)}</span>
    ${list === null
      ? html`<button class="ok-btn" onClick=${() => command("google.folders", { email: account.email }).then(setList, () => {})}>${say("Choose a folder")}</button>
        ${use.folder && html`<button class="ok-btn" onClick=${() => pick("")}>${say("The whole Drive")}</button>`}`
      : html`<select class="ok-input" aria-label=${say("A folder of My Drive")} onChange=${(e) => pick(e.target.value)}>
          <option value="">${say("The whole Drive")}</option>
          ${list.map((f) => html`<option key=${f.id} value=${f.id} selected=${f.id === use.folder}>${f.name}</option>`)}
        </select>`}
  </span>`;
}

function Account({ x, setA }) {
  const [asking, setAsking] = useState(false);
  const [detach, setDetach] = useState(false);
  const unused = x.parts.filter((p) => !x.uses.some((u) => u.part === p));
  const off = () => command("google.disconnect", { email: x.email, detach }).then((r) => { setA(r); setAsking(false); }, () => {});
  return html`<li class="gui-phones__one">
    <span class="gui-phones__name">${x.email}</span>
    <span class="ok-font-status ok-tone-muted">${x.parts.map((p) => NAME[p]).join(" · ")}</span>
    <span class="ok-font-status">${x.uses.length ? say(`Used by ${x.uses.map((u) => `${u.title} (${NAME[u.part]})`).join(", ")}`) : say("Not used by any building")}</span>
    ${x.uses.filter((u) => u.part === "drive").map((u) => html`<${Folder} key=${u.id} account=${x} use=${u} setA=${setA} />`)}
    ${unused.length > 0 && html`<button class="ok-btn" onClick=${() => command("google.use", { email: x.email, parts: unused }).then(setA, () => {})}>
      ${say(`Use ${unused.map((p) => NAME[p]).join(", ")} in the town`)}</button>`}
    <button class="ok-btn" onClick=${() => setAsking(true)}>Disconnect</button>
    ${asking && html`<${Dialog} title=${say(`Disconnect ${x.email}?`)} warn=${true} onCancel=${() => setAsking(false)}
        text=${say("Google takes back Orkcraft's access to this account, and the sign-in is deleted from this machine. Buildings that used it say Sign in again until you connect it again.")}
        actions=${html`<button class="ok-btn" onClick=${() => setAsking(false)}>Cancel</button>
          <button class="ok-btn primary" onClick=${off}>Disconnect</button>`}>
      <label class="ok-check"><input type="checkbox" class="gui-onb__hide" checked=${detach} onChange=${() => setDetach(!detach)} />
        <i>${detach ? "✓" : ""}</i><span>${say("Also take it out of the buildings")}</span></label>
    </${Dialog}>`}
  </li>`;
}

/** Settings → Accounts: each Google account, what uses it, its Drive folder, Disconnect; Connect Google. */
export function AccountsField() {
  const [a, setA] = useState(null);
  useEffect(() => { command("accounts.list").then(setA, () => {}); }, [googleOpen.value]);
  if (!a || (!googleShown() && !a.accounts.length)) return null;
  return html`<div class="gui-field"><span class="ok-font-label">${say("Accounts")}</span>
    ${a.accounts.length > 0 && html`<ul class="gui-phones__list">${a.accounts.map((x) => html`<${Account} key=${x.email} x=${x} setA=${setA} />`)}</ul>`}
    <p class="ok-font-status ok-tone-muted">${say(a.accounts.length ? SAFETY
      : "Your own Google account: Gmail for External listeners, your calendar for the Calendar, Drive for the Wiki. One sign-in, about 6 minutes.")}</p>
    ${googleShown() && html`<span><button class="ok-btn" onClick=${() => { googleOpen.value = true; }}>${say(a.accounts.length ? "Connect another Google account" : "Connect Google")}</button>
      ${a.client && !a.accounts.length && html` <button class="ok-btn" onClick=${() => command("google.forget_client").then(setA, () => {})}>${say("Forget the Google Cloud client")}</button>`}</span>`}
  </div>`;
}
