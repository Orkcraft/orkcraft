// The town in a phone's browser (gui/pwa.py; docs/design/mobile.md §8.1, §10, a prototype). No framework and
// no build: the phone listener serves these files as they are (this one, util.js, dock.js, town.js, fields.js, icons.js). It speaks the
// phone's protocol (gui/phones.py): the compact snapshot (`state`), a command and its `reply`, and `news` while
// the app is open. It may do what a phone may (gui/mobile.py COMMANDS): answer a question, follow the Advisor,
// Stop all, ask the Workchief, drop a text, a link or a file into Drop file here and write a to-do, a note or a
// task on Task Fields. Nothing else, whatever
// this page sends: the listener refuses the rest.

import { h, store, kept, outbox, clock, guessName } from "./util.js";
import { makeDock } from "./dock.js";
import { makeTown, chosenSpace } from "./town.js";
import { wearGround } from "./ground.js";
import { makeFields } from "./fields.js";
import { makeLook } from "./look.js";
import { makeSlots } from "./slots.js";

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
    h("h1", {}, "Orkline"),
    note && h("p", { class: "warn" }, note),
    h("p", {}, "This phone is not paired with a town yet."),
    h("p", { class: "muted" }, "On the computer: Town settings → Phones → Pair a phone, then scan the second QR code, "
      + "“Open in the phone’s browser”, with this phone’s camera. Both need Tailscale, logged in, with HTTPS certificates on.")));
}

