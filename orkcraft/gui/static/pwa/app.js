// The town in a phone's browser (gui/pwa.py; docs/design/mobile.md §8.1, a prototype). No framework and no
// build: the phone listener serves this file as it is. It speaks the phone's protocol (gui/phones.py): the
// compact snapshot (`state`), a command and its `reply`, and `news` while the app is open. It may do what a
// phone may (gui/mobile.py COMMANDS): answer a question, follow the Advisor, Stop all, ask the Warchief and
// drop a text, a link or a file into Drop file here. Nothing else, whatever this page sends: the listener
// refuses the rest.

const KEY = "orkcraft.device";          // {id, token, name}: this browser's pairing with the town
const PROTOCOL = "orkcraft.v1";
const API = 1;
const FILE_LIMIT = 5 * 1024 * 1024;     // as views/pit.py FILE_LIMIT
const IOS = "standalone" in navigator;  // only iOS Safari has navigator.standalone
const STANDALONE = matchMedia("(display-mode: standalone)").matches || navigator.standalone === true;

// -- small things -----------------------------------------------------------------------------------

function h(tag, attrs = {}, ...kids) {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (v === null || v === undefined || v === false) continue;
    if (k.startsWith("on")) el.addEventListener(k.slice(2), v);
    else if (k === "class") el.className = v;
    else el.setAttribute(k, v === true ? "" : v);
  }
  for (const kid of kids.flat()) if (kid !== null && kid !== undefined && kid !== false) el.append(kid);
  return el;
}

const store = {
  get() { try { return JSON.parse(localStorage.getItem(KEY)); } catch { return null; } },
  set(v) { try { localStorage.setItem(KEY, JSON.stringify(v)); } catch { /* private mode: this run only */ } },
  clear() { try { localStorage.removeItem(KEY); } catch { /* nothing kept */ } },
};

const app = document.getElementById("app");
const show = (...kids) => app.replaceChildren(...kids);
const minutes = (s) => (s < 60 ? `${Math.round(s)} s` : `${Math.round(s / 60)} min`);
const randomId = () => Array.from(crypto.getRandomValues(new Uint8Array(8)), (b) => b.toString(16).padStart(2, "0")).join("");

