// The town in a phone's browser (gui/pwa.py; docs/design/mobile.md §8.1, §10, a prototype). No framework and
// no build: the phone listener serves these files as they are (this one, util.js, dock.js). It speaks the
// phone's protocol (gui/phones.py): the compact snapshot (`state`), a command and its `reply`, and `news` while
// the app is open. It may do what a phone may (gui/mobile.py COMMANDS): answer a question, follow the Advisor,
// Stop all, ask the Warchief and drop a text, a link or a file into Drop file here. Nothing else, whatever
// this page sends: the listener refuses the rest.

import { h, store, minutes, guessName } from "./util.js";
import { makeDock } from "./dock.js";

const PROTOCOL = "orkcraft.v1";
const API = 1;
const IOS = "standalone" in navigator;  // only iOS Safari has navigator.standalone
const STANDALONE = matchMedia("(display-mode: standalone)").matches || navigator.standalone === true;
const LIGHT = matchMedia("(prefers-color-scheme: light)");

const app = document.getElementById("app");
const show = (...kids) => app.replaceChildren(...kids);

// -- what the address brings: a pairing code, a token for an iOS Home Screen app, a share ---------------

const hash = new URLSearchParams(location.hash.slice(1));
const query = new URLSearchParams(location.search);
const shared = [query.get("share_title"), query.get("share_text"), query.get("share_url")].filter(Boolean).join("\n");
let device = store.get();
if (hash.get("k") && !device) {                  // an iOS Home Screen app's first start (gui/pwa.py manifest)
  device = { id: "", token: hash.get("k"), name: guessName() };
  store.set(device);
}
const code = hash.get("pair");
// Nothing of it stays in the address: a code is once, a token is this phone's own, a share is used now.
if (location.hash || location.search) history.replaceState(null, "", location.pathname);

if ("serviceWorker" in navigator) navigator.serviceWorker.register("sw.js").catch(() => {});

// -- pairing ----------------------------------------------------------------------------------------

function unpaired(note = "") {
  show(h("section", { class: "card" },
    h("h1", {}, "Orkcraft"),
    note && h("p", { class: "warn" }, note),
    h("p", {}, "This phone is not paired with a town yet."),
    h("p", { class: "muted" }, "On the computer: Town settings → Phones → Pair a phone, then scan the second QR code, "
      + "“Open in the phone’s browser”, with this phone’s camera. Both need Tailscale, logged in, with HTTPS certificates on.")));
}

// Opened from the desktop's QR code: it pairs at once, by the phone's kind as its name (renamed nowhere yet).
function pairing(pairCode) {
  const msg = h("p", { class: "muted" }, "Pairing…");
  const again = h("button", { class: "btn", hidden: true, onclick: () => pair(pairCode, guessName(), msg, again) }, "Try again");
  show(h("section", { class: "card" },
    h("h1", {}, "Pairing this phone"),
    h("p", {}, "It will see the town small: each building, the questions the orks wait on, spend and quotas. "
      + "It may answer a question, stop all, ask the Warchief and drop a text or a file. It never builds or types into a terminal."),
    msg, again));
  pair(pairCode, guessName(), msg, again);
}

async function pair(pairCode, name, msg, button) {
  button.hidden = true;
  msg.textContent = "Pairing…";
  msg.className = "muted";
  try {
    const v = await fetch("/api/version", { headers: { Authorization: `Bearer ${pairCode}` } });
    if (!v.ok) throw new Error("The code was not taken: show a new one on the computer and scan it again.");
    const version = await v.json();
    if (version.api !== API) throw new Error(`This app speaks api ${API}, the town ${version.api}: update Orkcraft.`);
    const r = await fetch("/api/pair", { method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ code: pairCode, name }) });
    const body = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(body.error || `Not paired (${r.status})`);
    device = { id: body.id, token: body.token, name: body.name };
    store.set(device);
    if (IOS && !STANDALONE) homeScreen();
    else connect();
  } catch (e) {
    msg.textContent = e.message || String(e);
    msg.className = "warn";
    button.hidden = false;
  }
}

