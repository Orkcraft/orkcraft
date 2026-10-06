// The page's one link to the town: the socket, the snapshot as a signal, commands as promises.
// The host sends a fresh snapshot whenever the town changes (gui/server.py); signals redraw only
// what read the parts that changed.
import { signal } from "@preact/signals";

export const town = signal(null);          // the last snapshot (gui/state.py), null until the first
export const online = signal(false);
export const toasts = signal([]);          // [{id, message, title, severity}]
export const details = signal({});         // building id → its window's state (gui/views/), for the open ones

const TOKEN = new URLSearchParams(location.search).get("t") || "";
const pending = new Map();
const terminals = new Map();               // session key → (kind, bytes) => void: who draws its frames                 // command id → {resolve, reject}
let socket = null;
let nextId = 1;

const TOAST_S = { information: 5, warning: 8, error: 10 };

// The town's words as the page says them (realm/lexicon.py): the code's Camp words in Office's —
// say("🗼 Watchtower") is "🗼 External listeners", say("Garrison") "Agents".
let saying = { words: null, re: null, to: null };
export function say(text) {
  const t = town.value;
  if (!text || !t || !t.words?.length) return text;
  if (saying.words !== t.words) {
    const esc = (w) => w.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
    saying = { words: t.words, to: new Map(t.words),
               // as lexicon._WORD: not inside a word nor a path (./loot/, src/roads.py)
               re: new RegExp(`(?<![\\p{L}\\p{N}_\\-/\\\\.])(?:${t.words.map(([w]) => esc(w)).join("|")})(?![\\p{L}\\p{N}_\\-/\\\\]|\\.[\\p{L}\\p{N}_])`, "gu") };
  }
  return String(text).replace(saying.re, (w) => saying.to.get(w) ?? w);
}

export function toast(message, severity = "information", title = "", timeout = null) {
  const id = nextId++;
  toasts.value = [...toasts.value, { id, message, title, severity }].slice(-5);
  const seconds = timeout || TOAST_S[severity] || 5;
  setTimeout(() => { toasts.value = toasts.value.filter((t) => t.id !== id); }, seconds * 1000);
}

export function dismiss(id) {
  toasts.value = toasts.value.filter((t) => t.id !== id);
}

/** One of a building's own acts, done by its worker (gui/views/<type>.py ACTS). */
export function act(id, name, args = {}) {
  return command("act", { id, act: name, args });
}

/** Send a command to the host; resolves with its result, rejects with its error (also toasted). */
export function command(name, args = {}) {
  return new Promise((resolve, reject) => {
    if (!socket || socket.readyState !== WebSocket.OPEN) {
      toast("Not connected to the town", "error");
      reject(new Error("offline"));
      return;
    }
    const id = nextId++;
    pending.set(id, { resolve, reject });
    socket.send(JSON.stringify({ t: "cmd", id, name, args }));
  }).catch((e) => {
    if (e.message !== "offline") toast(e.message, "error", name);
    throw e;
  });
}

/** Who draws a session's bytes (js/terminal.js); kind 0 is output, 1 the whole of it again. */
export function onTerminal(key, fn) {
  terminals.set(key, fn);
  return () => { if (terminals.get(key) === fn) terminals.delete(key); };
}

function frame(buf) {
  const bytes = new Uint8Array(buf);
  const kind = bytes[0], len = bytes[1];
  const key = new TextDecoder().decode(bytes.subarray(2, 2 + len));
  const fn = terminals.get(key);
  if (fn) fn(kind, bytes.subarray(2 + len));
}

function receive(msg) {
  if (msg.t === "state") {
    town.value = msg.state;
  } else if (msg.t === "detail") {
    details.value = { ...details.value, [msg.detail.id]: msg.detail };
  } else if (msg.t === "toast") {
    // The page drops pictographs and says Office words: the host sends each text as it is and `_plain`.
    toast(msg.message_plain ?? msg.message, msg.severity || "information", msg.title_plain ?? msg.title ?? "", msg.timeout);
  } else if (msg.t === "reply") {
    const p = pending.get(msg.id);
    if (!p) return;
    pending.delete(msg.id);
    if (msg.ok) p.resolve(msg.result);
    else p.reject(new Error(msg.error || "Refused"));
  }
}

export function connect() {
  const ws = new WebSocket(`ws://${location.host}/ws?t=${encodeURIComponent(TOKEN)}`);
  ws.onopen = () => { socket = ws; online.value = true; };
  ws.binaryType = "arraybuffer";
  ws.onmessage = (e) => (typeof e.data === "string" ? receive(JSON.parse(e.data)) : frame(e.data));
  ws.onclose = () => {
    online.value = false;
    socket = null;
    for (const p of pending.values()) p.reject(new Error("The town went away"));
    pending.clear();
    setTimeout(connect, 1000);
  };
}