function guessName() {
  const ua = navigator.userAgent;
  if (/iPhone/.test(ua)) return "iPhone";
  if (/iPad/.test(ua)) return "iPad";
  if (/Android/.test(ua)) return "Android phone";
  return "Browser";
}

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
function homeScreen() {
  document.getElementById("manifest").href = `manifest.webmanifest?k=${encodeURIComponent(device.token)}`;
  history.replaceState(null, "", `${location.pathname}#k=${encodeURIComponent(device.token)}`);
  show(h("section", { class: "card" },
    h("h1", {}, `Paired: ${device.name}`),
    h("p", {}, "Now add it to the Home Screen: Share → Add to Home Screen, then open Orkcraft from there."),
    h("p", { class: "muted" }, "Until then this page’s address holds the phone’s key: do not share it."),
    h("button", { class: "btn", onclick: () => connect() }, "Use it in Safari for now")));
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
  status("Connecting…");
  opened = false;
  ws = new WebSocket(`wss://${location.host}/ws`, [PROTOCOL, `bearer.${device.token}`]);
  ws.onopen = () => { opened = true; retry = 1; status(""); };
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

function layout() {
  const parts = {
    status: h("p", { class: "status", role: "status" }),
    head: h("header", { class: "head" }),
    news: h("div", { class: "news", "aria-live": "polite" }),
    alerts: h("div", { class: "list" }),
    buildings: h("ul", { class: "buildings" }),
    chat: h("div", { class: "chat" }),
    stop: h("button", { class: "btn danger stop" }, "Stop all"),
  };
  let armed = 0;
  parts.stop.addEventListener("click", async () => {
    if (!armed) {                                // twice: a pocket must not stop the town
      parts.stop.textContent = "Tap again to stop every ork";
      armed = setTimeout(() => { armed = 0; parts.stop.textContent = "Stop all"; }, 4000);
      return;
    }
    clearTimeout(armed);
    armed = 0;
    parts.stop.disabled = true;
    const r = await send("halt");
    parts.stop.disabled = false;
    parts.stop.textContent = "Stop all";
    flash(r.ok ? `Stopped: ${r.result} session(s)` : r.error);
  });

  const ask = h("input", { class: "input", placeholder: "Ask the Warchief…", maxlength: "2000", enterkeyhint: "send" });
  const askBtn = h("button", { class: "btn", onclick: () => askWarchief(ask, askBtn) }, "Ask");
  ask.addEventListener("keydown", (e) => { if (e.key === "Enter") askWarchief(ask, askBtn); });

  const drop = h("textarea", { class: "input", rows: "3", placeholder: "A link or a text", maxlength: "20000" });
  drop.value = shared;
  const file = h("input", { type: "file", class: "file", "aria-label": "A file" });
  const dropBtn = h("button", { class: "btn", onclick: () => dropIt(drop, file, dropBtn) }, "Drop");

  parts.askSection = h("section", { class: "card" }, h("h2", {}, "Warchief"), h("div", { class: "row" }, ask, askBtn), parts.chat);
  parts.dropSection = h("section", { class: "card" }, h("h2", {}, "Drop file here"), drop, h("div", { class: "row" }, file, dropBtn));
  const notifyBtn = h("button", { class: "btn quiet", onclick: () => askNotify(notifyBtn) }, "Notify me while it is open");
  if (!("Notification" in window) || Notification.permission !== "default") notifyBtn.hidden = true;

  show(parts.status, parts.head, parts.news, parts.stop,
    h("section", { class: "card" }, h("h2", {}, "Answers"), parts.alerts),
    parts.askSection, parts.dropSection,
    h("section", { class: "card" }, h("h2", {}, "Buildings"), parts.buildings),
    h("footer", { class: "foot" },
      h("span", { class: "muted" }, `This phone: ${device?.name || ""}`), notifyBtn,
      h("button", { class: "btn quiet", onclick: unpairHere }, "Unpair here")));
  return parts;
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

function render(s) {
  town = s;
  const hud = s.hud || {};
  const words = s.resources || {};
  ui.head.replaceChildren(
    h("h1", {}, s.project || "Orkcraft", s.demo ? h("small", {}, " demo") : null),
    h("div", { class: "hud" },
      hud.show_gold !== false && h("span", { class: `pill ${hud.gold_level || "ok"}` }, `${words.gold || "Spend"} ${hud.gold ?? ""}`),
      hud.quota && h("span", { class: `pill ${hud.quota_level || "ok"}` }, `${words.quota || "Quota"} ${hud.quota}`),
      h("span", { class: "pill" }, `${hud.agents_working ?? 0} of ${hud.agents ?? 0} orks working`)));

  const alerts = s.alerts || [];
  ui.alerts.replaceChildren(...(alerts.length ? alerts.map(question) : [h("p", { class: "muted" }, "No ork is waiting on you.")]));

  const asking = [...(s.buildings || [])].sort((x, y) => Boolean(y.alert) - Boolean(x.alert));   // what asks first
  ui.buildings.replaceChildren(...asking.map((b) => h("li", { class: b.alert ? "asks" : "" },
    h("span", { class: "name" }, b.title_plain || b.title), h("span", { class: "muted" }, b.state || ""),
    b.alert && h("span", { class: "badge" }, "asks"))));

  ui.askSection.hidden = !building("town_hall");
  ui.dropSection.hidden = !building("pit");
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

// -- the Warchief and Drop file here ------------------------------------------------------------------

let chatTimer = 0;

async function askWarchief(input, button) {
  const text = input.value.trim();
  const hall = building("town_hall");
  if (!text || !hall) return;
  button.disabled = true;
  const r = await send("act", { id: hall.id, act: "ask", args: { text } });
  button.disabled = false;
  if (!r.ok) { flash(r.error); return; }
  input.value = "";
  readChat();
}

async function readChat() {
  clearTimeout(chatTimer);
  const r = await send("mobile.chat", { limit: 6 });
  if (!r.ok || !ui) return;
  const c = r.result;
  ui.chat.replaceChildren(...c.chat.map((m) => h("div", { class: `msg${m.error ? " warn" : ""}` },
    h("span", { class: "who" }, m.who === "user" ? "You" : (c.warchief || "Warchief")),
    h("p", {}, m.text || ""), m.offer && h("p", { class: "muted" }, "It offers a card: answer it at the computer."))),
    c.thinking ? h("p", { class: "muted" }, "Thinking…") : "");
  if (c.thinking) chatTimer = setTimeout(readChat, 3000);
}

async function dropIt(text, fileInput, button) {
  const pit = building("pit");
  if (!pit) return;
  const f = fileInput.files?.[0];
  if (!f && !text.value.trim()) return;
  if (f && f.size > FILE_LIMIT) { flash("The file is over 5 MB: drop it at the computer."); return; }
  button.disabled = true;
  // The client id makes a retry drop once (views/pit.py `once`).
  const r = f
    ? await send("act", { id: pit.id, act: "drop_file", args: { name: f.name, data: await base64(f), client_id: randomId() } })
    : await send("act", { id: pit.id, act: "drop", args: { text: text.value.trim(), client_id: randomId() } });
  button.disabled = false;
  if (!r.ok) { flash(r.error); return; }
  flash("Dropped.");
  text.value = "";
  fileInput.value = "";
}

function base64(file) {
  return new Promise((resolve, reject) => {
    const r = new FileReader();
    r.onload = () => resolve(String(r.result).split(",", 2)[1] || "");
    r.onerror = () => reject(r.error);
    r.readAsDataURL(file);
  });
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

async function askNotify(button) {
  const got = await Notification.requestPermission();
  button.hidden = got !== "default";
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