// iOS keeps a Home Screen app's storage apart from Safari's: the app the person adds opens with the token
// in its start_url once (gui/pwa.py `manifest`), and keeps it from then on.
function handOff() {
  if (!IOS || STANDALONE || !device?.token) return;
  document.getElementById("manifest").href = `manifest.webmanifest?k=${encodeURIComponent(device.token)}`;
  history.replaceState(null, "", `${location.pathname}#k=${encodeURIComponent(device.token)}`);
}

function homeScreen() {
  handOff();
  show(h("section", { class: "card" },
    h("h1", {}, `Paired: ${device.name}`),
    h("p", {}, "Now add it to the Home Screen: Share → Add to Home Screen, then open Orkcraft from there."),
    h("p", { class: "muted" }, "Until then this page’s address holds the phone’s key: do not share it."),
    h("button", { class: "btn", onclick: () => connect() }, "Use it in Safari for now")));
}

// -- add to the Home Screen ----------------------------------------------------------------------------
// Android's browsers offer their own install prompt (`beforeinstallprompt`): the banner's Add opens it. iOS has
// none: the banner says where Safari keeps it, and the page hands the token over (`handOff`) whenever it shows.

const HIDE = "orkcraft.install.hidden";      // when Not now was said: the banner waits HIDE_DAYS
const HIDE_DAYS = 14;
let installEvent = null;

window.addEventListener("beforeinstallprompt", (e) => { e.preventDefault(); installEvent = e; banner(); });
window.addEventListener("appinstalled", () => { installEvent = null; notNow(); });

function hiddenNow() {
  try { return Date.now() - Number(localStorage.getItem(HIDE) || 0) < HIDE_DAYS * 86400e3; } catch { return false; }
}

function notNow() {
  try { localStorage.setItem(HIDE, String(Date.now())); } catch { /* shown again next time */ }
  banner();
}

function banner() {
  if (!ui) return;
  const later = h("button", { class: "btn quiet", onclick: notNow }, "Not now");
  let card = null;
  if (STANDALONE || hiddenNow()) card = null;
  else if (installEvent) {
    const add = h("button", { class: "btn primary", onclick: async () => {
      const e = installEvent;
      installEvent = null;
      await e.prompt();
      await e.userChoice.catch(() => null);
      banner();                                  // the browser offers it again itself, when it may
    } }, "Add");
    card = h("section", { class: "card install" },
      h("p", {}, "Add Orkcraft to the Home screen: it opens like an app, without the browser’s bar."),
      h("div", { class: "row" }, add, later));
  } else if (IOS) {
    handOff();
    card = h("section", { class: "card install" },
      h("p", {}, "Add Orkcraft to the Home Screen: tap Share (the square with an arrow up; under ⋯ on newer iOS), "
        + "then Add to Home Screen."),
      h("p", { class: "muted" }, "Until it is added, this page’s address holds the phone’s key: do not share it."),
      h("div", { class: "row" }, later));
  }
  ui.install.replaceChildren(...(card ? [card] : []));
}

// -- the socket ---------------------------------------------------------------------------------------

let ws = null;
let opened = false;
let retry = 1;
let retryTimer = 0;
let nextId = 1;
const waiting = new Map();
let town = null;
let ui = null;