// Opened from the desktop's QR code: it pairs at once, by the phone's kind as its name (renamed nowhere yet).
function pairing(pairCode) {
  const msg = h("p", { class: "muted" }, "Pairing…");
  const again = h("button", { class: "ok-btn", hidden: true, onclick: () => pair(pairCode, guessName(), msg, again) }, "Try again");
  show(h("section", { class: "card" },
    h("h1", {}, "Pairing this phone"),
    h("p", {}, "It will see the town small: each building, the questions the orks wait on, spend and quotas. "
      + "It may answer a question, stop all, ask the Workchief and drop a text or a file. It never builds or types into a terminal."),
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
    if (version.api !== API) throw new Error(`This app speaks api ${API}, the town ${version.api}: update Orkline.`);
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
    h("p", {}, "Now add it to the Home Screen: Share → Add to Home Screen, then open Orkline from there."),
    h("p", { class: "muted" }, "Until then this page’s address holds the phone’s key: do not share it."),
    h("button", { class: "ok-btn", onclick: () => connect() }, "Use it in Safari for now")));
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
  const later = h("button", { class: "ok-btn", onclick: notNow }, "Not now");
  let card = null;
  if (STANDALONE || hiddenNow()) card = null;
  else if (installEvent) {
    const add = h("button", { class: "ok-btn primary", onclick: async () => {
      const e = installEvent;
      installEvent = null;
      await e.prompt();
      await e.userChoice.catch(() => null);
      banner();                                  // the browser offers it again itself, when it may
    } }, "Add");
    card = h("section", { class: "card install" },
      h("p", {}, "Add Orkline to the Home screen: it opens like an app, without the browser’s bar."),
      h("div", { class: "row" }, add, later));
  } else if (IOS) {
    handOff();
    card = h("section", { class: "card install" },
      h("p", {}, "Add Orkline to the Home Screen: tap Share (the square with an arrow up; under ⋯ on newer iOS), "
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
  if (!town) {                                   // the town as it was last seen, greyed, until it answers
    const last = kept.get();
    if (last?.state) { render(last.state, last.at); offline(last.at, "Connecting…"); }
  }
  opened = false;
  ws = new WebSocket(`wss://${location.host}/ws`, [PROTOCOL, `bearer.${device.token}`]);
  ws.onopen = () => { opened = true; retry = 1; status(""); hello(); flush(); };
  ws.onmessage = (e) => {
    let msg;
    try { msg = JSON.parse(e.data); } catch { return; }
    if (msg.t === "state") { render(msg.state); online(); }
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
    offline(seenAt, opened ? "The town went away: trying again…" : "Cannot reach the town: is it running, and Tailscale on?");
    retryTimer = setTimeout(connect, retry * 1000);
    retry = Math.min(retry * 2, 30);
  };
}

// Away from the town the phone shows what it last saw, greyed and said "as of", and acts on none of it: every
// button waits for a reply the town sends (docs/design/mobile.md §6). The page's foot (and Unpair here) stays
// usable, and so do Answers and the bar's Idea: an answer or an idea given with no signal is kept and sent when it
// returns (`deliver`).
let seenAt = 0;
function offline(at, why) {
  if (!ui) return;
  document.documentElement.classList.toggle("offline", Boolean(town));
  for (const el of ui.content()) el.inert = Boolean(town);
  status(town && at ? `As of ${clock(at)}. ${why}` : why);
}

function online() {
  document.documentElement.classList.remove("offline");
  for (const el of ui?.content() || []) el.inert = false;
}

// -- kept with no signal: answers and ideas (audience.md §2a.3) ----------------------------------------------

/** Send now, or with no signal keep it on the phone (`outbox`) and send it when the town answers again: an answer
 *  (the town says so if it was answered at the desk meanwhile) or an idea (a client id writes it once). `label`
 *  says what it was, when it is sent. {ok, kept, error, result}. */
async function deliver(name, args, label) {
  if (ws && ws.readyState === 1) {
    const r = await send(name, args);
    if (r.ok || r.error !== "The town went away") return r;
  }
  outbox.add({ name, args, label, at: Date.now() });
  return { ok: true, kept: true };
}

let flushing = false;
async function flush() {
  if (flushing) return;
  flushing = true;
  try {
    for (const item of outbox.all()) {
      if (!ws || ws.readyState !== 1) break;
      if (!outbox.claim(item.key)) continue;          // taken by another page of the app: never sent twice
      const r = await send(item.name, item.args);
      if (!r.ok && (r.error === "Not connected to the town" || r.error === "The town went away")) { outbox.restore(item); break; }
      flash(r.ok ? `Sent: ${item.label}` : `Not sent: ${item.label}. ${r.error}`);
    }
  } finally {
    flushing = false;
  }
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

// The first screen is what asks (the questions in their buildings' tiles, when any ork asks), Task Fields, then
// the orkspace's buildings: in trouble or at work, then the quiet ones as a grid (town.js); what a phone does now
// and then (the Workchief, Drop file here, Stop all) is the bar at the foot (dock.js), the look and this phone the
// page's own foot.
function layout() {
  const parts = {
    status: h("p", { class: "status", role: "status" }),
    install: h("div"),
    head: h("header", { class: "ok-hud head" }),
    news: h("div", { class: "news", "aria-live": "polite" }),
  };
  parts.town = makeTown({ send, deliver, flash, rerender: () => { if (town) { parts.town.render(town); ground(town); } } });
  parts.look = makeLook({ send, open: (id) => parts.town.open(id) });
  parts.fields = makeFields({ send, flash });
  parts.slots = makeSlots({ send, flash, open: (id) => parts.town.open(id) });
  parts.dock = makeDock({ send, deliver, flash, building, ideas: () => town?.ideas, device: () => device, unpair: unpairHere, shared });
  const [camp, answers, buildings, info, more] = parts.town.parts;
  // The town's parts acted on only while it answers (not its sheets, not Answers: an answer is kept offline).
  parts.content = () => [camp, parts.fields.el, buildings, parts.look.el];
  show(parts.status, parts.install, parts.head, parts.news, parts.look.el, camp, answers, parts.fields.el, buildings, info, more,
    parts.dock.foot, parts.dock.el, ...parts.dock.sheets, parts.fields.sheet, parts.slots.sheet);
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

// Camp draws the town as it is (its titles with their emoji, the ork's mark) on the design system's camp theme;
// Office calm and plain on its office theme, dark or light as the phone is. Only how things are drawn changes,
// never a word (CLAUDE.md: one vocabulary, two looks).
function applyLook(look) {
  const camp = look !== "office";
  document.documentElement.dataset.look = camp ? "camp" : "office";
  document.documentElement.dataset.theme = camp ? "camp" : "office";
}
LIGHT.addEventListener?.("change", () => { if (town) ground(town); });

// The page stands on the ground of the orkspace it shows, as the desktop's town does (ground.js), and the bar the
// system draws over the app takes that ground, so Office in light is light there too.
function ground(s) {
  const camp = s.look !== "office";
  const tint = wearGround(chosenSpace(s)?.biome || "dirt", camp);
  document.querySelector('meta[name="theme-color"]')?.setAttribute("content",
    camp ? tint : LIGHT.matches ? "#f4f4f4" : "#1a1813");
}

const LEVEL = { warn: "is-warn", over: "is-over" };
// A resource as the desktop's HUD draws it (js/chrome.js Resource; design system: Hud): its sprite in Camp, its
// word in Office, then its value.
// The score as the desktop's HUD has it (the-score.md): the tokens per accepted result this week and the trend; only
// what was recorded, the hint saying what is not measured yet. Nothing recorded: nothing shown.
function score(sc) {
  if (!sc || sc.tokens === null || sc.tokens === undefined) return null;
  const k = sc.tokens >= 1000 ? `${(sc.tokens / 1000).toFixed(1)}k` : String(Math.round(sc.tokens));
  const trend = sc.trend === null || sc.trend === undefined ? "" : `${sc.trend < 0 ? "↓" : "↑"}${Math.abs(Math.round(sc.trend * 100))}%`;
  const said = `Tokens per accepted result this week: ${k}${trend ? `, ${trend} on last week` : ""}. `
    + `Quality: 👎 ${sc.dislikes ?? 0}, sent back ${sc.reworks ?? 0} per result. Not measured yet: a cart's share of the window.`;
  return h("span", { class: `ok-res score${sc.lean ? " is-lean" : ""}`, title: said, "aria-label": said },
    h("img", { src: "icons/res-lumber.png", srcset: "icons/res-lumber.png 1x, icons/res-lumber@2x.png 2x", alt: "" }),
    h("span", { class: "ok-word" }, "per result"), k, trend ? h("small", { class: "trend" }, trend) : null);
}

function resource(icon, word, value, level) {
  return h("span", { class: `ok-res${LEVEL[level] ? ` ${LEVEL[level]}` : ""}` },
    h("img", { src: `icons/res-${icon}.png`, srcset: `icons/res-${icon}.png 1x, icons/res-${icon}@2x.png 2x`, alt: "" }),
    h("span", { class: "ok-word" }, word), value);
}

// `keptAt`: the town comes from this phone's storage (seen then), not from the socket.
function render(s, keptAt = 0) {
  const first = !town;
  town = s;
  seenAt = keptAt || Date.now();
  if (!keptAt) kept.set(s);
  badge((s.alerts || []).length + (s.pool_questions || []).length);
  applyLook(s.look);
  ground(s);
  const camp = s.look !== "office";
  const hud = s.hud || {};
  const words = s.resources || {};
  // The resources stand before the town's name, as the desktop's HUD has them: Quota, Spend while it is shown,
  // and the orks at work of all of them (the meat).
  ui.head.replaceChildren(
    h("div", { class: "hud" },
      hud.quota && resource("quota", words.quota || "Quota", hud.quota, hud.quota_level),
      hud.show_gold && hud.gold && resource("gold", words.gold || "Spend", hud.gold, hud.gold_level),
      meat(resource("meat", words.supply || "Orks", `${hud.agents_working ?? 0}/${hud.agents ?? 0}`, ""), hud, s),
      score(s.score)),
    h("h1", { class: "ok-hud__brand" }, camp && h("img", { class: "mark", src: "icon-192.png", alt: "" }),
      s.project || "Orkline", s.demo ? h("small", {}, " demo") : null));

  ui.look.render(s);
  ui.town.render(s);
  ui.fields.render(s);
  ui.slots.render(s);
  ui.dock.render(s);
  if (first) {
    phoneLine();
    if (shared) ui.dock.openDrop();             // shared from the phone's share sheet: Drop file here, filled
  }
}

// 🥩 The orks at work of all of them, as the desktop's HUD: a tap opens the list of orks at work or asking, with
// Stop all as its first row (slots.js; ork-console.md §8).
function meat(res, hud, s) {
  const sl = s.slots || {};
  const n = `${hud.agents_working ?? 0} of ${hud.agents ?? 0} orks working`;
  return h("button", { class: "meat", type: "button", "aria-label": `${n}: the orks at work`, title: n,
    onclick: () => ui.slots.open() }, res, sl.asks ? h("span", { class: "meat-sig" }, `❓${sl.asks}`) : null,
    sl.fire ? h("span", { class: "meat-sig" }, `🔥${sl.fire}`) : null);
}

// How many orks wait, in the page's title only: no badge on the app's icon, no dot to clear (audience.md §2a).
function badge(n) {
  document.title = n ? `(${n}) Orkline` : "Orkline";
  try { navigator.clearAppBadge?.().catch(() => {}); } catch { /* no badge here */ }
}

const building = (type) => (town?.buildings || []).find((b) => b.type === type);

// -- news ---------------------------------------------------------------------------------------------

function news(items) {
  for (const item of items) {
    flash(item.line);
    if (document.visibilityState === "hidden" && "Notification" in window && Notification.permission === "granted") {
      navigator.serviceWorker?.ready.then((reg) => reg.showNotification("Orkline", { body: item.line, tag: item.id || item.kind, icon: "icon-192.png" }));
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