function connect() {
  clearTimeout(retryTimer);
  if (!device?.token) { unpaired(); return; }
  if (ws && ws.readyState <= 1) return;
  ui = ui || layout();
  banner();
  status("Connecting…");
  opened = false;
  ws = new WebSocket(`wss://${location.host}/ws`, [PROTOCOL, `bearer.${device.token}`]);
  ws.onopen = () => { opened = true; retry = 1; status(""); hello(); };
  ws.onmessage = (e) => {
    let msg;
    try { msg = JSON.parse(e.data); } catch { return; }
    if (msg.t === "state") render(msg.state);
    else if (msg.t === "reply") { const w = waiting.get(msg.id); waiting.delete(msg.id); w?.(msg); }
    else if (msg.t === "news") news(msg.news || []);
  };
  ws.onclose = (e) => {
    for (const w of waiting.values()) w({ ok: false, error: "The town went away" });
    waiting.clear();
    if (e.code === 1008) {                       // forgotten on the computer: the token is dead
      store.clear();
      device = null;
      ui = null;
      unpaired("The town forgot this phone. Pair it again to use it.");
      return;
    }
    status(opened ? "The town went away: trying again…" : "Cannot reach the town: is it running, and Tailscale on?");
    retryTimer = setTimeout(connect, retry * 1000);
    retry = Math.min(retry * 2, 30);
  };
}

function send(name, args = {}) {
  return new Promise((resolve) => {
    if (!ws || ws.readyState !== 1) { resolve({ ok: false, error: "Not connected to the town" }); return; }
    const id = nextId++;
    waiting.set(id, resolve);
    ws.send(JSON.stringify({ t: "cmd", id, name, args }));
  });
}

document.addEventListener("visibilitychange", () => {
  if (document.visibilityState === "visible" && device?.token && (!ws || ws.readyState > 1)) connect();
});

// -- the town -----------------------------------------------------------------------------------------

// The first screen is what asks (the summary, then the questions), then the buildings; what a phone does now
// and then (the Warchief, Drop file here, the look, Stop all) is the bar at the foot (dock.js).
function layout() {
  const parts = {
    status: h("p", { class: "status", role: "status" }),
    install: h("div"),
    head: h("header", { class: "head" }),
    news: h("div", { class: "news", "aria-live": "polite" }),
    summary: h("p", { class: "summary" }),
    alerts: h("div", { class: "list" }),
    buildings: h("ul", { class: "buildings" }),
    foot: h("p", { class: "muted foot" }),
  };
  parts.dock = makeDock({ send, flash, building, device: () => device, unpair: unpairHere, shared });
  show(parts.status, parts.install, parts.head, parts.news,
    h("section", { class: "card asking", "aria-labelledby": "answers-h" },
      h("h2", { id: "answers-h" }, "Answers"), parts.summary, parts.alerts),
    h("section", { class: "card" }, h("h2", {}, "Buildings"), parts.buildings),
    parts.foot, parts.dock.el, ...parts.dock.sheets);
  return parts;
}

// The town's version, quiet in the footer (mobile.hello): the one the computer runs, which this app is.
async function hello() {
  const r = await send("mobile.hello");
  if (!r.ok || !ui) return;
  version = r.result?.version || "";
  phoneLine();
}

let version = "";
function phoneLine() {
  ui.foot.textContent = `This phone: ${device?.name || ""}${version ? ` · Orkcraft ${version}` : ""}`;
  ui.dock.phone(version);
}

function status(text) {
  if (!ui) return;
  ui.status.textContent = text;
  ui.status.hidden = !text;
}

function flash(text) {
  if (!ui || !text) return;
  const line = h("p", { class: "flash" }, text);
  ui.news.prepend(line);
  setTimeout(() => line.remove(), 6000);
}

// Camp draws the town as it is (its titles with their emoji, the ork's mark); Office calm and plain, dark or
// light as the phone is. Only how things are drawn changes, never a word (CLAUDE.md: one vocabulary, two looks).
function applyLook(look) {
  const camp = look !== "office";
  document.documentElement.dataset.look = camp ? "camp" : "office";
  // The bar the system draws over the app takes the page's ground, so Office in light is light there too.
  document.querySelector('meta[name="theme-color"]')?.setAttribute("content",
    camp ? "#172a0a" : LIGHT.matches ? "#f4f4f4" : "#161616");
}
LIGHT.addEventListener?.("change", () => { if (town) applyLook(town.look); });

function render(s) {
  const first = !town;
  town = s;
  applyLook(s.look);
  const camp = s.look !== "office";
  const hud = s.hud || {};
  const words = s.resources || {};
  ui.head.replaceChildren(
    h("h1", {}, camp && h("img", { class: "mark", src: "icon-192.png", alt: "" }),
      s.project || "Orkcraft", s.demo ? h("small", {}, " demo") : null),
    h("div", { class: "hud" },
      hud.show_gold !== false && h("span", { class: `pill ${hud.gold_level || "ok"}` }, `${words.gold || "Spend"} ${hud.gold ?? ""}`),
      hud.quota && h("span", { class: `pill ${hud.quota_level || "ok"}` }, `${words.quota || "Quota"} ${hud.quota}`),
      h("span", { class: "pill" }, `${hud.agents_working ?? 0} of ${hud.agents ?? 0} orks working`)));

  const alerts = s.alerts || [];
  const n = alerts.length;
  const longest = Math.max(0, ...alerts.map((a) => a.waited || 0));
  ui.summary.textContent = n ? `${n === 1 ? "An ork waits" : `${n} orks wait`} on you, the longest ${minutes(longest)}.`
    : "No ork is waiting on you.";
  ui.summary.classList.toggle("asks", n > 0);
  ui.alerts.replaceChildren(...alerts.map(question));

  const asking = [...(s.buildings || [])].sort((x, y) => Boolean(y.alert) - Boolean(x.alert));   // what asks first
  ui.buildings.replaceChildren(...asking.map((b) => h("li", { class: b.alert ? "asks" : "" },
    h("span", { class: "name" }, camp ? b.title : (b.title_plain || b.title)), h("span", { class: "muted" }, b.state || ""),
    b.alert && h("span", { class: "badge" }, "asks"))));

  ui.dock.render(s);
  if (first) {
    phoneLine();
    if (shared) ui.dock.openDrop();             // shared from the phone's share sheet: Drop file here, filled
  }
}

const building = (type) => (town?.buildings || []).find((b) => b.type === type);

function question(a) {
  const msg = h("p", { class: "warn", hidden: true });
  const answer = async (name, args, buttons) => {
    buttons.forEach((b) => { b.disabled = true; });
    const r = await send(name, args);
    if (!r.ok) {
      msg.textContent = r.error;
      msg.hidden = false;
      buttons.forEach((b) => { b.disabled = false; });
    }
  };
  const buttons = [];
  for (const [key, label] of a.options || []) {
    buttons.push(h("button", { class: "btn", onclick: () => answer("orders.answer", { id: a.id, key }, buttons) }, label || key));
  }
  if (a.advice) {
    buttons.push(h("button", { class: "btn primary", onclick: () => answer("orders.follow", { id: a.id }, buttons) }, "Follow the Advisor"));
  }
  return h("article", { class: "question" },
    h("p", { class: "muted" }, `${a.who || "An ork"} · waiting ${minutes(a.waited || 0)}`),
    h("p", { class: "title" }, a.title),
    (a.context || []).length > 0 && h("pre", {}, a.context.join("\n")),
    a.advice && h("p", { class: "advice" }, `The Advisor suggests ${a.advice.key}: ${a.advice.why}`),
    h("div", { class: "answers" }, buttons), msg);
}

// -- news ---------------------------------------------------------------------------------------------

function news(items) {
  for (const item of items) {
    flash(item.line);
    if (document.visibilityState === "hidden" && "Notification" in window && Notification.permission === "granted") {
      navigator.serviceWorker?.ready.then((reg) => reg.showNotification("Orkcraft", { body: item.line, tag: item.id || item.kind, icon: "icon-192.png" }));
    }
  }
  if (items.length && navigator.vibrate) navigator.vibrate(80);
}

function unpairHere() {
  if (!confirm("Unpair this phone here? Forget it on the computer too: Town settings → Phones.")) return;
  store.clear();
  device = null;
  ui = null;
  ws?.close(1000);
  unpaired();
}

// -- start ----------------------------------------------------------------------------------------------

if (code) pairing(code);
else if (device?.token) connect();
else unpaired();
